from django.db import models, transaction
# from .models_layout import PlanningLayoutYear

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
    layout_year = models.ForeignKey('bps.PlanningLayoutYear', on_delete=models.CASCADE,
                                    related_name='period_groupings')
    # number of months per bucket: 1, 3 or 6
    months_per_bucket = models.PositiveSmallIntegerField(choices=[(1,'Monthly'),(3,'Quarterly'),(6,'Half-Year')])
    # optional label prefix e.g. 'Q' or 'H'
    label_prefix = models.CharField(max_length=5, default='')

    class Meta:
        unique_together = ('layout_year','months_per_bucket')

    def buckets(self):
        # from bps.models.models import Period
        months = list(Period.objects.order_by('order'))
        size = self.months_per_bucket
        buckets = []
        for i in range(0, 12, size):
            group = months[i:i+size]
            if size == 1:  # monthly -> use real period codes
                code = group[0].code        # e.g. "01"
                name = group[0].name        # e.g. "Jan"
            else:
                idx = (i // size) + 1
                code = f"{self.label_prefix}{idx}"  # e.g. "Q1"
                name = code
            buckets.append({'code': code, 'name': name, 'periods': group})
        return buckets
