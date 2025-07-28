
### `autocomplete.py`
```python
from dal_select2.views import Select2QuerySetView
from dal_select2.widgets import ModelSelect2, ModelSelect2Multiple
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from .models.models import (
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
from .models.models import (
    Constant, SubFormula, Formula, PlanningFunction, ReferenceData,
    PlanningLayoutYear, PeriodGrouping, PlanningSession,
    DataRequest, PlanningFact, Year, Version, OrgUnit
)
class FactForm(forms.ModelForm):
    class Meta:
        model = PlanningFact
        fields = [
            'service', 'account', 'dimension_values',
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
                Column('dimension_values', css_class='col-md-4'),
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
        fields = ['org_unit']
        widgets = {
           'org_unit'   : ModelSelect2(url='bps:orgunit-autocomplete'),
        }
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
          Row(
              Column('org_unit',    css_class='col-md-6')
        ),
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
from bps.models.models import (
    PlanningFact, Formula, Constant, SubFormula,
    FormulaRun, FormulaRunEntry, ReferenceData, Period
)
_AGG_FUNCS = {
    'SUM': Sum,
    'AVG': Avg,
    'MIN': Min,
    'MAX': Max,
}
class FormulaExecutor:
    _re_refdata = re.compile(r"REF\('([^']+)'\s*,\s*([^\)]+)\)")
    _re_subf   = re.compile(r"\$(\w+)")
    _re_const  = re.compile(r"\b[A-Z_][A-Z0-9_]*\b")
    _re_ref    = re.compile(r"\[(.*?)\]\.\?\[(.*?)\]")
    def __init__(self, formula: Formula, session, period: str, preview: bool=False):
        self.formula = formula
        self.session = session
        self.period  = period
        self.preview = preview
        self.run     = None
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
        result   = self._safe_eval(src_eval, dims_map)
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
            text = arm.strip()
            if text.upper().startswith("WHEN"):
                _, cond, _, val = re.split(r"\s+", text, maxsplit=3)
                if self._safe_eval(cond, {}):
                    return self._safe_eval(val, {})
            elif text.upper().startswith("ELSE"):
                return self._safe_eval(text.split(None,1)[1], {})
        return Decimal('0')
    def _parse_ref(self, token: str, dims_map: Dict[str,Any]):
        m = self._re_ref.match(token)
        dims, kf = m.groups()
        fldmap = {}
        for d in dims.split(','):
            name,val = d.split('=')
            name,val = name.strip(), val.strip()
            if val == '$LOOP':
                inst = dims_map[name]
            else:
                inst = apps.get_model('bps',name).objects.get(pk=int(val))
            fldmap[name.lower()] = inst
        return kf, fldmap
    def _replace_refs_with_values(self, expr: str, dims_map: Dict[str,Any]) -> str:
        def repl(m):
            dims, k = m.groups()
            fkwargs = {}
            for d in dims.split(','):
                n,v = d.split('=')
                n,v = n.strip(), v.strip()
                if v == '$LOOP':
                    inst = dims_map[n]
                else:
                    inst = apps.get_model('bps',n).objects.get(pk=int(v))
                fkwargs[n.lower()] = inst
            return f"__ref__('{k}',{fkwargs})"
        return self._re_ref.sub(repl, expr)
    def _safe_eval(self, expr: str, dims_map: Dict[str,Any]) -> Decimal:
        def shift_func(k, offset):
            return self._shift(k, offset, dims_map)
        def lookup_func(k, **overrides):
            return self._lookup(k, dims_map, overrides)
        ns = {
            '__if__': self.__if__,
            '__case__': self.__case__,
            '__ref__': lambda k, kwargs: self._aggregate_or_fetch(k, kwargs),
            'SHIFT': shift_func,
            'LOOKUP': lookup_func,
        }
        node = ast.parse(expr, mode='eval').body
        def _eval(n):
            if isinstance(n, ast.Call):
                func = _eval(n.func)
                args = [_eval(a) for a in n.args]
                kwargs = {kw.arg: _eval(kw.value) for kw in n.keywords}
                return func(*args, **kwargs)
            if isinstance(n, ast.BinOp):
                return {
                  ast.Add: operator.add,
                  ast.Sub: operator.sub,
                  ast.Mult: operator.mul,
                  ast.Div: operator.truediv,
                  ast.Pow: operator.pow,
                }[type(n.op)](_eval(n.left), _eval(n.right))
            if isinstance(n, ast.UnaryOp):
                return operator.neg(_eval(n.operand))
            if isinstance(n, ast.Name):
                return ns[n.id]
            if isinstance(n, ast.Constant):
                return Decimal(str(n.value))
            raise ValueError(f"Unsupported AST node: {n}")
        return Decimal(str(round(_eval(node),4)))
    def _aggregate_or_fetch(self, kf: str, fkwargs: Dict[str,Any]) -> Decimal:
        return self._aggregate_or_fetch_for_period(kf, fkwargs, self.period)
    def _aggregate_or_fetch_for_period(self, kf: str, fkwargs: Dict[str,Any], period_code: str) -> Decimal:
        for fn, aggfunc in _AGG_FUNCS.items():
            if kf.upper().startswith(fn + ':'):
                real_kf = kf.split(':',1)[1]
                agg = aggfunc('value')
                qs = PlanningFact.objects.filter(
                    session=self.session,
                    period__code=period_code,
                    key_figure__code=real_kf,
                    **{dim:inst for dim,inst in fkwargs.items()}
                ).aggregate(agg)
                return Decimal(str(qs[f"value__{fn.lower()}"] or 0))
        rec = PlanningFact.objects.filter(
            session=self.session,
            period__code=period_code,
            key_figure__code=kf,
            **{dim:inst for dim,inst in fkwargs.items()}
        ).first()
        return rec.value if rec else Decimal('0')
    def _shift(self, kf: str, offset: Any, dims_map: Dict[str,Any]) -> Decimal:
        all_codes = list(Period.objects.order_by('order').values_list('code', flat=True))
        try:
            idx = all_codes.index(self.period)
        except ValueError:
            return Decimal('0')
        ni = idx + int(offset)
        if ni < 0 or ni >= len(all_codes):
            return Decimal('0')
        new_period = all_codes[ni]
        return self._aggregate_or_fetch_for_period(kf, dims_map, new_period)
    def _lookup(self, kf: str, base_dims: Dict[str,Any], overrides: Dict[str,Any]) -> Decimal:
        dims = base_dims.copy()
        for dim_name, val in overrides.items():
            try:
                inst = apps.get_model('bps', dim_name).objects.get(pk=int(val))
                dims[dim_name] = inst
            except Exception:
                continue
        return self._aggregate_or_fetch_for_period(kf, dims, self.period)
```

### `manual_planning.py`
```python
from django.views.generic import TemplateView
from django.shortcuts import redirect, get_object_or_404
from bps.models import PlanningLayoutYear, Year, Version, Period
class ManualPlanningSelectView(TemplateView):
    template_name = 'bps/manual_planning_select.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['layouts'] = PlanningLayoutYear.objects.select_related('layout','year','version')
        return ctx
class ManualPlanningView(TemplateView):
    template_name = 'bps/manual_planning.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        layout_id  = self.kwargs.get('layout_id')
        year_id    = self.kwargs.get('year_id')
        version_id = self.kwargs.get('version_id')
        if not (layout_id and year_id and version_id):
            return redirect('bps:manual-planning-select')
        ly = get_object_or_404(
            PlanningLayoutYear,
            layout_id=layout_id,
            year_id=year_id,
            version_id=version_id
        )
        ctx.update({
            'layout_year': ly,
            'layout':      ly.layout,
            'year':        ly.year,
            'version':     ly.version,
            'periods':     Period.objects.order_by('order'),
        })
        return ctx
```

### `views.py`
```python
from uuid import UUID
import json
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.contrib import messages
from django.views import View
from django.views.generic import (
    TemplateView, ListView, DetailView,
    FormView, RedirectView
)
from django.views.generic.edit import FormMixin
from django.forms import modelform_factory
from .models.models import (
    PlanningScenario, PlanningSession, PlanningStage, PlanningLayoutYear,
    PlanningLayout, Year, Version, Period,
    PlanningFact, DataRequest, Constant, SubFormula,
    Formula, PlanningFunction, ReferenceData
)
from .forms import (
    PlanningSessionForm, PeriodSelector, ConstantForm,
    SubFormulaForm, FormulaForm, FactForm,
    PlanningFunctionForm, ReferenceDataForm
)
from .formula_executor import FormulaExecutor
class ScenarioDashboardView(TemplateView):
    template_name = "bps/scenario_dashboard.html"
    def get_context_data(self, **kwargs):
        scenario = get_object_or_404(PlanningScenario, code=kwargs['code'])
        sessions = PlanningSession.objects.filter(
            layout_year=scenario.layout_year,
            org_unit__in=scenario.org_units.all()
        ).select_related('org_unit','current_stage')
        return {
            'scenario': scenario,
            'sessions': sessions,
            'stages': scenario.stages.all(),
            'org_units': scenario.org_units.all(),
        }
class DashboardView(TemplateView):
    template_name = 'bps/dashboard.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().year
        all_years = Year.objects.order_by('code').values_list('code', flat=True)
        selected_year = self.request.GET.get('year', str(current_year + 1))
        if selected_year not in all_years:
            selected_year = all_years[-1] if all_years else str(current_year)
        ctx.update({
            'all_years': all_years,
            'selected_year': selected_year,
            'layouts': PlanningLayoutYear.objects.filter(
                year__code=selected_year
            ).select_related('layout', 'version'),
            'incomplete_sessions': PlanningSession.objects.filter(
                layout_year__year__code=selected_year,
                status=PlanningSession.Status.DRAFT
            ).select_related('org_unit', 'layout_year').order_by('org_unit__name'),
            'planning_funcs': [
                {'name': 'Inbox', 'url': reverse('bps:inbox')},
                {'name': 'Notifications', 'url': reverse('bps:notifications')},
                {'name': 'Start New Session', 'url': reverse('bps:session_list')},
                {'name': 'Run All Formulas', 'url': reverse('bps:formula_list')},
                {'name': 'Create Reference Data', 'url': reverse('bps:reference_data_list')},
            ],
            'admin_links': [
                {'name': 'Layouts', 'url': reverse('admin:bps_planninglayout_changelist')},
                {'name': 'Layout-Years', 'url': reverse('admin:bps_planninglayoutyear_changelist')},
                {'name': 'Periods', 'url': reverse('admin:bps_period_changelist')},
                {'name': 'Sessions', 'url': reverse('admin:bps_planningsession_changelist')},
                {'name': 'Data Requests', 'url': reverse('admin:bps_datarequest_changelist')},
                {'name': 'Constants', 'url': reverse('bps:constant_list')},
                {'name': 'SubFormulas', 'url': reverse('bps:subformula_list')},
                {'name': 'Formulas', 'url': reverse('bps:formula_list')},
                {'name': 'Functions', 'url': reverse('bps:planning_function_list')},
                {'name': 'Rate Cards', 'url': reverse('admin:bps_ratecard_changelist')},
                {'name': 'Positions', 'url': reverse('admin:bps_position_changelist')},
            ],
        })
        return ctx
class ProfileView(View):
    def get(self, request):
        return HttpResponse('')
class InboxView(TemplateView):
    template_name = 'bps/inbox.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['breadcrumbs'] = [
            {'url': reverse('bps:dashboard'), 'title': 'Dashboard'},
            {'url': self.request.path,    'title': 'Inbox'},
        ]
        ctx['items'] = []
        return ctx
class NotificationsView(TemplateView):
    template_name = 'bps/notifications.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['breadcrumbs'] = [
            {'url': reverse('bps:dashboard'), 'title': 'Dashboard'},
            {'url': self.request.path,        'title': 'Notifications'},
        ]
        ctx['notifications'] = []
        return ctx
class ManualPlanningSelectView(TemplateView):
    template_name = "bps/manual_planning_select.html"
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["layouts"] = PlanningLayoutYear.objects.select_related(
            "layout", "year", "version"
        )
        return ctx
class ManualPlanningView(TemplateView):
    template_name = "bps/manual_planning.html"
    def get_context_data(self, layout_id, year_id, version_id, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["layout"]      = PlanningLayout.objects.get(pk=layout_id)
        ctx["year"]        = Year.objects.get(pk=year_id)
        ctx["version"]     = Version.objects.get(pk=version_id)
        ctx["layout_year"] = PlanningLayoutYear.objects.filter(
            layout_id=layout_id, year_id=year_id, version_id=version_id
        ).first()
        ctx["periods"]     = Period.objects.all().order_by("order")
        return ctx
class PlanningSessionListView(ListView):
    model = PlanningSession
    template_name = 'bps/session_list.html'
    context_object_name = 'sessions'
    ordering = ['-created_at']
    paginate_by = 50
class PlanningSessionDetailView(DetailView, FormMixin):
    model = PlanningSession
    template_name = 'bps/session_detail.html'
    context_object_name = 'sess'
    pk_url_kwarg = 'pk'
    form_class = PlanningSessionForm
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sess = self.object
        user = self.request.user
        ctx['can_edit']   = sess.can_edit(user)
        ctx['form']       = self.get_form()
        ctx['period_form'] = PeriodSelector(session=sess)
        grouping_id = self.request.session.get('grouping_id')
        if grouping_id:
            grouping = get_object_or_404(PeriodGrouping, pk=grouping_id)
            ctx['periods'] = grouping.buckets()
        else:
            ctx['periods'] = []
        ctx['dr']    = sess.requests.order_by('-created_at').first()
        facts        = PlanningFact.objects.filter(session=sess)
        hot_rows     = [
            [str(f.period), f.key_figure.code, float(f.value)]
            for f in facts
        ]
        ctx['hot_data'] = json.dumps(hot_rows)
        ctx['can_advance'] = bool(sess.current_stage and user.is_staff)
        return ctx
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        sess = self.object
        if 'start' in request.POST:
            form = PlanningSessionForm(request.POST, instance=sess)
            if form.is_valid():
                sess = form.save(commit=False)
                sess.created_by = request.user
                sess.save()
                messages.success(request, "Session started")
                return redirect('bps:session_detail', pk=sess.pk)
        if 'apply' in request.POST:
            ps = PeriodSelector(request.POST, session=sess)
            if ps.is_valid():
                request.session['grouping_id'] = ps.cleaned_data['grouping'].pk
                return redirect('bps:session_detail', pk=sess.pk)
        return self.get(request, *args, **kwargs)
class AdvanceStageView(View):
    def get(self, request, session_id):
        sess = get_object_or_404(PlanningSession, pk=session_id)
        next_stage = PlanningStage.objects.filter(
            order__gt=sess.current_stage.order
        ).order_by('order').first()
        if not next_stage:
            messages.warning(request, "Already at final stage.")
        else:
            sess.current_stage = next_stage
            sess.save(update_fields=['current_stage'])
            messages.success(request, f"Moved to stage: {next_stage.name}")
        return redirect('bps:session_detail', pk=session_id)
class ConstantListView(FormMixin, ListView):
    model = Constant
    template_name = 'bps/constant_list.html'
    context_object_name = 'consts'
    form_class = ConstantForm
    success_url = reverse_lazy('bps:constant_list')
    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "Constant saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)
class SubFormulaListView(FormMixin, ListView):
    model = SubFormula
    template_name = 'bps/subformula_list.html'
    context_object_name = 'subs'
    form_class = SubFormulaForm
    success_url = reverse_lazy('bps:subformula_list')
    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "SubFormula saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)
class FormulaListView(FormMixin, ListView):
    model = Formula
    template_name = 'bps/formula_list.html'
    context_object_name = 'formulas'
    form_class = FormulaForm
    success_url = reverse_lazy('bps:formula_list')
    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "Formula saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)
class FormulaRunView(View):
    def get(self, request, pk):
        formula = get_object_or_404(Formula, pk=pk)
        session = request.user.planningsession_set.filter(
            status=PlanningSession.Status.DRAFT
        ).first()
        period = request.GET.get('period', '01')
        entries = FormulaExecutor(formula, session, period, preview=False).execute()
        messages.success(
            request,
            f"Executed {formula.name}, {entries.count()} entries updated."
        )
        return redirect('bps:formula_list')
class PlanningFunctionListView(FormMixin, ListView):
    model = PlanningFunction
    template_name = 'bps/planning_function_list.html'
    context_object_name = 'functions'
    form_class = PlanningFunctionForm
    success_url = reverse_lazy('bps:planning_function_list')
    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "Planning Function saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)
class RunPlanningFunctionView(View):
    def get(self, request, pk, session_id):
        func = get_object_or_404(PlanningFunction, pk=pk)
        session = get_object_or_404(PlanningSession, pk=session_id)
        result = func.execute(session)
        messages.success(
            request,
            f"{func.get_function_type_display()} executed, result: {result}"
        )
        return redirect('bps:session_detail', pk=session_id)
class CopyActualView(View):
    def get(self, request):
        messages.info(request, "Copy Actual → Plan is not yet implemented.")
        return redirect('bps:dashboard')
class DistributeKeyView(View):
    def get(self, request):
        messages.info(request, "Distribute by Key is not yet implemented.")
        return redirect('bps:dashboard')
class ReferenceDataListView(FormMixin, ListView):
    model = ReferenceData
    template_name = 'bps/reference_data_list.html'
    context_object_name = 'references'
    form_class = ReferenceDataForm
    success_url = reverse_lazy('bps:reference_data_list')
    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "Reference Data saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)
DataRequestForm = modelform_factory(DataRequest, fields=['description'])
class DataRequestListView(ListView):
    model = DataRequest
    template_name = 'bps/data_request_list.html'
    context_object_name = 'data_requests'
    ordering = ['-created_at']
class DataRequestDetailView(FormMixin, DetailView):
    model = DataRequest
    template_name = 'bps/data_request_detail.html'
    context_object_name = 'dr'
    form_class = DataRequestForm
    def get_success_url(self):
        return reverse_lazy('bps:data_request_detail', kwargs={'pk': self.object.pk})
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "DataRequest updated.")
            return redirect(self.get_success_url())
        return self.form_invalid(form)
class FactListView(FormMixin, ListView):
    template_name = 'bps/fact_list.html'
    context_object_name = 'facts'
    form_class = FactForm
    def get_queryset(self):
        return PlanningFact.objects.filter(
            request__pk=self.kwargs['request_id']
        ).order_by('period')
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['dr'] = get_object_or_404(DataRequest, pk=self.kwargs['request_id'])
        return ctx
    def get_success_url(self):
        return reverse_lazy('bps:fact_list', kwargs={'request_id': self.kwargs['request_id']})
    def post(self, request, *args, **kwargs):
        dr = get_object_or_404(DataRequest, pk=self.kwargs['request_id'])
        form = self.get_form()
        if form.is_valid():
            fact = form.save(commit=False)
            fact.request = dr
            fact.session = dr.session
            fact.save()
            messages.success(request, "PlanningFact added.")
            return redirect(self.get_success_url())
        return self.form_invalid(form)
class VariableListView(ConstantListView):
    template_name = 'bps/variable_list.html'
    success_url = reverse_lazy('bps:variable_list')
```

### `views_decorator.py`
```python
from rest_framework.response import Response
from .models.models import PlanningSession
def require_stage(stage_code):
    def decorator(fn):
        def wrapped(self, request, *args, **kw):
            sess = PlanningSession.objects.get(pk=kw.get('session_id'))
            if sess.current_stage.code != stage_code \
               and not sess.current_stage.can_run_in_parallel:
                return Response(
                    {"detail": f"Must be in {stage_code} step to call this."},
                    status=403
                )
            return fn(self, request, *args, **kw)
        return wrapped
    return decorator
```

### `viewsets.py`
```python
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
import csv
from bps.models.models import PlanningFact, OrgUnit
from .serializers import PlanningFactSerializer, PlanningFactCreateUpdateSerializer
from .serializers import OrgUnitSerializer
class PlanningFactViewSet(viewsets.ModelViewSet):
    queryset = PlanningFact.objects.select_related(
        'org_unit','service','period','key_figure'
    ).all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields   = ['org_unit__name','service__name']
    ordering_fields = ['period__order']
    def get_serializer_class(self):
        if self.action in ('create','update','partial_update'):
            return PlanningFactCreateUpdateSerializer
        return PlanningFactSerializer
    @action(detail=False, methods=['get'])
    def export(self, request):
        qs = self.filter_queryset(self.get_queryset())
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="facts.csv"'
        writer = csv.writer(resp)
        writer.writerow(['ID','OrgUnit','Service','Period','KeyFigure','Value','RefValue'])
        for f in qs:
            writer.writerow([
                f.id,
                f.org_unit.name,
                f.service.name if f.service else '',
                f.period.code,
                f.key_figure.code,
                f.value,
                f.ref_value,
            ])
        return resp
class OrgUnitViewSet(viewsets.ModelViewSet):
    queryset = OrgUnit.objects.all()
    serializer_class = OrgUnitSerializer
```

