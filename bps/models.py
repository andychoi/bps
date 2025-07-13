# bps/models.py

from uuid import uuid4
from django.db import models
from django.db.models import Sum
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from treebeard.mp_tree import MP_Node
# from django.contrib.postgres.fields import JSONField

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
    
# ── 1. InfoObject Base & Dimension Models ─────────────────────────────────

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
    pass

class Version(InfoObject):
    """
    A global dimension (e.g. 'Draft', 'Final', 'Plan v1', 'Plan v2').
    Used to isolate concurrent planning streams.
    """
    pass

class OrgUnit(MP_Node, InfoObject):
    head_user      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        help_text="OrgUnit lead who must draft and approve"
    )
    # parent         = models.ForeignKey(
    #     'self',
    #     on_delete=models.SET_NULL, null=True, blank=True,
    #     related_name='children'
    # )
    cc_code    = models.CharField(max_length=10, blank=True)    # SAP cost center code
    node_order_by = ['order', 'code']  # controls sibling ordering

class Account(InfoObject):
    pass

class Service(InfoObject):
    category         = models.CharField(max_length=50)    # e.g. Platform, Security
    subcategory      = models.CharField(max_length=50)    # e.g. Directory Services
    related_services = models.ManyToManyField('self', blank=True)
    CRITICALITY_CHOICES = [('H','High'),('M','Medium'),('L','Low')]
    criticality      = models.CharField(max_length=1, choices=CRITICALITY_CHOICES)
    sla_response     = models.DurationField(help_text="e.g. PT2H for 2 hours")
    sla_resolution   = models.DurationField(help_text="e.g. PT4H for 4 hours")
    availability     = models.DecimalField(max_digits=5, decimal_places=3,
                                           help_text="e.g. 99.900")
    SUPPORT_HOUR_CHOICES = [
        ('24x7','24×7'),
        ('9x5','9×5 Mon–Fri'),
        ('custom','Custom')
    ]
    support_hours    = models.CharField(max_length=10,
                                        choices=SUPPORT_HOUR_CHOICES)
    orgunit      = models.ForeignKey('OrgUnit',
                                         on_delete=models.SET_NULL,
                                         null=True, blank=True)
    owner            = models.ForeignKey(settings.AUTH_USER_MODEL,
                                         on_delete=models.SET_NULL,
                                         null=True, blank=True)
    is_active        = models.BooleanField(default=True)

    class Meta:
        ordering = ['category','subcategory','code']

    def __str__(self):
        return f"{self.code} – {self.name}"
    
class CostCenter(InfoObject):
    pass

class InternalOrder(InfoObject):
    cc_code    = models.CharField(max_length=10, blank=True)    # SAP cost center code


class Position(InfoObject):
    # Override parent code to remove unique constraint
    code        = models.CharField(max_length=20)
    year        = models.ForeignKey(Year, on_delete=models.CASCADE)
    skill_group = models.CharField(max_length=50)
    level       = models.CharField(max_length=20)      # e.g. Junior/Mid/Senior
    fte         = models.FloatField(default=1.0)        # FTE equivalent
    is_open     = models.BooleanField(default=False)    # open vs. filled

    class Meta(InfoObject.Meta):
        unique_together = ('year', 'code')
        ordering = ['year__code', 'order', 'code']

    def __str__(self):
        status = 'Open' if self.is_open else 'Filled'
        return f"[{self.year.code}] {self.code} ({self.skill_group}/{self.level}) – {status}"
        

class CBU(InfoObject):
    """Client Business Unit (inherits InfoObject)"""
    group       = models.CharField(max_length=50, blank=True)  # e.g. industry vertical
    TIER_CHOICES = [('1','Tier-1'),('2','Tier-2'),('3','Tier-3')]
    tier        = models.CharField(max_length=1, choices=TIER_CHOICES)
    sla_profile = models.ForeignKey('SLAProfile', on_delete=models.SET_NULL,
                                    null=True, blank=True)
    region      = models.CharField(max_length=50, blank=True)
    is_active   = models.BooleanField(default=True)

    node_order_by = ['cbu_code']

    def __str__(self):
        return f"{self.code} – {self.name}"


class RateCard(models.Model):
    """
    Contractor/MSP rate and efficiency planning, scoped by Year.
    """
    VENDOR_CHOICES = [('CON','Contractor'), ('MSP','MSP')]

    year              = models.ForeignKey(Year, on_delete=models.CASCADE)
    skill_group       = models.CharField(max_length=50)
    vendor_type       = models.CharField(max_length=20, choices=VENDOR_CHOICES)
    country           = models.CharField(max_length=50)
    efficiency_factor = models.DecimalField(max_digits=5, decimal_places=2,
                                            help_text="0.00–1.00")
    hourly_rate       = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('year','skill_group','vendor_type','country')
        ordering = ['year__code','skill_group','vendor_type','country']

    def __str__(self):
        return (f"[{self.year.code}] {self.vendor_type} | {self.skill_group} @ "
                f"{self.country}: {self.hourly_rate}$/h, eff {self.efficiency_factor}")

class UserMaster(models.Model):
    """
    Links your custom user profile to OrgUnit & CostCenter.
    """
    user      = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    org_unit  = models.ForeignKey(OrgUnit, on_delete=models.SET_NULL, null=True)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username
    
class SLAProfile(models.Model):
    name           = models.CharField(max_length=50, unique=True)
    response_time  = models.DurationField()
    resolution_time= models.DurationField()
    availability   = models.DecimalField(max_digits=5, decimal_places=3)
    description    = models.TextField(blank=True)

    def __str__(self):
        return self.name
    
class KeyFigure(models.Model):
    """ “PlanAmount”, “ActualQuantity”, “FTE”, “Utilization%”, etc.
    """
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    is_percent = models.BooleanField(default=False)
    default_uom = models.ForeignKey(UnitOfMeasure, null=True, on_delete=models.SET_NULL)

# ── 2. PlanningLayout & Year‐Scoped Layouts ─────────────────────────────────

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

class PlanningDimension(models.Model):
    """ Specifies what dimensions are visible, editable, filtered.
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

class PlanningKeyFigure(models.Model):
    """ Key figures used in the layout: amount, quantity, derived ones.
    """
    layout = models.ForeignKey(PlanningLayout, related_name="key_figures", on_delete=models.CASCADE)
    code = models.CharField(max_length=100)  # e.g. 'amount', 'quantity', 'cost_per_mm'
    label = models.CharField(max_length=100)
    is_editable = models.BooleanField(default=True)
    is_computed = models.BooleanField(default=False)
    formula = models.TextField(blank=True)  # e.g. 'amount = quantity * rate'

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
        FEEDBACK  = 'B','Return Back'
        COMPLETED = 'C','Completed'
        REVIEW    = 'R','Review'
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
    Core Models (EAV-style with fixed dimension FK)
    One “row” of plan data for a given DataRequest + Period.
    """
    request     = models.ForeignKey(DataRequest, on_delete=models.PROTECT)
    session     = models.ForeignKey(PlanningSession, on_delete=models.CASCADE)
    version     = models.ForeignKey(Version, on_delete=models.PROTECT)

    year        = models.ForeignKey(Year, on_delete=models.PROTECT)
    period      = models.ForeignKey(Period, on_delete=models.PROTECT)
    
    org_unit    = models.ForeignKey(OrgUnit, on_delete=models.PROTECT)

    service   = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT)
    account   = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT)

    # Optional domain-specific dimensions
    driver_refs = models.JSONField(default=dict, help_text="e.g. {'Position':123, 'SkillGroup':'Developer'}")

    # Key figure
    # key_figure  = models.CharField(max_length=100)  
    key_figure  = models.ForeignKey(KeyFigure, on_delete=models.PROTECT)
    value       = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    uom         = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='+', null=True)   # allows multi-currency
    ref_value   = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    ref_uom     = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='+', null=True)

    class Meta:
        unique_together = ('request', 'version', 'year', 'period', 'org_unit', 'service', 'account', 'key_figure', 'driver_refs')
        indexes = [
            models.Index(fields=['year', 'version', 'org_unit']),
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
    
class PlanningFunction(models.Model):
    FUNCTION_CHOICES = [
        ('COPY', 'Copy'),
        ('DISTRIBUTE', 'Distribute'),
        ('CURRENCY_CONVERT', 'Currency Convert'),        
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
        if self.function_type == 'CURRENCY_CONVERT':
            return self._currency_convert(session)

    def _copy_data(self, session):
        """
        Copy facts from one version→another (or actual→plan).
        """
        from bps.models import PlanningFact
        src_vid = self.parameters['from_version']
        tgt_vid = self.parameters['to_version']
        year    = self.parameters.get('year')
        period  = self.parameters.get('period')
        src_facts = PlanningFact.objects.filter(
            session__layout_year__version_id=src_vid,
            session=session,
            year_id=year,
            period=period
        )
        created = 0
        for f in src_facts:
            f.pk = None  # clone
            f.request = None
            f.session.layout_year.version_id = tgt_vid
            f.save()
            created += 1
        return created

    def _distribute(self, session):
        """
        Top-down distribute session-level totals to row-dim values
        by reference data proportions.
        """
        from bps.models import PlanningFact, ReferenceData
        by = self.parameters['by']             # e.g. "OrgUnit"
        ref_name = self.parameters['reference_data']
        ref = ReferenceData.objects.get(name=ref_name)
        # for each period / keyfigure
        total = ref.fetch_reference_fact(**{by: None})['value__sum'] or 0
        if total == 0:
            return 0
        # determine proportions
        qs = PlanningFact.objects.filter(session=session)
        created = 0
        for f in qs:
            share = f.value / total
            f.value = share * total
            f.save()
            created += 1
        return created

    def _currency_convert(self, session):
        """
        Revalue all facts to a new UoM using ConversionRate table.
        """
        from bps.models import PlanningFact, ConversionRate, UnitOfMeasure
        tgt = self.parameters['target_uom']
        tgt_uom = UnitOfMeasure.objects.get(code=tgt)
        conv_map = {
          (c.from_uom_id, c.to_uom_id): c.factor
          for c in ConversionRate.objects.filter(to_uom=tgt_uom)
        }
        updated = 0
        for f in PlanningFact.objects.filter(session=session):
            key = (f.uom_id, tgt_uom.id)
            if key not in conv_map: continue
            f.value = round(f.value * conv_map[key], 4)
            f.uom = tgt_uom
            f.save()
            updated += 1
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
    
        