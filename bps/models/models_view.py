from django.db import models

class PivotedPlanningFact(models.Model):
    version = models.CharField(max_length=50)
    year = models.IntegerField()
    org_unit = models.CharField(max_length=50)
    service = models.CharField(max_length=50)
    account = models.CharField(max_length=50)
    key_figure = models.CharField(max_length=50)
    # Value columns
    v01 = models.FloatField(null=True, blank=True)
    v02 = models.FloatField(null=True, blank=True)
    v03 = models.FloatField(null=True, blank=True)
    v04 = models.FloatField(null=True, blank=True)
    v05 = models.FloatField(null=True, blank=True)
    v06 = models.FloatField(null=True, blank=True)
    v07 = models.FloatField(null=True, blank=True)
    v08 = models.FloatField(null=True, blank=True)
    v09 = models.FloatField(null=True, blank=True)
    v10 = models.FloatField(null=True, blank=True)
    v11 = models.FloatField(null=True, blank=True)
    v12 = models.FloatField(null=True, blank=True)
    # Reference value columns
    r01 = models.FloatField(null=True, blank=True)
    r02 = models.FloatField(null=True, blank=True)
    r03 = models.FloatField(null=True, blank=True)
    r04 = models.FloatField(null=True, blank=True)
    r05 = models.FloatField(null=True, blank=True)
    r06 = models.FloatField(null=True, blank=True)
    r07 = models.FloatField(null=True, blank=True)
    r08 = models.FloatField(null=True, blank=True)
    r09 = models.FloatField(null=True, blank=True)
    r10 = models.FloatField(null=True, blank=True)
    r11 = models.FloatField(null=True, blank=True)
    r12 = models.FloatField(null=True, blank=True)
    # Totals
    total_value = models.FloatField(null=True, blank=True)
    total_reference = models.FloatField(null=True, blank=True)

    class Meta:
        managed = False  # Do not let Django manage the database schema
        db_table = 'pivoted_planningfact'  # Match the view name
