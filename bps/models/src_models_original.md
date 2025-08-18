# Python Project Summary: models

---

### `models.py`
```python
from uuid import uuid4
from django.db import models, transaction
from django.contrib.postgres.fields import JSONField
from django.shortcuts import get_object_or_404
from django.db.models import Sum
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from treebeard.mp_tree import MP_Node
class TimestampModel(models.Model):
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    class Meta: abstract = True
class UnitOfMeasure(models.Model):
    code        = models.CharField(max_length=10, unique=True)
    name        = models.CharField(max_length=50)
    is_base     = models.BooleanField(default=False,
                                      help_text="Target unit for conversion rates")
    def __str__(self):
        return self.code
class ConversionRate(models.Model):
    from_uom = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE, related_name='conv_from')
    to_uom   = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE, related_name='conv_to')
    factor   = models.DecimalField(max_digits=18, decimal_places=6,
                                   help_text="Multiply a from_uom value by this to get to_uom")
    class Meta:
        unique_together = ('from_uom','to_uom')
    def __str__(self):
        return f"1 {self.from_uom} → {self.factor} {self.to_uom}"
from .models_dimension import *
from .models_resource import *
class UserMaster(models.Model):
    user      = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True)
    def __str__(self):
        return self.user.get_full_name() or self.user.username
class KeyFigure(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    is_percent = models.BooleanField(default=False)
    default_uom = models.ForeignKey(UnitOfMeasure, null=True, on_delete=models.SET_NULL)
    display_decimals = models.PositiveSmallIntegerField(
        default=2,
        help_text="Number of decimal places to show for this key figure in grids and totals."
    )
    def __str__(self):
        return self.code
from .models_layout import *
from .models_period import *
from .models_workflow import *
class DataRequest(TimestampModel):
    ACTION_CHOICES = [
        ('DELTA',     'Delta'),
        ('OVERWRITE', 'Overwrite'),
        ('RESET',     'Reset to zero'),
        ('SUMMARY','Final summary'),
    ]
    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    session     = models.ForeignKey(PlanningSession, on_delete=models.CASCADE,
                                    related_name='requests')
    description = models.CharField(max_length=200, blank=True)
    action_type = models.CharField(max_length=20,choices=ACTION_CHOICES,default='DELTA',
        help_text="Delta: add on top of existing; Overwrite: replace; Reset: zero-out then write",
    )
    is_summary  = models.BooleanField(default=False,help_text="True if this request holds the final, rolled-up facts")
    def __str__(self): return f"{self.session} - {self.description or self.id}"
class PlanningFact(models.Model):
    request     = models.ForeignKey(DataRequest, on_delete=models.PROTECT)
    session     = models.ForeignKey(PlanningSession, on_delete=models.CASCADE)
    version     = models.ForeignKey(Version, on_delete=models.PROTECT)
    year        = models.ForeignKey(Year, on_delete=models.PROTECT)
    period      = models.ForeignKey(Period, on_delete=models.PROTECT, null=True, blank=True)
    org_unit    = models.ForeignKey(OrgUnit, on_delete=models.PROTECT)
    service   = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT)
    account   = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT)
    key_figure  = models.ForeignKey(KeyFigure, on_delete=models.PROTECT)
    value       = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    uom         = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='+', null=True)
    ref_value   = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    ref_uom     = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='+', null=True)
    class Meta:
        indexes = [
            models.Index(fields=['session','period']),
            models.Index(fields=['session','org_unit','period']),
            models.Index(fields=['key_figure']),
        ]
    def __str__(self):
        return f"{self.key_figure}={self.value} | {self.service} | {self.period} | {self.org_unit}"
    def get_value_in(self, target_uom_code):
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
from .models_view import *
from .models_extras import *
class PlanningFactDimension(models.Model):
    fact       = models.ForeignKey(PlanningFact, on_delete=models.CASCADE, related_name="fact_dimensions")
    dimension = models.ForeignKey(PlanningLayoutDimension, on_delete=models.PROTECT)
    value_id   = models.PositiveIntegerField(help_text="PK of the chosen dimension value")
    class Meta:
        unique_together = (("fact", "dimension"),)
        indexes = [
            models.Index(fields=["dimension","value_id"]),
        ]
class DataRequestLog(TimestampModel):
    request     = models.ForeignKey(DataRequest, on_delete=models.CASCADE, related_name='log_entries')
    fact        = models.ForeignKey(PlanningFact, on_delete=models.CASCADE)
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
        help_text=
    )
    def execute(self, session):
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
        return 0
    def _copy_data(self, session: PlanningSession) -> int:
        params = self.parameters
        src_version = session.layout_year.version
        tgt_version = get_object_or_404(Version, pk=params['to_version'])
        tgt_ly, _ = PlanningLayoutYear.objects.get_or_create(
            layout=session.layout_year.layout,
            year=session.layout_year.year,
            version=tgt_version,
        )
        tgt_sess, _ = PlanningSession.objects.get_or_create(
            layout_year=tgt_ly,
            org_unit=session.org_unit,
        )
        new_req = DataRequest.objects.create(
            session=tgt_sess,
            description=f"Copy from v{src_version.code}"
        )
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
        by     = self.parameters['by']
        ref_nm = self.parameters['reference_data']
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
        filters = self.parameters.get('filters', {})
        qs = PlanningFact.objects.filter(session=session, **filters)
        updated = qs.update(value=0, ref_value=0)
        return updated
class ReferenceData(models.Model):
    name = models.CharField(max_length=100)
    source_version = models.ForeignKey('Version', on_delete=models.CASCADE)
    source_year = models.ForeignKey('Year', on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    def fetch_reference_fact(self, **filters):
        return PlanningFact.objects.filter(
            session__scenario__layout_year__version=self.source_version,
            session__scenario__layout_year__year=self.source_year,
            **filters
        ).aggregate(Sum('value'))
class GlobalVariable(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    value = models.DecimalField(max_digits=18, decimal_places=6)
class Constant(models.Model):
    name  = models.CharField(max_length=100, unique=True)
    value = models.DecimalField(max_digits=18, decimal_places=6)
    def __str__(self):
        return f"{self.name} = {self.value}"
class SubFormula(models.Model):
    name = models.CharField(max_length=100)
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE, related_name='subformulas')
    expression = models.TextField(
        help_text="Expression using other constants/sub-formulas, e.g. [Year=2025]?.[Qty] * TAX_RATE"
    )
    class Meta:
        unique_together = ('layout', 'name')
    def __str__(self):
        return f"{self.name} ({self.layout})"
class Formula(models.Model):
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    expression = models.TextField(help_text="Supports conditional logic, loops, and aggregation.")
    dimensions = models.ManyToManyField(ContentType, help_text="Multiple dimensions for looping")
    reference_version = models.ForeignKey('Version', null=True, blank=True, on_delete=models.SET_NULL)
    reference_year = models.ForeignKey('Year', null=True, blank=True, on_delete=models.SET_NULL)
    def __str__(self):
        return f"{self.name} ({self.layout})"
class FormulaRun(models.Model):
    formula   = models.ForeignKey(Formula, on_delete=models.CASCADE)
    run_at    = models.DateTimeField(auto_now_add=True)
    preview   = models.BooleanField(default=False)
    run_by    = models.ForeignKey(settings.AUTH_USER_MODEL,
                                  null=True, on_delete=models.SET_NULL)
    def __str__(self): return f"Run
class FormulaRunEntry(models.Model):
    run        = models.ForeignKey(FormulaRun, related_name='entries', on_delete=models.CASCADE)
    record     = models.ForeignKey('PlanningFact', on_delete=models.CASCADE)
    key        = models.CharField(max_length=100)
    old_value  = models.DecimalField(max_digits=18, decimal_places=6)
    new_value  = models.DecimalField(max_digits=18, decimal_places=6)
    def __str__(self): return f"{self.record} :: {self.key}: {self.old_value} → {self.new_value}"
```

### `models_access.py`
```python
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import Q
from .models_dimension import OrgUnit
User = settings.AUTH_USER_MODEL
class OrgUnitAccess(models.Model):
    EXACT = "EXACT"
    SUBTREE = "SUBTREE"
    SCOPE_CHOICES = [(EXACT, "Exact"), (SUBTREE, "Subtree")]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ou_access")
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.CASCADE, related_name="user_access")
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default=SUBTREE)
    can_edit = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ("user", "org_unit", "scope")
    def __str__(self):
        return f"{self.user} → {self.org_unit} [{self.scope}]"
    def units_qs(self):
        base = OrgUnit.objects.filter(pk=self.org_unit_id)
        if self.scope == self.SUBTREE:
            return base.union(self.org_unit.get_descendants())
        return base
    @classmethod
    def scope_for_user(cls, user, *, include_delegations=True):
        qs = OrgUnit.objects.none()
        for access in cls.objects.filter(user=user).select_related("org_unit"):
            qs = qs.union(access.units_qs())
        if include_delegations:
            now = timezone.now()
            dels = Delegation.objects.filter(
                delegatee=user,
                active=True
            ).filter(
                Q(starts_at__isnull=True) | Q(starts_at__lte=now),
                Q(ends_at__isnull=True)   | Q(ends_at__gte=now),
            ).select_related("delegator")
            if dels.exists():
                delegator_ids = list(dels.values_list("delegator_id", flat=True))
                for access in cls.objects.filter(user_id__in=delegator_ids).select_related("org_unit"):
                    qs = qs.union(access.units_qs())
        return qs.distinct()
    @classmethod
    def can_edit_orgunit(cls, user, org_unit, *, include_delegations=True):
        anc_ids = list(org_unit.get_ancestors().values_list("id", flat=True)) + [org_unit.id]
        base = cls.objects.filter(user=user, can_edit=True).filter(
            Q(scope=cls.EXACT, org_unit_id=org_unit.id) |
            Q(scope=cls.SUBTREE, org_unit_id__in=anc_ids)
        )
        if base.exists():
            return True
        if include_delegations:
            now = timezone.now()
            delegator_ids = list(
                Delegation.objects.filter(
                    delegatee=user, active=True
                ).filter(
                    Q(starts_at__isnull=True) | Q(starts_at__lte=now),
                    Q(ends_at__isnull=True)   | Q(ends_at__gte=now),
                ).values_list("delegator_id", flat=True)
            )
            if delegator_ids:
                via_del = cls.objects.filter(user_id__in=delegator_ids, can_edit=True).filter(
                    Q(scope=cls.EXACT, org_unit_id=org_unit.id) |
                    Q(scope=cls.SUBTREE, org_unit_id__in=anc_ids)
                )
                if via_del.exists():
                    return True
        return False
class Delegation(models.Model):
    delegator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="delegations_out")
    delegatee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="delegations_in")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    note = models.CharField(max_length=200, blank=True)
    class Meta:
        unique_together = ("delegator", "delegatee")
    def is_active(self):
        now = timezone.now()
        if not self.active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True
    def __str__(self):
        return f"{self.delegator} → {self.delegatee}"
```

### `models_dimension.py`
```python
from django.conf import settings
from django.db import models, transaction
from treebeard.mp_tree import MP_Node
class InfoObject(models.Model):
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
    pass
class Version(InfoObject):
    is_public = models.BooleanField(default=True, help_text="Public versions are visible to everyone; private only to creator")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="For private versions, track the owner"
    )
    class Meta(InfoObject.Meta):
        ordering = ['order', 'code']
class OrgUnit(MP_Node, InfoObject):
    head_user      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bps_orgunits_headed',
        related_query_name='bps_orgunit_headed',
        help_text="OrgUnit lead who must draft and approve"
    )
    cc_code    = models.CharField(max_length=10, blank=True)
    node_order_by = ['order', 'code']
class CBU(InfoObject):
    group       = models.CharField(max_length=50, blank=True)
    TIER_CHOICES = [('1','Tier-1'),('2','Tier-2'),('3','Tier-3')]
    tier        = models.CharField(max_length=1, choices=TIER_CHOICES)
    region      = models.CharField(max_length=50, blank=True)
    is_active   = models.BooleanField(default=True)
    node_order_by = ['group', 'code']
    def __str__(self):
        return f"{self.code} - {self.name}"
class Account(InfoObject):
    pass
class Service(InfoObject):
    category         = models.CharField(max_length=50)
    subcategory      = models.CharField(max_length=50)
    related_services = models.ManyToManyField('self', blank=True)
    orgunit      = models.ForeignKey('OrgUnit',on_delete=models.SET_NULL,null=True, blank=True)
    is_active        = models.BooleanField(default=True)
    class Meta:
        ordering = ['category','subcategory','code']
    def __str__(self):
        return f"{self.code} – {self.name}"
class CostCenter(InfoObject):
    pass
class InternalOrder(InfoObject):
    cc_code    = models.CharField(max_length=10, blank=True)
class PriceType(InfoObject):
    pass
```

### `models_extras.py`
```python
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
class DimensionKey(models.Model):
    key = models.CharField(max_length=64, unique=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    def __str__(self):
        return self.key
class PlanningFactExtra(models.Model):
    fact = models.ForeignKey(
        "bps.PlanningFact",
        on_delete=models.CASCADE,
        related_name="extras",
        db_index=True,
    )
    key = models.ForeignKey(DimensionKey, on_delete=models.PROTECT, db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id    = models.PositiveIntegerField()
    value_obj    = GenericForeignKey("content_type", "object_id")
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["fact", "key"],
                name="uniq_fact_key",
            ),
            models.Index(fields=["key", "content_type", "object_id"], name="bps_factextra_ct_obj_idx",),
        ]
    def clean(self):
        if self.key_id and self.content_type_id:
            if self.key.content_type_id != self.content_type_id:
                raise ValidationError(
                    {"content_type": f"Key '{self.key.key}' must reference {self.key.content_type}."}
                )
```

### `models_function.py`
```python
from django.db import models, transaction
```

### `models_layout.py`
```python
from django.db import models, transaction
from django.contrib.contenttypes.models import ContentType
from .models_dimension import Year, Version, OrgUnit
SHORT_LABELS = {
    "orgunit": "OU",
    "service": "Srv",
    "internalorder": "IO",
    "position": "Pos",
    "skill": "Skill",
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
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    domain = models.CharField(max_length=100)
    default = models.BooleanField(default=False)
    def __str__(self):
        return self.code
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
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE, related_name='per_year')
    year   = models.ForeignKey(Year, on_delete=models.CASCADE)
    version= models.ForeignKey(Version, on_delete=models.CASCADE)
    org_units = models.ManyToManyField(OrgUnit, blank=True)
    header_dims = models.JSONField(default=dict, help_text="e.g. {'Company':3,'Region':'NA'}")
    class Meta:
        unique_together = ('layout','year','version')
    def __str__(self):
        return f"{self.layout.name} – {self.year.code} / {self.version.code}"
    def header_defaults(self):
        base = dict(self.header_dims or {})
        return base
    def header_pairs(self, *, use_short_labels=True, short_values=True, exclude=EXCLUDE_FROM_CONTEXT):
        pairs = []
        defaults = self.header_defaults()
        dims = self.layout.dimensions.filter(is_header=True).select_related("content_type").order_by("order")
        for dim in dims:
            ct = dim.content_type
            key = ct.model
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
class LayoutDimensionOverride(models.Model):
    layout_year      = models.ForeignKey(PlanningLayoutYear, related_name="dimension_overrides", on_delete=models.CASCADE)
    dimension = models.ForeignKey(PlanningLayoutDimension, related_name="overrides", on_delete=models.CASCADE)
    allowed_values   = models.JSONField(blank=True, default=list)
    filter_criteria  = models.JSONField(blank=True, default=dict)
    header_selection = models.PositiveIntegerField(null=True, blank=True)
    order_override   = models.PositiveSmallIntegerField(null=True, blank=True)
    class Meta:
        unique_together = ("layout_year", "dimension")
class PlanningKeyFigure(models.Model):
    layout        = models.ForeignKey(PlanningLayout, related_name="key_figures", on_delete=models.CASCADE)
    key_figure    = models.ForeignKey('bps.KeyFigure', on_delete=models.CASCADE)
    is_editable   = models.BooleanField(default=True)
    is_computed   = models.BooleanField(default=False)
    is_yearly     = models.BooleanField(default=False, help_text="If true, this key figure is planned at year level without periods for this layout.")
    formula       = models.TextField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    class Meta:
        ordering = ["display_order", "id"]
        unique_together = ("layout", "key_figure")
```

### `models_period.py`
```python
from django.db import models, transaction
class Period(models.Model):
    code   = models.CharField(max_length=2, unique=True)
    name   = models.CharField(max_length=10)
    order  = models.PositiveSmallIntegerField()
    def __str__(self):
        return self.name
class PeriodGrouping(models.Model):
    layout_year = models.ForeignKey('bps.PlanningLayoutYear', on_delete=models.CASCADE,
                                    related_name='period_groupings')
    months_per_bucket = models.PositiveSmallIntegerField(choices=[(1,'Monthly'),(3,'Quarterly'),(6,'Half-Year')])
    label_prefix = models.CharField(max_length=5, default='')
    class Meta:
        unique_together = ('layout_year','months_per_bucket')
    def buckets(self):
        months = list(Period.objects.order_by('order'))
        size = self.months_per_bucket
        buckets = []
        for i in range(0, 12, size):
            group = months[i:i+size]
            if size == 1:
                code = group[0].code
                name = group[0].name
            else:
                idx = (i // size) + 1
                code = f"{self.label_prefix}{idx}"
                name = code
            buckets.append({'code': code, 'name': name, 'periods': group})
        return buckets
```

### `models_resource.py`
```python
from django.db import models, transaction
from .models_dimension import *
class Skill(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    def __str__(self): return self.name
class RateCard(models.Model):
    RESOURCE_CHOICES = [('EMP', 'Employee'), ('CON','Contractor'), ('MSP','MSP')]
    year = models.ForeignKey('Year', on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT)
    level             = models.CharField(max_length=20)
    resource_type       = models.CharField(max_length=20, choices=RESOURCE_CHOICES)
    country           = models.CharField(max_length=50)
    efficiency_factor = models.DecimalField(default=1.00, max_digits=5, decimal_places=2,
                                            help_text="0.00-1.00")
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    class Meta:
        unique_together = ('year','skill','level','resource_type','country')
        ordering = ['skill','level','resource_type','country']
        verbose_name = "Rate Card Template"
        verbose_name_plural = "Rate Card Templates"
    def __str__(self):
        return (f"{self.resource_type} | {self.skill} ({self.level}) @ "
                f"{self.country}")
class Resource(models.Model):
    RESOURCE_TYPES = [
        ('EMP', 'Employee'),
        ('CON', 'Contractor'),
        ('MSP','MSP Staff'),
    ]
    unique_id         = models.CharField(max_length=100, unique=True)
    display_name      = models.CharField(max_length=255)
    resource_type     = models.CharField(max_length=3, choices=RESOURCE_TYPES)
    current_skill     = models.ForeignKey(Skill,  on_delete=models.SET_NULL, null=True)
    current_level     = models.CharField(max_length=20, blank=True, null=True)
    country           = models.CharField(max_length=50, blank=True)
    def __str__(self):
        return self.display_name
class Employee(Resource):
    employee_id       = models.CharField(max_length=20, unique=True)
    hire_date         = models.DateField()
    annual_salary     = models.DecimalField(max_digits=12, decimal_places=2)
class Vendor(models.Model):
    name = models.CharField(max_length=255, unique=True)
    vendor_type = models.CharField(max_length=20, choices=RateCard.RESOURCE_CHOICES[1:])
    def __str__(self):
        return self.name
class Contractor(Resource):
    vendor            = models.ForeignKey(Vendor, on_delete=models.PROTECT)
    contract_id       = models.CharField(max_length=50, unique=True)
    contract_start    = models.DateField()
    contract_end      = models.DateField()
class MSPStaff(Resource):
    pass
class Position(InfoObject):
    code        = models.CharField(max_length=20)
    year        = models.ForeignKey(Year, on_delete=models.CASCADE)
    skill       = models.ForeignKey(Skill, on_delete=models.PROTECT)
    level       = models.CharField(max_length=20)
    orgunit     = models.ForeignKey(OrgUnit, on_delete=models.PROTECT, null=True, blank=True)
    fte         = models.FloatField(default=1.0)
    is_open     = models.BooleanField(default=False)
    intended_resource_type = models.CharField(
        max_length=20,
        choices=RateCard.RESOURCE_CHOICES,
        default='EMP',
        help_text="Intended category for this position (Employee, Contractor, MSP). Used for budgeting if 'is_open' is True."
    )
    filled_by_resource = models.ForeignKey(Resource, on_delete=models.SET_NULL, null=True, blank=True,
                                            help_text="The specific person filling this position.")
    class Meta(InfoObject.Meta):
        unique_together = ('year', 'code')
        ordering = ['year__code', 'order', 'code']
    def __str__(self):
        status = 'Open' if self.is_open else 'Filled'
        return f"[{self.year.code}] {self.code} ({self.skill}/{self.level}) - {status}"
```

### `models_view.py`
```python
from django.db import models
class PivotedPlanningFact(models.Model):
    version = models.CharField(max_length=50)
    year = models.IntegerField()
    org_unit = models.CharField(max_length=50)
    service = models.CharField(max_length=50)
    account = models.CharField(max_length=50)
    extra_dimensions_json = models.JSONField()
    key_figure = models.CharField(max_length=50)
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
    total_value = models.FloatField(null=True, blank=True)
    total_reference = models.FloatField(null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'pivoted_planningfact'
```

### `models_workflow.py`
```python
from django.db import models, transaction
from django.conf import settings
from .models_dimension import OrgUnit
class PlanningStage(models.Model):
    code       = models.CharField(max_length=20, unique=True)
    name       = models.CharField(max_length=100)
    order      = models.PositiveSmallIntegerField(
                   help_text="Determines execution order. Lower=earlier.")
    can_run_in_parallel = models.BooleanField(
                   default=False,
                   help_text="If True, this step may execute alongside others.")
    class Meta:
        ordering = ['order']
    def __str__(self):
        return f"{self.order}: {self.name}"
class PlanningScenario(models.Model):
    code        = models.CharField(max_length=50, unique=True)
    name        = models.CharField(max_length=200)
    layout_year = models.ForeignKey('bps.PlanningLayoutYear', on_delete=models.CASCADE)
    org_units   = models.ManyToManyField(OrgUnit, through='ScenarioOrgUnit')
    stages      = models.ManyToManyField(PlanningStage, through='ScenarioStage')
    functions   = models.ManyToManyField('bps.PlanningFunction', through='ScenarioFunction')
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
class ScenarioOrgUnit(models.Model):
    scenario   = models.ForeignKey(PlanningScenario, on_delete=models.CASCADE)
    org_unit   = models.ForeignKey(OrgUnit, on_delete=models.CASCADE)
    order      = models.PositiveSmallIntegerField()
    class Meta:
        unique_together = ('scenario','org_unit')
        ordering = ['order']
class ScenarioStage(models.Model):
    scenario = models.ForeignKey(PlanningScenario, on_delete=models.CASCADE)
    stage    = models.ForeignKey(PlanningStage, on_delete=models.CASCADE)
    order    = models.PositiveSmallIntegerField()
    class Meta:
        unique_together = ('scenario','stage')
        ordering = ['order']
class ScenarioStep(models.Model):
    scenario    = models.ForeignKey(PlanningScenario, on_delete=models.CASCADE)
    stage       = models.ForeignKey(PlanningStage, on_delete=models.CASCADE)
    layout      = models.ForeignKey('bps.PlanningLayout', on_delete=models.PROTECT)
    order       = models.PositiveSmallIntegerField()
    class Meta:
        unique_together = ('scenario','stage', 'layout')
        ordering = ['order']
class ScenarioFunction(models.Model):
    scenario  = models.ForeignKey(PlanningScenario, on_delete=models.CASCADE)
    function  = models.ForeignKey('bps.PlanningFunction', on_delete=models.CASCADE)
    order     = models.PositiveSmallIntegerField()
    class Meta:
        unique_together = ('scenario','function')
        ordering = ['order']
class PlanningSession(models.Model):
    scenario      = models.ForeignKey(PlanningScenario, on_delete=models.CASCADE, related_name='sessions')
    org_unit    = models.ForeignKey(OrgUnit, on_delete=models.CASCADE,
                                    help_text="Owner of this session")
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
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
    current_step = models.ForeignKey(ScenarioStep, on_delete=models.PROTECT)
    class Meta:
        unique_together = ('scenario','org_unit')
    def __str__(self):
        return f"{self.org_unit.name} - {self.layout_year}"
    @property
    def layout_year(self):
        return self.scenario.layout_year
    def can_edit(self, user):
        if self.status == self.Status.DRAFT and user == self.org_unit.head_user:
            return True
        return False
    def complete(self, user):
        if user == self.org_unit.head_user:
            self.status = self.Status.COMPLETED
            self.save()
    def freeze(self, user):
        self.status    = self.Status.FROZEN
        self.frozen_by = user
        self.frozen_at = models.functions.Now()
        self.save()
```

