# bps/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import re
from django.core.exceptions import ValidationError

class Year(models.Model):
    value = models.PositiveIntegerField(unique=True)

    def __str__(self):
        return str(self.value)

class PlanVersion(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class OrgUnit(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Account(models.Model):
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.code} - {self.name}"

class CBU(models.Model):
    name = models.CharField(_("name"), max_length=10, db_index=True, unique=True)
    fullname = models.CharField(_("full name"), max_length=100)
    group = models.CharField(_("group name"), max_length=100, blank=True, null=True)
    is_active = models.BooleanField(_("is active"), default=True)
    is_tier1 = models.BooleanField(_("is Tier-1"), default=False)

    class Meta:
        ordering = ["id"]
        verbose_name = _("CBU")
        verbose_name_plural = _("CBU")

    def __str__(self):
        return self.name
    
class Period(models.Model):
    code = models.CharField(max_length=10)
    order = models.PositiveIntegerField()

    def __str__(self):
        return self.code

class PriceType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name
    
class PlanningLayout(models.Model):
    name = models.CharField(max_length=100)
    lead_dimensions = models.ManyToManyField(
        ContentType,
        through='PlanningLayoutLeadDimension',
        related_name='lead_dimensions'
    )
    column_dimension = models.ForeignKey(
        ContentType,
        null=True,
        on_delete=models.SET_NULL,
        related_name='column_dimension'
    )
    key_figures = models.JSONField(default=list)

    def __str__(self):
        return self.name

# class PlanDimension(models.Model):
#     year        = models.PositiveIntegerField()
#     version     = models.CharField(max_length=50)
#     org_unit    = models.CharField(max_length=100)
#     account     = models.CharField(max_length=100)
#     period      = models.CharField(max_length=20)
#     cbu         = models.ForeignKey(CBU, on_delete=models.PROTECT, verbose_name=_("CBU"))

#     class Meta:
#         unique_together = (
#             "year", "version", "org_unit", "account", "period", "cbu"
#         )

#     def __str__(self):
#         return f"{self.year}/{self.version} – {self.org_unit}/{self.account}/{self.period} – {self.cbu}"

class PlanningLayoutLeadDimension(models.Model):
    bpslayout = models.ForeignKey(
        PlanningLayout,
        on_delete=models.CASCADE
    )
    contenttype = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ('bpslayout', 'contenttype')

class PlanningRecord(models.Model):
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE)
    # FK fields for dimension filtering
    year = models.ForeignKey(Year, null=True, blank=True, on_delete=models.SET_NULL)
    version = models.ForeignKey(PlanVersion, null=True, blank=True, on_delete=models.SET_NULL)
    orgunit = models.ForeignKey(OrgUnit, null=True, blank=True, on_delete=models.SET_NULL)
    account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL)
    cbu     = models.ForeignKey(CBU,       null=True, blank=True, on_delete=models.SET_NULL)
    period = models.ForeignKey(Period, null=True, blank=True, on_delete=models.SET_NULL)
    # Flexible data
    dimension_values = models.JSONField(default=dict)
    key_figure_values = models.JSONField(default=dict)

    def __str__(self):
        parts = [str(self.layout)]
        if self.period: parts.append(str(self.period))
        return " | ".join(parts)

class Constant(models.Model):
    name = models.CharField(max_length=100, unique=True)
    value = models.FloatField()

    def __str__(self):
        return f"{self.name}={self.value}"

class SubFormula(models.Model):
    name = models.CharField(max_length=100, unique=True)
    expression = models.TextField()
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

class Formula(models.Model):
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    loop_dimension = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    expression = models.TextField()

    def __str__(self):
        return self.name

class FormulaRun(models.Model):
    formula = models.ForeignKey(Formula, on_delete=models.CASCADE)
    run_at = models.DateTimeField(auto_now_add=True)
    preview = models.BooleanField(default=False)

    def __str__(self):
        return f"Run {self.id} of {self.formula.name}"

class FormulaRunEntry(models.Model):
    run = models.ForeignKey(FormulaRun, related_name='entries', on_delete=models.CASCADE)
    record = models.ForeignKey(PlanningRecord, on_delete=models.CASCADE)
    key = models.CharField(max_length=100)
    old_value = models.FloatField()
    new_value = models.FloatField()

    def __str__(self):
        return f"{self.record}: {self.key} {self.old_value} → {self.new_value}"
    
class Hierarchy(models.Model):
    """
    A named hierarchy (e.g. 'CBU Regions', 'Product Families', 'Account Segments').
    """
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Hierarchy"
        verbose_name_plural = "Hierarchies"

    def __str__(self):
        return self.name


class HierarchyNode(models.Model):
    """
    A single node in a Hierarchy, with an optional regex
    that will match raw values and assign them to this node.
    """
    hierarchy = models.ForeignKey(
        Hierarchy,
        on_delete=models.CASCADE,
        related_name="nodes"
    )
    parent    = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="children"
    )
    name      = models.CharField(max_length=100)
    regex     = models.CharField(
        max_length=200,
        blank=True,
        help_text="A Python-style regex that, when matched against a raw dimension value, assigns that value to this node."
    )
    order     = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = (('hierarchy', 'name'),)
        ordering = ('hierarchy', 'order',)

    def __str__(self):
        return f"{self.hierarchy.name}: {self.name}"

    def clean(self):
        # ensure the regex compiles
        if self.regex:
            try:
                re.compile(self.regex)
            except re.error as e:
                raise ValidationError({'regex': f"Invalid regex: {e}"})

    def matches(self, raw_value: str) -> bool:
        """Return True if this node’s regex matches the supplied raw_value."""
        if not self.regex:
            return False
        return bool(re.search(self.regex, raw_value))


# Optional utility: assign a raw_value to the first matching node
def classify_value(hierarchy: Hierarchy, raw_value: str) -> HierarchyNode:
    """
    Given a Hierarchy and a raw dimension value (string),
    return the first node whose regex matches, or None.
    """
    for node in hierarchy.nodes.order_by('order'):
        if node.matches(raw_value):
            return node
    return None