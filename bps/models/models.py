# bps/models.py

from uuid import uuid4
from django.db import models, transaction
from django.contrib.postgres.fields import JSONField
from django.shortcuts import get_object_or_404
from django.db.models import Sum
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from treebeard.mp_tree import MP_Node
# from django.contrib.postgres.fields import JSONField

class TimestampModel(models.Model):
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    class Meta: abstract = True

# ── 0. Cross Models ─────────────────────────────────

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
    from_uom = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE, related_name='conv_from')
    to_uom   = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE, related_name='conv_to')
    factor   = models.DecimalField(max_digits=18, decimal_places=6,
                                   help_text="Multiply a from_uom value by this to get to_uom")
    class Meta:
        unique_together = ('from_uom','to_uom')
    def __str__(self):
        return f"1 {self.from_uom} → {self.factor} {self.to_uom}"
    
# ── InfoObject Base & Dimension Models ─────────────────────────────────
from .models_dimension import *


# ── # RESOURCE Models ─────────────────────────────────
from .models_resource import *


class UserMaster(models.Model):
    """
    Links your custom user profile to OrgUnit & CostCenter.
    """
    user      = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # org_unit  = models.ForeignKey(OrgUnit, on_delete=models.SET_NULL, null=True)
    # FIXME
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username
    

class KeyFigure(models.Model):
    """ “PlanAmount”, “ActualQuantity”, “FTE”, “Utilization%”, etc.
    """
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    is_percent = models.BooleanField(default=False)
    default_uom = models.ForeignKey(UnitOfMeasure, null=True, on_delete=models.SET_NULL)

# Pre-populate some KeyFigures for your rates:
# hourly_rate = KeyFigure.objects.create(code='HOURLY_RATE', name='Hourly Rate (Fully Loaded)')
# base_salary_hourly_equiv = KeyFigure.objects.create(code='BASE_SALARY_HRLY', name='Base Salary Hourly Equivalent')
# benefits_hourly_equiv = KeyFigure.objects.create(code='BENEFITS_HRLY', name='Benefits Hourly Equivalent')
# payroll_tax_hourly_equiv = KeyFigure.objects.create(code='PAYROLL_TAX_HRLY', name='Payroll Tax Hourly Equivalent')
# overhead_allocation_hourly = KeyFigure.objects.create(code='OVERHEAD_HRLY', name='Overhead Allocation Hourly')

# ── 2. PlanningLayout & Year‐Scoped Layouts ─────────────────────────────────

from .models_layout import *



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
        # grab the one global list of 12 periods, ordered Jan→Dec
        from bps.models.models import Period
        qs = Period.objects.order_by('order')
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

from .models_workflow import *


# ── 5. Fact & EAV (as before) ───────────────────────────────────────────────

class DataRequest(TimestampModel):
    ACTION_CHOICES = [
        ('DELTA',     'Delta'),
        ('OVERWRITE', 'Overwrite'),
        ('RESET',     'Reset to zero'),
        ('SUMMARY','Final summary'),     # ← new
    ]    
    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    session     = models.ForeignKey(PlanningSession, on_delete=models.CASCADE,
                                    related_name='requests')
    description = models.CharField(max_length=200, blank=True)
    action_type = models.CharField(max_length=20,choices=ACTION_CHOICES,default='DELTA',
        help_text="Delta: add on top of existing; Overwrite: replace; Reset: zero-out then write",
    )    
    is_summary  = models.BooleanField(default=False,help_text="True if this request holds the final, rolled-up facts")    

    # … store all current fact values → dict on create
    # before_snapshot = models.JSONField()

    def __str__(self): return f"{self.session} - {self.description or self.id}"


class PlanningFact(models.Model):
    """
    Core Models (EAV-style with fixed dimension FK)
    One “row” of plan data for a given DataRequest + Period.
    """
    request     = models.ForeignKey(DataRequest, on_delete=models.PROTECT)    # move to ReqeustLogs
    session     = models.ForeignKey(PlanningSession, on_delete=models.CASCADE)
    version     = models.ForeignKey(Version, on_delete=models.PROTECT)

    year        = models.ForeignKey(Year, on_delete=models.PROTECT)
    period      = models.ForeignKey(Period, on_delete=models.PROTECT)
    
    org_unit    = models.ForeignKey(OrgUnit, on_delete=models.PROTECT)

    service   = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT)
    account   = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT)

    # Optional domain-specific dimensions
    extra_dimensions_json = models.JSONField(default=dict, help_text="Mapping of extra dimension name → selected dimension key: e.g. {'Position':123, 'SkillGroup':'Developer'}")

    # Key figure
    # key_figure  = models.CharField(max_length=100)  
    key_figure  = models.ForeignKey(KeyFigure, on_delete=models.PROTECT)
    value       = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    uom         = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='+', null=True)   # allows multi-currency
    ref_value   = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    ref_uom     = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='+', null=True)

    class Meta:
        # unique_together = ('version', 'year', 'period', 'org_unit', 'service', 'account', 'key_figure', 'extra_dimensions_json')
        indexes = [
            models.Index(fields=['session','period']),
            models.Index(fields=['session','org_unit','period']),
            models.Index(fields=['key_figure']),
        ]
    def __str__(self):
        return f"{self.key_figure}={self.value} | {self.service} | {self.period} | {self.org_unit}"        

    def get_value_in(self, target_uom_code):
        """
        Return self.value converted into the unit target_uom_code.
        """
        if not self.uom:
            return None
        if self.uom.code == target_uom_code:
            return self.value
        to_uom = UnitOfMeasure.objects.get(code=target_uom_code, is_base=True)
        rate  = ConversionRate.objects.get(
            from_uom=self.uom,
            to_uom=to_uom
        ).factor
        return round(self.value * rate, 2)

# ── 6. Pivoted Planning Fact View ───────────────────────────────────────────
from .models_view import *  

class PlanningFactDimension(models.Model):
    fact       = models.ForeignKey(PlanningFact, on_delete=models.CASCADE, related_name="fact_dimensions")
    dimension  = models.ForeignKey(PlanningLayoutDimension, on_delete=models.PROTECT)
    value_id   = models.PositiveIntegerField(help_text="PK of the chosen dimension value")


class DataRequestLog(TimestampModel):
    """A log of every change made to a planning fact."""
    # The batch or transaction this change belongs to
    request     = models.ForeignKey(DataRequest, on_delete=models.CASCADE, related_name='log_entries')
    
    # A link to the specific fact record that was changed
    fact        = models.ForeignKey(PlanningFact, on_delete=models.CASCADE)

    # The actual change details
    old_value   = models.DecimalField(max_digits=18, decimal_places=2)
    new_value   = models.DecimalField(max_digits=18, decimal_places=2)
    
    def __str__(self):
        return f"{self.fact}: {self.old_value} → {self.new_value}"


class PlanningFunction(models.Model):
    FUNCTION_CHOICES = [
        ('COPY', 'Copy'),
        ('DISTRIBUTE', 'Distribute'),
        ('CURRENCY_CONVERT', 'Currency Convert'),  
        ('REPOST',     'Re-Post'),   
        ('RESET_SLICE',     'Reset Slice'),    
    ]
    layout      = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE)
    name        = models.CharField(max_length=50)
    function_type = models.CharField(choices=FUNCTION_CHOICES, max_length=20)
    parameters   = models.JSONField(
        default=dict,
        help_text="""
            COPY: { "from_version": <vid>, "to_version": <vid>, "year":<y>, "period":"01" }  
            DISTRIBUTE: { "by":"OrgUnit", "reference_data":"2024 Actuals" }  
            CURRENCY_CONVERT: { "target_uom":"USD" }
            REPOST:           {}                # no params
            RESET_SLICE:      { "filters": { "<field>": <value>, … } }
        """
    )
    def execute(self, session):
        """
        Dispatch to the correct implementation.
        """
        if self.function_type == 'COPY':
            return self._copy_data(session)
        if self.function_type == 'DISTRIBUTE':
            return self._distribute(session)
        if self.function_type == 'REPOST':
            return self._repost(session)        
        if self.function_type == 'CURRENCY_CONVERT':
            return self._currency_convert(session)
        if self.function_type == 'RESET_SLICE':
            return self._reset_slice(session)

        # Unknown type
        return 0
        
    def _copy_data(self, session: PlanningSession) -> int:
        """
        Copy all facts from this session to a new version within same layout/year.
        """
        params = self.parameters
        src_version = session.layout_year.version
        tgt_version = get_object_or_404(Version, pk=params['to_version'])
        # find or create the target layout-year & session
        tgt_ly, _ = PlanningLayoutYear.objects.get_or_create(
            layout=session.layout_year.layout,
            year=session.layout_year.year,
            version=tgt_version,
        )
        tgt_sess, _ = PlanningSession.objects.get_or_create(
            layout_year=tgt_ly,
            org_unit=session.org_unit,
        )
        # create a new DataRequest to hold the copied facts
        new_req = DataRequest.objects.create(
            session=tgt_sess,
            description=f"Copy from v{src_version.code}"
        )

        # bulk copy
        new_facts = []
        for fact in PlanningFact.objects.filter(session=session).iterator():
            new_facts.append(PlanningFact(
                request    = new_req,
                session    = tgt_sess,
                version    = tgt_version,
                year       = fact.year,
                period     = fact.period,
                org_unit   = fact.org_unit,
                service    = fact.service,
                account    = fact.account,
                extra_dimensions_json= fact.extra_dimensions_json,
                key_figure = fact.key_figure,
                value      = fact.value,
                uom        = fact.uom,
                ref_value  = fact.ref_value,
                ref_uom    = fact.ref_uom,
            ))
        PlanningFact.objects.bulk_create(new_facts)
        return len(new_facts)

    def _distribute(self, session: PlanningSession) -> int:
        """
        Distribute top-level reference total down into each fact by proportion.
        """
        by     = self.parameters['by']                # e.g. "org_unit"
        ref_nm = self.parameters['reference_data']    # e.g. "2024 Actuals"
        ref    = get_object_or_404(ReferenceData, name=ref_nm)

        total = ref.fetch_reference_fact(**{by: None})['value__sum'] or 0
        if total == 0:
            return 0

        updated = 0
        with transaction.atomic():
            for fact in PlanningFact.objects.filter(session=session):
                proportion = fact.value / total
                fact.value = proportion * total
                fact.save(update_fields=['value'])
                updated += 1

        return updated

    def _currency_convert(self, session: PlanningSession) -> int:
        """
        Revalue all facts in this session to a new UoM using ConversionRate.
        """
        tgt_code = self.parameters['target_uom']
        tgt_uom  = get_object_or_404(UnitOfMeasure, code=tgt_code)
        conv_map = {
            (c.from_uom_id, c.to_uom_id): c.factor
            for c in ConversionRate.objects.filter(to_uom=tgt_uom)
        }

        updated = 0
        with transaction.atomic():
            for fact in PlanningFact.objects.filter(session=session):
                key = (fact.uom_id, tgt_uom.id)
                if key not in conv_map:
                    continue
                fact.value = round(fact.value * conv_map[key], 4)
                fact.uom   = tgt_uom
                fact.save(update_fields=['value','uom'])
                updated += 1

        return updated

    def _repost(self, session: PlanningSession) -> int:
        """
        Clone the last DataRequest + its facts, so you can "repost" identical data.
        """
        last_dr = session.requests.order_by('-created_at').first()
        if not last_dr:
            return 0

        new_dr = DataRequest.objects.create(
            session     = session,
            description = f"Re-Post of {last_dr.id}",
            created_by  = last_dr.created_by,
        )

        created = 0
        with transaction.atomic():
            for fact in PlanningFact.objects.filter(request=last_dr):
                fact.pk      = None
                fact.request = new_dr
                fact.save()
                created += 1

        return created

    def _reset_slice(self, session: PlanningSession) -> int:
        """
        Zero-out all facts in this session matching the given filters.
        parameters = { "filters": {"org_unit_id": 5, "service_id": null, … } }
        """
        filters = self.parameters.get('filters', {})
        qs = PlanningFact.objects.filter(session=session, **filters)
        # zero both plan & reference values
        updated = qs.update(value=0, ref_value=0)
        return updated



class ReferenceData(models.Model):
    """
    Example:
    [Year=2025]?.[Revenue] = REF('2024 Actuals', OrgUnit=$OrgUnit)?.[Revenue] * (1 + INFLATION)
    """
    name = models.CharField(max_length=100)
    source_version = models.ForeignKey('Version', on_delete=models.CASCADE)
    source_year = models.ForeignKey('Year', on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    
    def fetch_reference_fact(self, **filters):
        return PlanningFact.objects.filter(
            session__layout_year__version=self.source_version,
            session__layout_year__year=self.source_year,
            **filters
        ).aggregate(Sum('value'))

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
    name = models.CharField(max_length=100)
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE, related_name='subformulas')
    expression = models.TextField(
        help_text="Expression using other constants/sub-formulas, e.g. [Year=2025]?.[Qty] * TAX_RATE"
    )

    class Meta:
        unique_together = ('layout', 'name')

    def __str__(self):
        return f"{self.name} ({self.layout})"


# class Formula(models.Model):
#     """
#     A full formula. loop_dimension tells Executor which dimension to iterate.
#     Expression syntax:  [Dim=val,…]?.[Key] = <arithmetic with [..]?.[..], $SUB, CONSTANT>
#     """
#     name = models.CharField(max_length=100)
#     layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE, related_name='formulas')
#     loop_dimension = models.ForeignKey(
#         ContentType,
#         on_delete=models.CASCADE,
#         help_text="InfoObject (e.g. Product) to loop over"
#     )
#     expression = models.TextField(
#         help_text="e.g. [OrgUnit=12,Product=$LOOP]?.[amount] = [..]?.[quantity] * $RATE"
#     )

#     class Meta:
#         unique_together = ('layout', 'name')

#     def __str__(self):
#         return f"{self.name} ({self.layout})"

class Formula(models.Model):
    """
    Example:
    FOREACH OrgUnit, Product:
        [Year=2025,OrgUnit=$OrgUnit,Product=$Product]?.[Revenue] =
            IF EXISTS([Year=2024,OrgUnit=$OrgUnit,Product=$Product]?.[ActualRevenue]) THEN
            [Year=2024,OrgUnit=$OrgUnit,Product=$Product]?.[ActualRevenue] * (1 + GROWTH_RATE)
            ELSE
            DEFAULT_REVENUE
    """
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    expression = models.TextField(help_text="Supports conditional logic, loops, and aggregation.")
    dimensions = models.ManyToManyField(ContentType, help_text="Multiple dimensions for looping")
    reference_version = models.ForeignKey('Version', null=True, blank=True, on_delete=models.SET_NULL)
    reference_year = models.ForeignKey('Year', null=True, blank=True, on_delete=models.SET_NULL)
    
    def __str__(self):
        return f"{self.name} ({self.layout})"
    
class FormulaRun(models.Model):
    """
    Audit of a single formula execution.
    """
    formula   = models.ForeignKey(Formula, on_delete=models.CASCADE)
    run_at    = models.DateTimeField(auto_now_add=True)
    preview   = models.BooleanField(default=False)
    run_by    = models.ForeignKey(settings.AUTH_USER_MODEL,
                                  null=True, on_delete=models.SET_NULL)

    def __str__(self): return f"Run #{self.pk} of {self.formula.name} @ {self.run_at}"


class FormulaRunEntry(models.Model):
    """
    One “cell” change by a FormulaRun.
    """
    run        = models.ForeignKey(FormulaRun, related_name='entries', on_delete=models.CASCADE)
    record     = models.ForeignKey('PlanningFact', on_delete=models.CASCADE)
    key        = models.CharField(max_length=100)       # e.g. 'amount' or 'other_key'
    old_value  = models.DecimalField(max_digits=18, decimal_places=6)
    new_value  = models.DecimalField(max_digits=18, decimal_places=6)

    def __str__(self): return f"{self.record} :: {self.key}: {self.old_value} → {self.new_value}"
    
        