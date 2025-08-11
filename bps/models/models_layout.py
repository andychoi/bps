from django.db import models, transaction
from django.contrib.contenttypes.models import ContentType
from .models_dimension import Year, Version, OrgUnit
# from .models import KeyFigure

SHORT_LABELS = {
    "orgunit": "OU",
    "service": "Srv",
    "internalorder": "IO",
    "position": "Pos",
    "skill": "Skill",
    # "year": "Yr",      # intentionally not shown in context
    # "version": "Ver",  # intentionally not shown in context
    # "period": "Per",   # period lives in KF columns, not context
}
EXCLUDE_FROM_CONTEXT = {"year", "version", "period"}

def _resolve_value(Model, raw):
    if not raw:
        return None
    if isinstance(raw, int):
        return Model.objects.filter(pk=raw).first()
    if hasattr(Model, "code"):
        return Model.objects.filter(code=raw).first()
    return Model.objects.filter(pk=raw).first()

class PlanningLayout(models.Model):
    """
    Defines which dims & periods & key‐figures go into a layout.
    """
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    domain = models.CharField(max_length=100)  # e.g. 'resource', 'cost', 'demand'
    default = models.BooleanField(default=False)

    def __str__(self):
        return self.code

# TEMPLATE-LEVEL dimension declaration (single source of truth)
class PlanningLayoutDimension(models.Model):
    layout        = models.ForeignKey(
        PlanningLayout, related_name="dimensions", on_delete=models.CASCADE
    )
    content_type  = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    is_row        = models.BooleanField(default=False)
    is_column     = models.BooleanField(default=False)
    is_header     = models.BooleanField(
        default=False,
        help_text="If true, UI should render a header selector for this dimension."
    )
    order         = models.PositiveSmallIntegerField(default=0,
                      help_text="Defines the sequence in the grid")
    group_priority = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="1,2,3… to enable nested row grouping (lower = outer); leave blank to not group by this dimension."
    )
    
    class Meta:
        ordering = ["order", "id"]
        unique_together = ("layout", "content_type", "is_row", "is_column", "is_header")

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
    # row_dims  = models.ManyToManyField(ContentType, blank=True)
    # Selected header defaults/slice, e.g. {'Company': 3, 'Region': 'NA'}
    header_dims = models.JSONField(default=dict, help_text="e.g. {'Company':3,'Region':'NA'}")

    class Meta:
        unique_together = ('layout','year','version')
    def __str__(self):
        return f"{self.layout.name} – {self.year.code} / {self.version.code}"

    def header_defaults(self):
        base = dict(self.header_dims or {})
        # if you use per-dimension overrides, merge them here as needed
        return base

    def header_pairs(self, *, use_short_labels=True, short_values=True, exclude=EXCLUDE_FROM_CONTEXT):
        """
        Returns label/value pairs for header selections to show in the compact context line,
        excluding Year/Version/Period by default.
        """
        pairs = []
        defaults = self.header_defaults()
        dims = self.layout.dimensions.filter(is_header=True).select_related("content_type").order_by("order")
        for dim in dims:
            ct = dim.content_type
            key = ct.model  # lowercase model name, e.g. "orgunit", "service", "year"...
            if key in (exclude or set()):
                continue

            Model = ct.model_class()
            label = SHORT_LABELS.get(key, Model._meta.verbose_name.title() if not use_short_labels else key[:3].title())
            raw = defaults.get(key)
            inst = _resolve_value(Model, raw)
            if not inst:
                val = "All"
            else:
                val = getattr(inst, "code", None) or getattr(inst, "name", str(inst))
            pairs.append((label, val))
        return pairs

    def header_string(self, exclude=EXCLUDE_FROM_CONTEXT):
        return " · ".join(f"{k}: {v}" for k, v in self.header_pairs(exclude=exclude))
    

# INSTANCE — per year/version tweaks only (NO is_row/is_column/is_header here)
class LayoutDimensionOverride(models.Model):
    layout_year      = models.ForeignKey(PlanningLayoutYear, related_name="dimension_overrides", on_delete=models.CASCADE)
    dimension = models.ForeignKey(PlanningLayoutDimension, related_name="overrides", on_delete=models.CASCADE)

    # Optional: constrain values or filter lists for this LY
    allowed_values   = models.JSONField(blank=True, default=list)   # list of PKs or codes
    filter_criteria  = models.JSONField(blank=True, default=dict)   # e.g. {"tier": ["1","2"]}

    # Optional: pick a default header slice for this LY
    header_selection = models.PositiveIntegerField(null=True, blank=True)

    # Optional: per-instance order tweak (rarely needed)
    order_override   = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("layout_year", "dimension")


class PlanningKeyFigure(models.Model):
    """
    Link layout to global KeyFigure, keeping per-layout UI flags.
    """
    layout        = models.ForeignKey(PlanningLayout, related_name="key_figures", on_delete=models.CASCADE)
    key_figure    = models.ForeignKey('bps.KeyFigure', on_delete=models.CASCADE)
    is_editable   = models.BooleanField(default=True)
    is_computed   = models.BooleanField(default=False)
    formula       = models.TextField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "id"]
        unique_together = ("layout", "key_figure")
     