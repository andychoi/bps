from django.db import models, transaction
from django.contrib.contenttypes.models import ContentType
from .models_dimension import Year, Version, OrgUnit


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

class PlanningDimension(models.Model):
    """ Specifies what dimensions are visible, editable, filtered.
    API, expose the distinct values for that dimension (e.g. GET /api/planning-grid/headers/?dim=Region&layout=123) and accept a query‐param like &Region=EMEA to filter.
    """
    layout = models.ForeignKey(PlanningLayout, related_name="dimensions", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # e.g. "SkillGroup", "System", "ServiceType"
    label = models.CharField(max_length=100)
    is_row = models.BooleanField(default=False)
    is_column = models.BooleanField(default=False)
    is_filter = models.BooleanField(default=True)
    is_editable = models.BooleanField(default=False)
    required = models.BooleanField(default=True)
    data_source = models.CharField(max_length=100)  # optional: e.g. 'SkillGroup.objects.all()'
    is_navigable = models.BooleanField(default=False,
        help_text="If true, UI should render Prev/Next controls for this dimension"
    )
    display_order = models.PositiveSmallIntegerField(default=0)


class PlanningLayoutDimension(models.Model):
    """
    Example in views
        layout_dims = layout_year.layout_dimensions.filter(is_row=True).order_by('order')
        ctx["lead_dimensions"] = [
            {
            "model": ld.content_type.model,
            "label": ld.content_type.model_class()._meta.verbose_name,
            "order": ld.order,
            "allowed": ld.allowed_values,
            "filters": ld.filter_criteria,
            }
            for ld in layout_dims
        ]    
    """
    layout_year    = models.ForeignKey(PlanningLayoutYear,
                                       on_delete=models.CASCADE,
                                       related_name="layout_dimensions")
    content_type   = models.ForeignKey(ContentType,
                                       on_delete=models.CASCADE)
    is_row         = models.BooleanField(default=False)
    is_column      = models.BooleanField(default=False)

    order          = models.PositiveSmallIntegerField(default=0,
                        help_text="Defines the sequence in the grid")

    # Optional: constrain available values
    allowed_values = models.JSONField(blank=True, default=list,
                        help_text="List of allowed PKs or codes")
    filter_criteria= models.JSONField(blank=True, default=dict,
                        help_text="Extra filters to apply when building headers")
    

class PlanningKeyFigure(models.Model):
    """ Key figures used in the layout: amount, quantity, derived ones.
    """
    layout = models.ForeignKey(PlanningLayout, related_name="key_figures", on_delete=models.CASCADE)
    code = models.CharField(max_length=100)  # e.g. 'amount', 'quantity', 'cost_per_mm'
    label = models.CharField(max_length=100)
    is_editable = models.BooleanField(default=True)
    is_computed = models.BooleanField(default=False)
    formula = models.TextField(blank=True)  # e.g. 'amount = quantity * rate'
    display_order = models.PositiveSmallIntegerField(default=0)

