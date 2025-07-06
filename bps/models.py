# bps/models.py

from uuid import uuid4
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
# from django.contrib.postgres.fields import JSONField

# ── 1. InfoObject Base & Dimension Models ─────────────────────────────────

class UnitOfMeasure(models.Model):
    """
    Master list of units (e.g. 'EA', 'KG', 'HRS', 'USD').
    The 'base' flag marks the canonical target for conversions.
    """
    code        = models.CharField(max_length=10, unique=True)
    name        = models.CharField(max_length=50)
    is_base     = models.BooleanField(default=False,
                                      help_text="Target unit for conversion rates")
    def __str__(self):
        return self.code

class ConversionRate(models.Model):
    """
    Conversion factors between units:
      value_in_to_unit = factor * value_in_from_unit
    """
    from_uom = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE,
                                 related_name='conv_from')
    to_uom   = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE,
                                 related_name='conv_to')
    factor   = models.DecimalField(max_digits=18, decimal_places=6,
                                   help_text="Multiply a from_uom value by this to get to_uom")
    class Meta:
        unique_together = ('from_uom','to_uom')
    def __str__(self):
        return f"1 {self.from_uom} → {self.factor} {self.to_uom}"
    
class InfoObject(models.Model):
    """
    Abstract base for any dimension (Year, Period, Version, OrgUnit, etc.).
    """
    code        = models.CharField(max_length=20, unique=True)
    name        = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    order       = models.IntegerField(default=0,
                      help_text="Controls ordering in UIs")

    class Meta:
        abstract = True
        ordering = ['order', 'code']

    def __str__(self):
        return self.name

class Year(InfoObject):
    """e.g. code='2025', name='Fiscal Year 2025'"""

class Version(InfoObject):
    """
    A global dimension (e.g. 'Draft', 'Final', 'Plan v1', 'Plan v2').
    Used to isolate concurrent planning streams.
    """

class OrgUnit(InfoObject):
    head_user      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        help_text="OrgUnit lead who must draft and approve"
    )
    parent         = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children'
    )
    cc_code    = models.CharField(max_length=10, blank=True)    # SAP cost center code

class Account(InfoObject):
    pass

class CostCenter(InfoObject):
    pass

class InternalOrder(InfoObject):
    cc_code    = models.CharField(max_length=10, blank=True)    # SAP cost center code


class UserMaster(models.Model):
    """
    Links your custom user profile to OrgUnit & CostCenter.
    """
    user      = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    org_unit  = models.ForeignKey(OrgUnit, on_delete=models.SET_NULL, null=True)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

class CBU(InfoObject):
    """Client Business Unit (inherits InfoObject)"""


# ── 2. PlanningLayout & Year‐Scoped Layouts ─────────────────────────────────

class PlanningLayout(models.Model):
    """
    Defines which dims & periods & key‐figures go into a layout.
    Can be versioned per year.
    """
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    # eg. ["Revenue","Qty"]
    key_figures = models.JSONField(default=list)

    def __str__(self):
        return self.name

class PlanningLayoutYear(models.Model):
    """
    Binds a PlanningLayout to a specific Year with its own dims.
    Allows per‐year changes in dimensions.
    """
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE, related_name='per_year')
    year   = models.ForeignKey(Year, on_delete=models.CASCADE)
    version= models.ForeignKey(Version, on_delete=models.CASCADE)
    # which OrgUnits participate this year?
    org_units = models.ManyToManyField(OrgUnit, blank=True)
    # which dims (ContentTypes) are row dims
    row_dims  = models.ManyToManyField(ContentType, blank=True)
    # static dims in header
    header_dims = models.JSONField(default=dict,
                      help_text="e.g. {'Company':'ALL','Region':'EMEA'}")

    class Meta:
        unique_together = ('layout','year','version')
    def __str__(self):
        return f"{self.layout.name} – {self.year.code} / {self.version.code}"


# ── 3. Period + Grouping ────────────────────────────────────────────────────

class Period(models.Model):
    """
    Months 01–12.  name='Jan', order=1, code='01'
    """
    code   = models.CharField(max_length=2, unique=True)
    name   = models.CharField(max_length=10)  # 'Jan','Feb',…,'Dec'
    order  = models.PositiveSmallIntegerField()

    def __str__(self):
        return self.name

class PeriodGrouping(models.Model):
    """
    Allows each layout‐year to choose how to group months:
    - monthly (1) → 12 columns
    - quarterly (3) → Q1…Q4
    - half-year (6) → H1, H2
    """
    layout_year = models.ForeignKey(PlanningLayoutYear, on_delete=models.CASCADE,
                                    related_name='period_groupings')
    # number of months per bucket: 1, 3 or 6
    months_per_bucket = models.PositiveSmallIntegerField(choices=[(1,'Monthly'),(3,'Quarterly'),(6,'Half-Year')])
    # optional label prefix e.g. 'Q' or 'H'
    label_prefix = models.CharField(max_length=5, default='')

    class Meta:
        unique_together = ('layout_year','months_per_bucket')

    def buckets(self):
        """
        Return list of dicts: {'code':'Q1','name':'Q1', 'periods':[Period,…]}
        """
        from itertools import groupby
        qs = self.layout_year.layout.year.period_set.order_by('order')
        months = list(qs)
        size   = self.months_per_bucket
        buckets = []
        for i in range(0, 12, size):
            group = months[i:i+size]
            idx   = (i//size)+1
            code  = f"{self.label_prefix}{idx}"
            buckets.append({'code':code, 'name':code, 'periods':group})
        return buckets


# ── 4. Workflow: PlanningSession ────────────────────────────────────────────

class PlanningSession(models.Model):
    """
    One OrgUnit’s planning for one layout‐year.
    """
    layout_year = models.ForeignKey(PlanningLayoutYear, on_delete=models.CASCADE,
                                    related_name='sessions')
    org_unit    = models.ForeignKey(OrgUnit, on_delete=models.CASCADE,
                                    help_text="Owner of this session")
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    # Draft → Completed (owner) → Frozen (admin)
    class Status(models.TextChoices):
        DRAFT     = 'D','Draft'
        COMPLETED = 'C','Completed'
        FROZEN    = 'F','Frozen'
    status      = models.CharField(max_length=1,
                                   choices=Status.choices,
                                   default=Status.DRAFT)
    frozen_by   = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='+')
    frozen_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('layout_year','org_unit')
    def __str__(self):
        return f"{self.org_unit.name} – {self.layout_year}"

    def can_edit(self, user):
        if self.status == self.Status.DRAFT and user == self.org_unit.head_user:
            return True
        return False

    def complete(self, user):
        if user == self.org_unit.head_user:
            self.status = self.Status.COMPLETED
            self.save()

    def freeze(self, user):
        # planning admin only
        self.status    = self.Status.FROZEN
        self.frozen_by = user
        self.frozen_at = models.functions.Now()
        self.save()


# ── 5. Fact & EAV (as before) ───────────────────────────────────────────────

class DataRequest(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    session     = models.ForeignKey(PlanningSession, on_delete=models.CASCADE,
                                    related_name='requests')
    description = models.CharField(max_length=200, blank=True)
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.session} – {self.description or self.id}"


class PlanningFact(models.Model):
    """
    One “row” of plan data for a given DataRequest + Period.
    Most plans have both Quantity and Amount; we surface them.
    """
    request      = models.ForeignKey(DataRequest,
                                     on_delete=models.PROTECT,
                                     related_name='facts')
    session      = models.ForeignKey(PlanningSession,
                                     on_delete=models.CASCADE,
                                     related_name='facts')
    period       = models.CharField(max_length=10)     # '01','Q1','H1'
    row_values   = models.JSONField(default=dict,
                 help_text="Dynamic dims: {'OrgUnit':12,'Product':34}")

    # ← First-class key-figures instead of value      = models.DecimalField(max_digits=18, decimal_places=2)
    quantity     = models.DecimalField(max_digits=18, decimal_places=3,
                                       default=0,
                                       help_text="Planned quantity in quantity_uom")
    quantity_uom = models.ForeignKey(UnitOfMeasure,
                                     on_delete=models.PROTECT,
                                     related_name='+',
                                     null=True, blank=True)
    amount       = models.DecimalField(max_digits=18, decimal_places=2,
                                       default=0,
                                       help_text="Planned amount in amount_uom")
    amount_uom   = models.ForeignKey(UnitOfMeasure,
                                     on_delete=models.PROTECT,
                                     related_name='+',
                                     null=True, blank=True)

    # ← Legacy generic slot, for any other key-figure
    other_key_figure = models.CharField(max_length=100, blank=True)
    other_value      = models.DecimalField(max_digits=18, decimal_places=2,
                                           null=True, blank=True)

    class Meta:
        unique_together = (
            'request','period','other_key_figure','row_values'
        )
    def __str__(self):
        return (f"{self.session} | {self.period} | "
                f"Qty={self.quantity}{self.quantity_uom or ''}  "
                f"Amt={self.amount}{self.amount_uom or ''}")

    def get_amount_in(self, target_uom_code):
        """
        Return self.amount converted into the unit target_uom_code.
        """
        if not self.amount_uom:
            return None
        if self.amount_uom.code == target_uom_code:
            return self.amount
        to_uom = UnitOfMeasure.objects.get(code=target_uom_code, is_base=True)
        rate  = ConversionRate.objects.get(
            from_uom=self.amount_uom,
            to_uom=to_uom
        ).factor
        return round(self.amount * rate, 2)
    
class PlanningFunction(models.Model):
    FUNCTION_CHOICES = [
        ('COPY', 'Copy'),
        ('DISTRIBUTE', 'Distribute'),
        ('REVALUE', 'Revalue'),
        ('AGGREGATE', 'Aggregate'),
    ]
    name = models.CharField(max_length=50)
    function_type = models.CharField(choices=FUNCTION_CHOICES, max_length=20)
    parameters = models.JSONField(default=dict)    

class GlobalVariable(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    value = models.DecimalField(max_digits=18, decimal_places=6)    

class Constant(models.Model):
    """
    A named constant for use in formulas, e.g. TAX_RATE=0.15.
    """
    name  = models.CharField(max_length=100, unique=True)
    value = models.DecimalField(max_digits=18, decimal_places=6)

    def __str__(self):
        return f"{self.name} = {self.value}"


class SubFormula(models.Model):
    """
    A reusable sub‐expression fragment, referenced in formulas via $NAME.
    """
    name       = models.CharField(max_length=100, unique=True)
    expression = models.TextField(
        help_text="Expression using other constants/sub‐formulas, e.g. [Year=2025]?.[Qty] * TAX_RATE"
    )

    def __str__(self):
        return self.name


class Formula(models.Model):
    """
    A full formula. loop_dimension tells Executor which dimension to iterate.
    Expression syntax:  [Dim=val,…]?.[Key] = <arithmetic with [..]?.[..], $SUB, CONSTANT>
    """
    name           = models.CharField(max_length=100, unique=True)
    loop_dimension = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="InfoObject (e.g. Product) to loop over"
    )
    expression     = models.TextField(
        help_text="e.g. [OrgUnit=12,Product=$LOOP]?.[amount] = [..]?.[quantity] * $RATE"
    )

    def __str__(self):
        return self.name


class FormulaRun(models.Model):
    """
    Audit of a single formula execution.
    """
    formula   = models.ForeignKey(Formula, on_delete=models.CASCADE)
    run_at    = models.DateTimeField(auto_now_add=True)
    preview   = models.BooleanField(default=False)
    run_by    = models.ForeignKey(settings.AUTH_USER_MODEL,
                                  null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Run #{self.pk} of {self.formula.name} @ {self.run_at}"


class FormulaRunEntry(models.Model):
    """
    One “cell” change by a FormulaRun.
    """
    run        = models.ForeignKey(FormulaRun, related_name='entries', on_delete=models.CASCADE)
    record     = models.ForeignKey('PlanningFact', on_delete=models.CASCADE)
    key        = models.CharField(max_length=100)       # e.g. 'amount' or 'other_key'
    old_value  = models.DecimalField(max_digits=18, decimal_places=6)
    new_value  = models.DecimalField(max_digits=18, decimal_places=6)

    def __str__(self):
        return f"{self.record} :: {self.key}: {self.old_value} → {self.new_value}"
    
        