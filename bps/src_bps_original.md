# Python Project Summary: bps

---

### `apps.py`
```python
from django.apps import AppConfig
class BpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bps"
```

### `autocomplete.py`
```python
from dal_select2.views import Select2QuerySetView
from dal_select2.widgets import ModelSelect2, ModelSelect2Multiple
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from .models import (
    PlanningLayout,
    Year,
    Period,
    OrgUnit,
    Account,
    InternalOrder,
    CBU,
    UnitOfMeasure,
    PlanningLayoutYear,
)
class LayoutAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = PlanningLayout.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs
class ContentTypeAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = ContentType.objects.all()
        if self.q:
            qs = qs.filter(
                Q(model__icontains=self.q) |
                Q(app_label__icontains=self.q)
            )
        return qs
class YearAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = Year.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs
class PeriodAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = Period.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs
class OrgUnitAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = OrgUnit.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs
class AccountAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = Account.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs
class InternalOrderAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = InternalOrder.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs
class CBUAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = CBU.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs
class PriceTypeAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = PriceType.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs
class UnitOfMeasureAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = UnitOfMeasure.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs
class LayoutYearAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = PlanningLayoutYear.objects.select_related('layout', 'year', 'version')
        if self.q:
            qs = qs.filter(
                Q(layout__name__icontains=self.q) |
                Q(year__code__icontains=self.q) |
                Q(version__code__icontains=self.q)
            )
        return qs
```

### `forms.py`
```python
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
from dal_select2.widgets import ModelSelect2
from django.contrib.contenttypes.models import ContentType
from .models import (
    Constant, SubFormula, Formula, PlanningFunction, ReferenceData,
    PlanningLayoutYear, PeriodGrouping, PlanningSession,
    DataRequest, PlanningFact, Year, Version, OrgUnit
)
class FactForm(forms.ModelForm):
    class Meta:
        model = PlanningFact
        fields = [
            'service', 'account', 'driver_refs',
            'key_figure', 'value', 'uom',
            'ref_value', 'ref_uom'
        ]
        widgets = {
            'service': ModelSelect2(url='bps:service-autocomplete'),
            'account': ModelSelect2(url='bps:account-autocomplete'),
            'key_figure': ModelSelect2(url='bps:keyfigure-autocomplete'),
            'uom': ModelSelect2(url='bps:uom-autocomplete'),
            'ref_uom': ModelSelect2(url='bps:uom-autocomplete'),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Row(
                Column('service',   css_class='col-md-4'),
                Column('account',   css_class='col-md-4'),
                Column('driver_refs', css_class='col-md-4'),
            ),
            Row(
                Column('key_figure', css_class='col-md-4'),
                Column('value',      css_class='col-md-4'),
                Column('uom',        css_class='col-md-4'),
            ),
            Row(
                Column('ref_value', css_class='col-md-4'),
                Column('ref_uom',   css_class='col-md-4'),
            ),
            Submit('save', 'Save Fact')
        )
class ConstantForm(forms.ModelForm):
    class Meta:
        model = Constant
        fields = ['name', 'value']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'name', 'value',
            Submit('save','Save Constant')
        )
class SubFormulaForm(forms.ModelForm):
    class Meta:
        model = SubFormula
        fields = ['layout', 'name', 'expression']
        widgets = {
            'layout': ModelSelect2(url='bps:layout-autocomplete'),
            'expression': forms.Textarea(attrs={'rows':3})
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Row(Column('layout', css_class='col-md-4'),
                Column('name', css_class='col-md-4')),
            'expression',
            Submit('save', 'Save Sub-Formula')
        )
class FormulaForm(forms.ModelForm):
    loop_dimension = forms.ModelChoiceField(
        queryset=ContentType.objects.all(),
        widget=ModelSelect2(url='bps:contenttype-autocomplete')
    )
    class Meta:
        model = Formula
        fields = ['layout', 'name', 'loop_dimension', 'expression']
        widgets = {
            'layout': ModelSelect2(url='bps:layout-autocomplete'),
            'expression': forms.Textarea(attrs={'rows':4}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Row(Column('layout', css_class='col-md-4'),
                Column('name', css_class='col-md-4')),
            'loop_dimension',
            'expression',
            Submit('save', 'Save Formula')
        )
class PlanningFunctionForm(forms.ModelForm):
    class Meta:
        model = PlanningFunction
        fields = ['layout', 'name', 'function_type', 'parameters']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Row(
                Column('layout', css_class='col-md-4'),
                Column('name', css_class='col-md-4'),
                Column('function_type', css_class='col-md-4'),
            ),
            'parameters',
            Submit('save','Save Function')
        )
class ReferenceDataForm(forms.ModelForm):
    class Meta:
        model = ReferenceData
        fields = ['name', 'source_version', 'source_year', 'description']
        widgets = {
            'source_version': ModelSelect2(url='bps:version-autocomplete'),
            'source_year'   : ModelSelect2(url='bps:year-autocomplete'),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-4'),
                Column('source_version', css_class='col-md-4'),
                Column('source_year', css_class='col-md-4'),
            ),
            'description',
            Submit('save','Save Reference')
        )
class PlanningSessionForm(forms.ModelForm):
    class Meta:
        model = PlanningSession
        fields = ['layout_year','org_unit']
        widgets = {
           'layout_year': ModelSelect2(url='layoutyear-autocomplete'),
           'org_unit'   : ModelSelect2(url='orgunit-autocomplete'),
        }
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
          Row(Column('layout_year', css_class='col-md-6'),
              Column('org_unit',    css_class='col-md-6')),
          Submit('start','Start Planning')
        )
class PeriodSelector(forms.Form):
    grouping = forms.ModelChoiceField(
        queryset=PeriodGrouping.objects.none(),
        label="Period Grouping"
    )
    def __init__(self, *a, session:PlanningSession, **kw):
        super().__init__(*a,**kw)
        qs = session.layout_year.period_groupings.all()
        self.fields['grouping'].queryset = qs
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'grouping',
            Submit('apply','Apply')
        )
```

### `formula_executor.py`
```python
import re, ast, operator, itertools
from decimal import Decimal
from typing import Any, Dict, List
from django.apps import apps
from django.db.models import Sum, Avg, Min, Max, Q
from bps.models import (
    PlanningFact, Formula, Constant, SubFormula,
    FormulaRun, FormulaRunEntry, ReferenceData
)
_AGG_FUNCS = {
    'SUM': Sum, 'AVG': Avg, 'MIN': Min, 'MAX': Max
}
class FormulaExecutor:
    _re_refdata = re.compile(r"REF\('([^']+)'\s*,\s*([^\)]+)\)")
    def __init__(self, formula: Formula, session, period: str, preview: bool=False):
        self.formula = formula
        self.session = session
        self.period  = period
        self.preview = preview
        self.run     = None
        self._re_subf = re.compile(r"\$(\w+)")
        self._re_const= re.compile(r"\b[A-Z_][A-Z0-9_]*\b")
        self._re_ref  = re.compile(r"\[(.*?)\]\.\?\[(.*?)\]")
        self.dim_cts = list(formula.dimensions.all())
    def execute(self):
        self.run = FormulaRun.objects.create(formula=self.formula,
                                             preview=self.preview)
        loops = []
        for ct in self.dim_cts:
            Model = ct.model_class()
            loops.append([(ct, obj) for obj in Model.objects.all()])
        for combo in itertools.product(*loops):
            dims_map = {ct.model: inst for ct,inst in combo}
            self._apply(dims_map)
        return self.run.entries.all()
    def _apply(self, dims_map: Dict[str,Any]):
        expr = self.formula.expression
        expr = self._expand_subformulas(expr)
        expr = self._replace_reference_data(expr, dims_map)
        expr = self._replace_constants(expr)
        expr = self._rewrite_conditionals(expr)
        tgt, src = map(str.strip, expr.split('=',1))
        key_fig, tgt_dims = self._parse_ref(tgt, dims_map)
        src_eval = self._replace_refs_with_values(src, dims_map)
        result = self._safe_eval(src_eval, dims_map)
        rec = self._get_record(key_fig, tgt_dims, create=not self.preview)
        old = getattr(rec, key_fig, 0)
        if not self.preview:
            setattr(rec, key_fig, result)
            rec.save()
        FormulaRunEntry.objects.create(
            run=self.run, record=rec,
            key=key_fig, old_value=old, new_value=result
        )
    def _expand_subformulas(self, expr: str) -> str:
        def repl(m):
            sub = SubFormula.objects.get(name=m.group(1),
                                         layout=self.formula.layout)
            return f"({self._expand_subformulas(sub.expression)})"
        return self._re_subf.sub(repl, expr)
    def _replace_constants(self, expr: str) -> str:
        def repl(m):
            val = Constant.objects.get(name=m.group(0)).value
            return str(val)
        return self._re_const.sub(repl, expr)
    def _rewrite_conditionals(self, expr: str) -> str:
        expr = re.sub(r"\bIF\(", "__if__(", expr)
        def case_repl(m):
            body = m.group(1)
            return f"__case__([{body}])"
        expr = re.sub(r"\bCASE\s+(.*?)\s+END", case_repl, expr, flags=re.S)
        return expr
    def __if__(self, cond, tval, fval):
        return tval if cond else fval
    def __case__(self, arms: List[str]):
        for arm in arms:
            if arm.strip().upper().startswith("WHEN"):
                _, cond, _, val = re.split(r"\s+", arm, maxsplit=3)
                if self._safe_eval(cond, {}):
                    return self._safe_eval(val, {})
            elif arm.strip().upper().startswith("ELSE"):
                return self._safe_eval(arm.split(None,1)[1], {})
        return Decimal('0')
    def _parse_ref(self, token: str, dims_map: Dict[str,Any]):
        m = self._re_ref.match(token)
        dims, kf = m.groups()
        fldmap = {}
        for d in dims.split(','):
            name,val = d.split('=')
            name,val = name.strip(), val.strip()
            if val == "$LOOP":
                inst = dims_map[name]
            else:
                inst = apps.get_model('bps',name).objects.get(pk=int(val))
            fldmap[name.lower()] = inst
        return kf, fldmap
    def _replace_refs_with_values(self, expr: str, dims_map: Dict[str,Any]):
        def repl(m):
            dims, k = m.groups()
            fkwargs = {}
            for d in dims.split(','):
                n,v = d.split('=')
                n,v = n.strip(), v.strip()
                if v == "$LOOP":
                    inst = dims_map[n]
                else:
                    inst = apps.get_model('bps',n).objects.get(pk=int(v))
                fkwargs[n.lower()] = inst
            return f"__ref__('{k}',{fkwargs})"
        return self._re_ref.sub(repl, expr)
    def _safe_eval(self, expr: str, dims_map: Dict[str,Any]) -> Decimal:
        ns = {
            '__if__': self.__if__,
            '__case__': self.__case__,
            '__ref__': lambda k, kwargs: self._aggregate_or_fetch(k, kwargs),
        }
        node = ast.parse(expr, mode='eval').body
        def _eval(node):
            if isinstance(node, ast.Call):
                func = _eval(node.func)
                args = [_eval(a) for a in node.args]
                return func(*args)
            if isinstance(node, ast.BinOp):
                return {
                  ast.Add: operator.add,
                  ast.Sub: operator.sub,
                  ast.Mult: operator.mul,
                  ast.Div: operator.truediv,
                  ast.Pow: operator.pow,
                }[type(node.op)](_eval(node.left), _eval(node.right))
            if isinstance(node, ast.UnaryOp):
                return operator.neg(_eval(node.operand))
            if isinstance(node, ast.Name):
                return ns[node.id]
            if isinstance(node, ast.Constant):
                return Decimal(str(node.value))
            raise ValueError("Unsupported AST node")
        return Decimal(str(round(_eval(node),4)))
    def _aggregate_or_fetch(self, kf: str, fkwargs: Dict[str,Any]) -> Decimal:
        for fn in _AGG_FUNCS:
            if kf.upper().startswith(fn+':'):
                real_kf = kf.split(':',1)[1]
                agg = _AGG_FUNCS[fn]('value')
                qs = PlanningFact.objects.filter(
                    session=self.session,
                    period=self.period,
                    key_figure__code=real_kf,
                    **{f"{dim}":inst for dim,inst in fkwargs.items()}
                ).aggregate(agg)
                return Decimal(str(qs[f"value__{fn.lower()}"] or 0))
        rec = PlanningFact.objects.filter(
            session=self.session,
            period=self.period,
            key_figure__code=kf,
            **{f"{dim}":inst for dim,inst in fkwargs.items()}
        ).first()
        return rec.value if rec else Decimal('0')
    def _get_record(self, kf: str, dims: Dict[str,Any], create=False):
        qs = PlanningFact.objects.filter(session=self.session,
                                         period=self.period,
                                         key_figure__code=kf,
                                         **{f"{dim}":inst for dim,inst in dims.items()})
        rec = qs.first()
        if not rec and create:
            rec = PlanningFact(
                request=self.run.formula,
                session=self.session,
                period=self.period,
                **{dim:inst for dim,inst in dims.items()},
                key_figure=apps.get_model('bps','KeyFigure').objects.get(code=kf),
                value=Decimal('0')
            )
            rec.save()
        return rec
    def _replace_reference_data(self, expr: str, dims_map: dict) -> str:
        def repl(m):
            ref_name = m.group(1)
            dims_spec= m.group(2)
            filters = {}
            for part in dims_spec.split(','):
                name,val = part.split('=')
                name, val = name.strip(), val.strip()
                if val == '$LOOP':
                    inst = dims_map[name]
                else:
                    inst = apps.get_model('bps',name).objects.get(pk=int(val))
                filters[name.lower()] = inst
            ref = ReferenceData.objects.get(name=ref_name)
            agg = ref.fetch_reference_fact(**filters)
            return str(agg.get('value__sum') or 0)
        return self._re_refdata.sub(repl, expr)
```

### `models.py`
```python
from uuid import uuid4
from django.db import models
from django.db.models import Sum
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from treebeard.mp_tree import MP_Node
class UnitOfMeasure(models.Model):
    code        = models.CharField(max_length=10, unique=True)
    name        = models.CharField(max_length=50)
    is_base     = models.BooleanField(default=False,
                                      help_text="Target unit for conversion rates")
    def __str__(self):
        return self.code
class ConversionRate(models.Model):
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
    pass
class OrgUnit(MP_Node, InfoObject):
    head_user      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        help_text="OrgUnit lead who must draft and approve"
    )
    cc_code    = models.CharField(max_length=10, blank=True)
    node_order_by = ['order', 'code']
class Account(InfoObject):
    pass
class Service(InfoObject):
    category         = models.CharField(max_length=50)
    subcategory      = models.CharField(max_length=50)
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
    cc_code    = models.CharField(max_length=10, blank=True)
class UserMaster(models.Model):
    user      = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    org_unit  = models.ForeignKey(OrgUnit, on_delete=models.SET_NULL, null=True)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True)
    def __str__(self):
        return self.user.get_full_name() or self.user.username
class CBU(InfoObject):
    group       = models.CharField(max_length=50, blank=True)
    TIER_CHOICES = [('1','Tier-1'),('2','Tier-2'),('3','Tier-3')]
    tier        = models.CharField(max_length=1, choices=TIER_CHOICES)
    sla_profile = models.ForeignKey('SLAProfile', on_delete=models.SET_NULL,
                                    null=True, blank=True)
    region      = models.CharField(max_length=50, blank=True)
    is_active   = models.BooleanField(default=True)
    node_order_by = ['cbu_code']
    def __str__(self):
        return f"{self.code} – {self.name}"
class SLAProfile(models.Model):
    name           = models.CharField(max_length=50, unique=True)
    response_time  = models.DurationField()
    resolution_time= models.DurationField()
    availability   = models.DecimalField(max_digits=5, decimal_places=3)
    description    = models.TextField(blank=True)
    def __str__(self):
        return self.name
class KeyFigure(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    is_percent = models.BooleanField(default=False)
    default_uom = models.ForeignKey(UnitOfMeasure, null=True, on_delete=models.SET_NULL)
class PlanningLayout(models.Model):
    code = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=200)
    domain = models.CharField(max_length=100)
    default = models.BooleanField(default=False)
    def __str__(self):
        return self.code
class PlanningDimension(models.Model):
    layout = models.ForeignKey(PlanningLayout, related_name="dimensions", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    label = models.CharField(max_length=100)
    is_row = models.BooleanField(default=False)
    is_column = models.BooleanField(default=False)
    is_filter = models.BooleanField(default=True)
    is_editable = models.BooleanField(default=False)
    required = models.BooleanField(default=True)
    data_source = models.CharField(max_length=100)
class PlanningKeyFigure(models.Model):
    layout = models.ForeignKey(PlanningLayout, related_name="key_figures", on_delete=models.CASCADE)
    code = models.CharField(max_length=100)
    label = models.CharField(max_length=100)
    is_editable = models.BooleanField(default=True)
    is_computed = models.BooleanField(default=False)
    formula = models.TextField(blank=True)
class PlanningLayoutYear(models.Model):
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE, related_name='per_year')
    year   = models.ForeignKey(Year, on_delete=models.CASCADE)
    version= models.ForeignKey(Version, on_delete=models.CASCADE)
    org_units = models.ManyToManyField(OrgUnit, blank=True)
    row_dims  = models.ManyToManyField(ContentType, blank=True)
    header_dims = models.JSONField(default=dict,
                      help_text="e.g. {'Company':'ALL','Region':'EMEA'}")
    class Meta:
        unique_together = ('layout','year','version')
    def __str__(self):
        return f"{self.layout.name} – {self.year.code} / {self.version.code}"
class Period(models.Model):
    code   = models.CharField(max_length=2, unique=True)
    name   = models.CharField(max_length=10)
    order  = models.PositiveSmallIntegerField()
    def __str__(self):
        return self.name
class PeriodGrouping(models.Model):
    layout_year = models.ForeignKey(PlanningLayoutYear, on_delete=models.CASCADE,
                                    related_name='period_groupings')
    months_per_bucket = models.PositiveSmallIntegerField(choices=[(1,'Monthly'),(3,'Quarterly'),(6,'Half-Year')])
    label_prefix = models.CharField(max_length=5, default='')
    class Meta:
        unique_together = ('layout_year','months_per_bucket')
    def buckets(self):
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
class PlanningSession(models.Model):
    layout_year = models.ForeignKey(PlanningLayoutYear, on_delete=models.CASCADE,
                                    related_name='sessions')
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
        self.status    = self.Status.FROZEN
        self.frozen_by = user
        self.frozen_at = models.functions.Now()
        self.save()
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
    request     = models.ForeignKey(DataRequest, on_delete=models.PROTECT)
    session     = models.ForeignKey(PlanningSession, on_delete=models.CASCADE)
    version     = models.ForeignKey(Version, on_delete=models.PROTECT)
    year        = models.ForeignKey(Year, on_delete=models.PROTECT)
    period      = models.ForeignKey(Period, on_delete=models.PROTECT)
    org_unit    = models.ForeignKey(OrgUnit, on_delete=models.PROTECT)
    service   = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT)
    account   = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT)
    driver_refs = models.JSONField(default=dict, help_text="e.g. {'Position':123, 'SkillGroup':'Developer'}")
    key_figure  = models.ForeignKey(KeyFigure, on_delete=models.PROTECT)
    value       = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    uom         = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='+', null=True)
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
        help_text=
    )
    def execute(self, session):
        if self.function_type == 'COPY':
            return self._copy_data(session)
        if self.function_type == 'DISTRIBUTE':
            return self._distribute(session)
        if self.function_type == 'CURRENCY_CONVERT':
            return self._currency_convert(session)
    def _copy_data(self, session):
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
            f.pk = None
            f.request = None
            f.session.layout_year.version_id = tgt_vid
            f.save()
            created += 1
        return created
    def _distribute(self, session):
        from bps.models import PlanningFact, ReferenceData
        by = self.parameters['by']
        ref_name = self.parameters['reference_data']
        ref = ReferenceData.objects.get(name=ref_name)
        total = ref.fetch_reference_fact(**{by: None})['value__sum'] or 0
        if total == 0:
            return 0
        qs = PlanningFact.objects.filter(session=session)
        created = 0
        for f in qs:
            share = f.value / total
            f.value = share * total
            f.save()
            created += 1
        return created
    def _currency_convert(self, session):
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
    def __str__(self):
        return f"Run
class FormulaRunEntry(models.Model):
    run        = models.ForeignKey(FormulaRun, related_name='entries', on_delete=models.CASCADE)
    record     = models.ForeignKey('PlanningFact', on_delete=models.CASCADE)
    key        = models.CharField(max_length=100)
    old_value  = models.DecimalField(max_digits=18, decimal_places=6)
    new_value  = models.DecimalField(max_digits=18, decimal_places=6)
    def __str__(self):
        return f"{self.record} :: {self.key}: {self.old_value} → {self.new_value}"
```

### `templates/bps/base.html`
```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Enterprise Planning{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-9ndCyUa6mY5D6T+Ly2YbMkQZ6Yr6Y1YAd+0F6fqG5s5B5KRb8DXe6fVXMZV+fl1M" crossorigin="anonymous">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{% static 'css/custom.css' %}" rel="stylesheet">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light bg-light shadow-sm">
        <div class="container-fluid">
            <a class="navbar-brand" href="{% url 'bps:dashboard' %}">CorpPlanner</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarMain" aria-controls="navbarMain" aria-expanded="false" aria-label="Toggle navigation">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarMain">
                <ul class="navbar-nav me-auto mb-2 mb-lg-0">
                    {% block nav_links %}
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'bps:inbox' %}"><i class="bi bi-inbox"></i> Inbox</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'bps:notifications' %}"><i class="bi bi-bell"></i> Notifications</a>
                    </li>
                    {% endblock %}
                </ul>
                <ul class="navbar-nav ms-auto mb-2 mb-lg-0">
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="userDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                            <i class="bi bi-person-circle"></i> {{ request.user.get_full_name }}
                        </a>
                        <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="userDropdown">
                            <li><a class="dropdown-item" href="{% url 'bps:profile' %}">Profile</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item" href="{% url 'logout' %}">Logout</a></li>
                        </ul>
                    </li>
                </ul>
            </div>
        </div>
    </nav>
    <div class="container-fluid mt-3">
        {% if breadcrumbs %}
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                {% for crumb in breadcrumbs %}
                <li class="breadcrumb-item {% if forloop.last %}active{% endif %}" {% if forloop.last %}aria-current="page"{% endif %}>
                    {% if not forloop.last %}
                    <a href="{{ crumb.url }}">{{ crumb.title }}</a>
                    {% else %}
                    {{ crumb.title }}
                    {% endif %}
                </li>
                {% endfor %}
            </ol>
        </nav>
        {% endif %}
        {% if messages %}
            {% for message in messages %}
            <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                {{ message }}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
            {% endfor %}
        {% endif %}
        {% block content %}{% endblock %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js" integrity="sha384-ENjdO4Dr2bkBIFxQpeo7F9LQG8Z1iQg9Ph2+Qx4U5Y0Q5h9vF3Vf5y2Q5y2qbi1" crossorigin="anonymous"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### `templates/bps/constant_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<h1>Constants</h1>
<form method="post" class="mb-4">{% csrf_token %}
  {{ form|crispy }}
</form>
<table class="table">
  <thead><tr><th>Name</th><th>Value</th></tr></thead>
  <tbody>
    {% for c in consts %}
      <tr><td>{{ c.name }}</td><td>{{ c.value }}</td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

### `templates/bps/dashboard.html`
```html
{% extends "bps/base.html" %}
{% load static %}
{% block content %}
<div class="container py-4">
  <h1 class="mb-4">Planning Dashboard</h1>
  <div class="row mb-4">
    <div class="col-md-4">
      <div class="card">
        <div class="card-header">Select Planning Year</div>
        <div class="card-body p-3">
          <form method="get">
            <select name="year" class="form-select" onchange="this.form.submit()">
              {% for y in all_years %}
                <option value="{{ y }}" {% if y == selected_year %}selected{% endif %}>
                  {{ y }}
                </option>
              {% endfor %}
            </select>
          </form>
        </div>
      </div>
    </div>
  </div>
  <div class="row gy-4">
    <div class="col-md-6">
      <div class="card h-100">
        <div class="card-header bg-warning text-white">Incomplete Planning Tasks</div>
        <ul class="list-group list-group-flush">
          {% for sess in incomplete_sessions %}
            <li class="list-group-item">
              <a href="{% url 'bps:session_detail' sess.pk %}">
                {{ sess.org_unit.name }} &dash; {{ sess.layout_year.layout.name }}
              </a>
            </li>
          {% empty %}
            <li class="list-group-item">None—everything is up to date!</li>
          {% endfor %}
        </ul>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card h-100">
        <div class="card-header bg-info text-white">Available Layouts</div>
        <div class="card-body">
          <div class="row row-cols-1 row-cols-md-2 g-3">
            {% for ly in layouts %}
              <div class="col">
                <div class="card h-100">
                  <div class="card-body p-2">
                    <h5 class="card-title mb-1">{{ ly.layout.name }}</h5>
                    <p class="card-text small mb-0">Version: {{ ly.version.code }}</p>
                  </div>
                  <div class="card-footer text-end">
                    <a href="{% url 'bps:session_list' %}?layout_year={{ ly.pk }}"
                       class="btn btn-sm btn-outline-primary">
                       Open
                    </a>
                  </div>
                </div>
              </div>
            {% empty %}
              <p class="text-muted">No layouts defined for {{ selected_year }}.</p>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card">
        <div class="card-header bg-success text-white">Planning Functions</div>
        <div class="card-body">
          <div class="list-group">
            {% for fn in planning_funcs %}
              <a href="{% url fn.url %}" class="list-group-item list-group-item-action">
                {{ fn.name }}
              </a>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card">
        <div class="card-header bg-secondary text-white">Admin</div>
        <div class="card-body">
          <div class="list-group">
            {% for link in admin_links %}
              <a href="{% url link.url %}" class="list-group-item list-group-item-action">
                {{ link.name }}
              </a>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

### `templates/bps/data_request_detail.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <h1>Data Request {{ dr.id }}</h1>
  <form method="post" class="mb-4">{% csrf_token %}
    {{ form|crispy }}
    <button type="submit" class="btn btn-primary">Update</button>
    <a href="{% url 'bps:data_request_list' %}" class="btn btn-link">Back to list</a>
  </form>
  <h2>Facts</h2>
  <table class="table table-striped">
    <thead>
      <tr>
        <th>Period</th>
        <th>Qty</th>
        <th>UoM</th>
        <th>Amount</th>
        <th>UoM</th>
        <th>Other</th>
        <th>Value</th>
      </tr>
    </thead>
    <tbody>
      {% for f in facts %}
      <tr>
        <td>{{ f.period }}</td>
        <td>{{ f.quantity }}</td>
        <td>{{ f.quantity_uom }}</td>
        <td>{{ f.amount }}</td>
        <td>{{ f.amount_uom }}</td>
        <td>{{ f.other_key_figure }}</td>
        <td>{{ f.other_value }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="7">No facts recorded yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
  <a href="{% url 'bps:fact_list' dr.pk %}" class="btn btn-success">Add/Edit Facts</a>
</div>
{% endblock %}
```

### `templates/bps/data_request_list.html`
```html
{% extends "bps/base.html" %}
{% block content %}
<div class="container my-4">
  <h1>Data Requests</h1>
  <ul class="list-group mt-3">
    {% for dr in data_requests %}
      <li class="list-group-item d-flex justify-content-between align-items-center">
        <a href="{% url 'bps:data_request_detail' dr.pk %}">
          {{ dr.id }} – {{ dr.description|default:"(no description)" }}
        </a>
        <span class="badge bg-secondary">
          {{ dr.created_at|date:"Y-m-d H:i" }}
        </span>
      </li>
    {% empty %}
      <li class="list-group-item">No data requests found.</li>
    {% endfor %}
  </ul>
</div>
{% endblock %}
```

### `templates/bps/fact_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <h1>Facts for Request {{ dr.id }}</h1>
  <form method="post" class="row g-3 align-items-end mb-4">{% csrf_token %}
    <div class="col-md-2">
      {{ form.session|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.period|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.quantity|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.quantity_uom|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.amount|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.amount_uom|as_crispy_field }}
    </div>
    <div class="col-md-3">
      {{ form.other_key_figure|as_crispy_field }}
    </div>
    <div class="col-md-3">
      {{ form.other_value|as_crispy_field }}
    </div>
    <div class="col-md-2">
      <button type="submit" class="btn btn-primary">Save Fact</button>
      <a href="{% url 'bps:data_request_detail' dr.pk %}" class="btn btn-link">Done</a>
    </div>
  </form>
  <table class="table table-bordered">
    <thead>
      <tr>
        <th>Period</th><th>Qty</th><th>UoM</th>
        <th>Amount</th><th>UoM</th><th>Other</th><th>Value</th>
      </tr>
    </thead>
    <tbody>
      {% for f in facts %}
      <tr>
        <td>{{ f.period }}</td>
        <td>{{ f.quantity }}</td>
        <td>{{ f.quantity_uom }}</td>
        <td>{{ f.amount }}</td>
        <td>{{ f.amount_uom }}</td>
        <td>{{ f.other_key_figure }}</td>
        <td>{{ f.other_value }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="7">No facts yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

### `templates/bps/formula_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<h1>Formulas</h1>
<form method="post" class="mb-4">{% csrf_token %}
  {{ form|crispy }}
</form>
<table class="table">
  <thead><tr><th>Name</th><th>Loop Dim</th><th>Expression</th><th>Actions</th></tr></thead>
  <tbody>
    {% for f in formulas %}
      <tr>
        <td>{{ f.name }}</td>
        <td>{{ f.loop_dimension.model }}</td>
        <td><code>{{ f.expression }}</code></td>
        <td>
          <a href="{% url 'formula_run' f.pk %}?period=01" class="btn btn-sm btn-primary">
            Run
          </a>
        </td>
      </tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

### `templates/bps/session_detail.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<h1>Planning: {{ sess.org_unit }} / {{ sess.layout_year }}</h1>
{% if sess.can_edit(request.user) %}
  <form method="post" class="mb-3">{% csrf_token %}
    {{ form|crispy }}
  </form>
{% endif %}
<h2>Period Definition</h2>
<form method="post" class="mb-3">{% csrf_token %}
  {{ period_form|crispy }}
</form>
<div id="period-table">
  <vue-period-table
    :buckets='{{ periods|safe }}'
  />
</div>
<h2>Current Facts ({{ dr.description }})</h2>
<table class="table table-sm">
  <thead>
    <tr>
      <th>Period</th>
      <th>Key Figure</th>
      <th>Value</th>
    </tr>
  </thead>
  <tbody>
    {% for f in facts %}
    <tr>
      <td>{{ f.period }}</td>
      <td>{{ f.key_figure }}</td>
      <td>{{ f.value }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% if sess.status == sess.Status.DRAFT and request.user == sess.org_unit.head_user %}
  <form method="post">
    {% csrf_token %}
    <button name="complete" class="btn btn-success">Mark Completed</button>
  </form>
{% endif %}
{% if sess.status == sess.Status.COMPLETED and request.user.is_staff %}
  <form method="post">
    {% csrf_token %}
    <button name="freeze" class="btn btn-danger">Freeze Session</button>
  </form>
{% endif %}
{% endblock %}
<script src="https://unpkg.com/vue@3"></script>
<script>
const app = Vue.createApp({});
app.component('vue-period-table', {
  props:['buckets'],
  template: `
    <table class="table table-bordered">
      <thead>
        <tr>
          <th v-for="b in buckets">{{ b.name }}</th>
        </tr>
      </thead>
    </table>`
});
app.mount('#period-table');
</script>
```

### `templates/bps/subformula_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<h1>Sub-Formulas</h1>
<form method="post" class="mb-4">{% csrf_token %}
  {{ form|crispy }}
</form>
<table class="table">
  <thead><tr><th>Name</th><th>Expression</th></tr></thead>
  <tbody>
    {% for s in subs %}
      <tr><td>{{ s.name }}</td><td><code>{{ s.expression }}</code></td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

### `templates/bps/variable_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <h1>Global Variables</h1>
  <form method="post" class="row g-3 align-items-end mb-4">{% csrf_token %}
    <div class="col-md-4">
      {{ form.name|as_crispy_field }}
    </div>
    <div class="col-md-4">
      {{ form.value|as_crispy_field }}
    </div>
    <div class="col-md-8">
      {{ form.description|as_crispy_field }}
    </div>
    <div class="col-md-2">
      <button type="submit" class="btn btn-primary">Add Variable</button>
    </div>
  </form>
  <table class="table table-hover">
    <thead>
      <tr><th>Name</th><th>Value</th><th>Description</th></tr>
    </thead>
    <tbody>
      {% for v in consts %}
      <tr>
        <td>{{ v.name }}</td>
        <td>{{ v.value }}</td>
        <td>{{ v.description }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="3">No variables defined.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

### `urls.py`
```python
from django.urls import path
from django.contrib.contenttypes.models import ContentType
from dal import autocomplete
from . import views
from .autocomplete import *
from .models import (
    Year, Period, OrgUnit, CBU, Account, InternalOrder, CostCenter,
    UnitOfMeasure, PlanningLayoutYear
)
app_name = "bps"
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('inbox/', views.inbox, name='inbox'),
    path('notifications/', views.notifications, name='notifications'),
    path('constants/', views.constant_list, name='constant_list'),
    path('subformulas/', views.subformula_list, name='subformula_list'),
    path('formulas/', views.formula_list, name='formula_list'),
    path('formulas/run/<int:pk>/', views.formula_run, name='formula_run'),
    path('functions/run/<int:pk>/', views.run_planning_function, name='run_function'),
    path('functions/',            views.planning_function_list,  name='planning_function_list'),
    path('functions/run/<int:pk>/<int:session_id>/', views.run_planning_function, name='run_function'),
    path('reference-data/',       views.reference_data_list,     name='reference_data_list'),
    path('data-requests/', views.data_request_list, name='data_request_list'),
    path('data-requests/<uuid:pk>/', views.data_request_detail, name='data_request_detail'),
    path('requests/<uuid:request_id>/facts/', views.fact_list, name='fact_list'),
    path('variables/', views.variable_list, name='variable_list'),
    path('sessions/', views.session_list, name='session_list'),
    path('sessions/<int:pk>/', views.session_detail, name='session_detail'),
    path('autocomplete/layout/',    LayoutAutocomplete.as_view(), name='layout-autocomplete'),
    path('autocomplete/contenttype/', ContentTypeAutocomplete.as_view(), name='contenttype-autocomplete'),
    path('autocomplete/year/',         YearAutocomplete.as_view(),         name='year-autocomplete'),
    path('autocomplete/period/',       PeriodAutocomplete.as_view(),       name='period-autocomplete'),
    path('autocomplete/orgunit/',      OrgUnitAutocomplete.as_view(),      name='orgunit-autocomplete'),
    path('autocomplete/cbu/',          CBUAutocomplete.as_view(),          name='cbu-autocomplete'),
    path('autocomplete/account/',      AccountAutocomplete.as_view(),      name='account-autocomplete'),
    path('autocomplete/internalorder/',InternalOrderAutocomplete.as_view(),name='internalorder-autocomplete'),
     path('autocomplete/uom/',          UnitOfMeasureAutocomplete.as_view(), name='uom-autocomplete'),
    path('autocomplete/layoutyear/',   LayoutYearAutocomplete.as_view(),   name='layoutyear-autocomplete'),
]
```

### `views.py`
```python
from uuid import UUID
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from .models import (
    Year, PlanningLayoutYear,
    PlanningSession, PlanningFunction, ReferenceData, DataRequest, PlanningFact,
    PeriodGrouping,
    Constant, SubFormula, Formula, FormulaRun
)
from .forms  import (
    PlanningSessionForm, PeriodSelector, ConstantForm, SubFormulaForm,
    FormulaForm, FactForm, PlanningFunctionForm, ReferenceDataForm
)
from .formula_executor import FormulaExecutor
from django.forms import modelform_factory
from django.shortcuts import render
from django.urls import reverse
def inbox(request):
    breadcrumbs = [
        {'url': reverse('bps:dashboard'), 'title': 'Dashboard'},
        {'url': request.path, 'title': 'Inbox'},
    ]
    items = []
    return render(request, 'bps/inbox.html', {
        'breadcrumbs': breadcrumbs,
        'items': items,
    })
def profile(request):
    return ""
def notifications(request):
    breadcrumbs = [
        {'url': reverse('bps:dashboard'), 'title': 'Dashboard'},
        {'url': request.path, 'title': 'Notifications'},
    ]
    notifications_list = []
    return render(request, 'bps/notifications.html', {
        'breadcrumbs': breadcrumbs,
        'notifications': notifications_list,
    })
def dashboard(request):
    current_year = timezone.now().year
    all_years = Year.objects.order_by('code').values_list('code', flat=True)
    selected_year = request.GET.get('year', str(current_year + 1))
    if selected_year not in all_years:
        selected_year = all_years[-1] if all_years else str(current_year)
    layouts = PlanningLayoutYear.objects.filter(year__code=selected_year).select_related('layout','version')
    incomplete_sessions = PlanningSession.objects.filter(
        layout_year__year__code=selected_year,
        status=PlanningSession.Status.DRAFT
    ).select_related('org_unit','layout_year').order_by('org_unit__name')
    planning_funcs = [
        {'name': 'Copy Actual → Plan', 'url': 'bps:copy_actual'},
        {'name': 'Distribute by Key',   'url': 'bps:distribute_key'},
        {'name': 'Run All Formulas',    'url': 'bps:formula_list'},
        {'name': 'Freeze Version',      'url': 'bps:session_list'},
    ]
    admin_links = [
        {'name': 'Manage Layouts',        'url': 'admin:bps_planninglayout_changelist'},
        {'name': 'Manage Layout-Years',   'url': 'admin:bps_planninglayoutyear_changelist'},
        {'name': 'Manage Periods',        'url': 'admin:bps_period_changelist'},
        {'name': 'Manage Sessions',       'url': 'admin:bps_planningsession_changelist'},
        {'name': 'Manage Data Requests',  'url': 'admin:bps_datarequest_changelist'},
    ]
    return render(request, 'bps/dashboard.html', {
        'all_years': all_years,
        'selected_year': selected_year,
        'layouts': layouts,
        'incomplete_sessions': incomplete_sessions,
        'planning_funcs': planning_funcs,
        'admin_links': admin_links,
    })
def session_list(request):
    sessions = PlanningSession.objects.all().order_by('-created_at')
    return render(request,'bps/session_list.html',{'sessions':sessions})
def session_detail(request, pk):
    sess = get_object_or_404(PlanningSession, pk=pk)
    if request.method=='POST' and 'start' in request.POST:
        form = PlanningSessionForm(request.POST)
        if form.is_valid():
            sess = form.save(commit=False)
            sess.created_by = request.user
            sess.save()
            messages.success(request,"Session started")
            return redirect('session_detail',sess.pk)
    else:
        form = PlanningSessionForm(instance=sess)
    if request.method=='POST' and 'apply' in request.POST:
        ps = PeriodSelector(request.POST, session=sess)
        if ps.is_valid():
            grouping = ps.cleaned_data['grouping']
            request.session['grouping_id'] = grouping.pk
            return redirect('session_detail',sess.pk)
    else:
        ps = PeriodSelector(session=sess)
    grouping = None
    if request.session.get('grouping_id'):
        grouping = PeriodGrouping.objects.get(pk=request.session['grouping_id'])
    periods = grouping.buckets() if grouping else []
    dr = sess.requests.order_by('-created_at').first()
    facts = dr.facts.all() if dr else []
    return render(request,'bps/session_detail.html',{
        'sess': sess, 'form': form,
        'period_form': ps, 'periods': periods,
        'facts': facts, 'dr': dr
    })
def constant_list(request):
    if request.method == 'POST':
        form = ConstantForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Constant saved.")
            return redirect('constant_list')
    else:
        form = ConstantForm()
    consts = Constant.objects.all()
    return render(request, 'bps/constant_list.html', {'form': form, 'consts': consts})
def subformula_list(request):
    if request.method == 'POST':
        form = SubFormulaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "SubFormula saved.")
            return redirect('subformula_list')
    else:
        form = SubFormulaForm()
    subs = SubFormula.objects.all()
    return render(request, 'bps/subformula_list.html', {'form': form, 'subs': subs})
def formula_list(request):
    if request.method == 'POST':
        form = FormulaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Formula saved.")
            return redirect('formula_list')
    else:
        form = FormulaForm()
    formulas = Formula.objects.all()
    return render(request, 'bps/formula_list.html', {'form': form, 'formulas': formulas})
def formula_run(request, pk):
    formula = get_object_or_404(Formula, pk=pk)
    session = request.user.planningsession_set.filter(status='D').first()
    period  = request.GET.get('period', '01')
    executor = FormulaExecutor(formula, session, period, preview=False)
    entries = executor.execute()
    messages.success(request, f"Executed {formula.name}, {entries.count()} entries updated.")
    return redirect(reverse('formula_list'))
def planning_function_list(request):
    if request.method == 'POST':
        form = PlanningFunctionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Planning Function saved.")
            return redirect('bps:planning_function_list')
    else:
        form = PlanningFunctionForm()
    functions = PlanningFunction.objects.all()
    return render(request, 'bps/planning_function_list.html', {
        'form': form, 'functions': functions
    })
def run_planning_function(request, pk, session_id):
    func = get_object_or_404(PlanningFunction, pk=pk)
    session = get_object_or_404(PlanningSession, pk=session_id)
    result = func.execute(session)
    messages.success(
        request,
        f"{func.get_function_type_display()} executed, result: {result}"
    )
    return redirect('bps:session_detail', pk=session_id)
def reference_data_list(request):
    if request.method == 'POST':
        form = ReferenceDataForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Reference Data saved.")
            return redirect('bps:reference_data_list')
    else:
        form = ReferenceDataForm()
    refs = ReferenceData.objects.all()
    return render(request, 'bps/reference_data_list.html', {
        'form': form, 'references': refs
    })
DataRequestForm = modelform_factory(DataRequest, fields=['description'])
def data_request_list(request):
    requests = DataRequest.objects.order_by('-created_at')
    return render(request, "bps/data_request_list.html", {
        "data_requests": requests
    })
def data_request_detail(request, pk: UUID):
    dr = get_object_or_404(DataRequest, pk=pk)
    if request.method == 'POST':
        form = DataRequestForm(request.POST, instance=dr)
        if form.is_valid():
            form.save()
            messages.success(request, "DataRequest updated.")
            return redirect("bps:data_request_detail", pk=pk)
    else:
        form = DataRequestForm(instance=dr)
    facts = dr.facts.order_by('period')
    return render(request, "bps/data_request_detail.html", {
        "dr": dr,
        "form": form,
        "facts": facts,
    })
def fact_list(request, request_id: UUID):
    dr = get_object_or_404(DataRequest, pk=request_id)
    if request.method == 'POST':
        form = FactForm(request.POST)
        if form.is_valid():
            fact = form.save(commit=False)
            fact.request = dr
            fact.session = dr.session
            fact.save()
            messages.success(request, "PlanningFact added.")
            return redirect("bps:fact_list", request_id=request_id)
    else:
        form = FactForm()
    facts = dr.facts.order_by('period')
    return render(request, "bps/fact_list.html", {
        "dr": dr, "form": form, "facts": facts
    })
def variable_list(request):
    if request.method == 'POST':
        form = ConstantForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Global variable saved.")
            return redirect("bps:variable_list")
    else:
        form = ConstantForm()
    consts = Constant.objects.order_by('name')
    return render(request, "bps/variable_list.html", {
        "form": form,
        "consts": consts,
    })
def run_planning_function(request, pk, session_id):
    func = get_object_or_404(PlanningFunction, pk=pk)
    session = get_object_or_404(PlanningSession, pk=session_id)
    count_or_result = func.execute(session)
    messages.success(
        request,
        f"{func.get_function_type_display()} executed, result: {count_or_result}"
    )
    return redirect('bps:session_detail', pk=session_id)
```

