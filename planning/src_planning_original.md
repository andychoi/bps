# Python Project Summary: bps

---

### `apps.py`
```python
from django.apps import AppConfig
class BpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bps"
```

### `formula_executor.py`
```python
import re
import ast
import operator
from typing import Dict, Any
from django.apps import apps
from bps.models import (
    PlanningRecord, Formula, Constant, SubFormula,
    FormulaRun, FormulaRunEntry
)
class FormulaExecutor:
    def __init__(self, formula: Formula, preview: bool = False):
        self.formula = formula
        self.layout = formula.layout
        self.loop_dimension = formula.loop_dimension.model_class()
        self.base_expr = formula.expression
        self.preview = preview
    def execute(self):
        self.run = FormulaRun.objects.create(formula=self.formula, preview=self.preview)
        for loop_value in self.loop_dimension.objects.all():
            self._apply_formula(loop_value)
        return self.run.entries.all()
    def _apply_formula(self, loop_value):
        expr = self._expand_subformulas(self.base_expr, loop_value)
        expr = self._replace_constants(expr)
        target_expr, source_expr = map(str.strip, expr.split('='))
        target_key = self._parse_key(target_expr, loop_value)
        replaced = self._replace_keys_with_values(source_expr, loop_value)
        result = self._safe_eval(replaced)
        record = self._get_record_by_key(target_key, create_if_missing=not self.preview)
        old_val = record.key_figure_values.get(target_key['k'], 0)
        if not self.preview:
            record.key_figure_values[target_key['k']] = result
            record.save()
        FormulaRunEntry.objects.create(
            run=self.run,
            record=record,
            key=target_key['k'],
            old_value=old_val,
            new_value=result
        )
    def _expand_subformulas(self, expr: str, loop_value) -> str:
        def repl(m):
            name = m.group(1)
            sub = SubFormula.objects.get(name=name, layout=self.layout)
            return f"({self._expand_subformulas(sub.expression, loop_value)})"
        return re.sub(r"\$(\w+)", repl, expr)
    def _replace_constants(self, expr: str) -> str:
        def repl(m):
            const = Constant.objects.get(name=m.group(0))
            return str(const.value)
        return re.sub(r"\b[A-Z_][A-Z0-9_]*\b", repl, expr)
    def _replace_keys_with_values(self, expr: str, loop_value) -> str:
        pattern = r"\[(.*?)\]\.\?\[(.*?)\]"
        def repl(m):
            dims, k = m.groups()
            filter_kwargs = {}
            for d in dims.split(','):
                d = d.strip()
                Model = apps.get_model('bps', d.capitalize())
                field_name = None
                for f in PlanningRecord._meta.get_fields():
                    if getattr(f, 'related_model', None) == Model:
                        field_name = f.name
                        break
                if not field_name:
                    raise ValueError(f"No FK on PlanningRecord for dimension {d}")
                if Model == self.loop_dimension:
                    filter_kwargs[field_name] = loop_value
                else:
                    filter_kwargs[field_name] = self._resolve_dimension_value(d)
            rec = self._get_record_by_key({'filter': filter_kwargs, 'k': k})
            return str(rec.key_figure_values.get(k, 0) if rec else 0)
        return re.sub(pattern, repl, expr)(pattern, repl, expr)
    def _safe_eval(self, expr: str) -> float:
        ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
        }
        def _eval(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.Num):
                return node.n
            if isinstance(node, ast.BinOp):
                return ops[type(node.op)](_eval(node.left), _eval(node.right))
            if isinstance(node, ast.UnaryOp):
                return ops[type(node.op)](_eval(node.operand))
            raise ValueError("Unsupported expression")
        node = ast.parse(expr, mode='eval').body
        return round(_eval(node), 4)(_eval(node), 4)("Unsupported")
        return round(_eval(ast.parse(expr, mode='eval').body), 4)
    def _parse_key(self, expr: str, loop_value) -> Dict[str, Any]:
        m = re.match(r"\[(.*?)\]\.\?\[(.*?)\]", expr)
        if not m:
            raise ValueError(f"Invalid expression format: {expr}")
        dims, k = m.groups()
        filter_kwargs = {}
        for d in dims.split(','):
            d = d.strip()
            Model = apps.get_model('bps', d.capitalize())
            field_name = None
            for f in PlanningRecord._meta.get_fields():
                if getattr(f, 'related_model', None) == Model:
                    field_name = f.name
                    break
            if not field_name:
                raise ValueError(f"No FK on PlanningRecord for dimension {d}")
            if Model == self.loop_dimension:
                filter_kwargs[field_name] = loop_value
            else:
                filter_kwargs[field_name] = self._resolve_dimension_value(d)
        return {'filter': filter_kwargs, 'k': k}
    def _resolve_dimension_value(self, dim: str):
        Model = apps.get_model('bps', dim.capitalize())
        return Model.objects.first()
    def _get_record_by_key(self, key: Dict[str, Any], create_if_missing=False):
        qs = PlanningRecord.objects.filter(layout=self.layout)
        for f, v in key['filter'].items():
            qs = qs.filter(**{f: v})
        rec = qs.first()
        if not rec and create_if_missing:
            rec = PlanningRecord(layout=self.layout, dimension_values={}, key_figure_values={})
            for f, v in key['filter'].items(): setattr(rec, f, v)
            rec.save()
        return rec
```

### `models.py`
```python
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
class Year(models.Model):
    value = models.PositiveIntegerField(unique=True)
    def __str__(self):
        return str(self.value)
class PlanVersion(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self):
        return self.name
class OrgUnit(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self):
        return self.name
class Account(models.Model):
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    def __str__(self):
        return f"{self.code} - {self.name}"
class CBU(models.Model):
    name = models.CharField(_("name"), max_length=10, db_index=True, unique=True)
    fullname = models.CharField(_("full name"), max_length=100)
    group = models.CharField(_("group name"), max_length=100, blank=True, null=True)
    is_active = models.BooleanField(_("is active"), default=True)
    is_tier1 = models.BooleanField(_("is Tier-1"), default=False)
    class Meta:
        ordering = ["id"]
        verbose_name = _("CBU")
        verbose_name_plural = _("CBU")
    def __str__(self):
        return self.name
class Period(models.Model):
    code = models.CharField(max_length=10)
    order = models.PositiveIntegerField()
    def __str__(self):
        return self.code
class PlanningLayout(models.Model):
    name = models.CharField(max_length=100)
    lead_dimensions = models.ManyToManyField(
        ContentType,
        through='PlanningLayoutLeadDimension',
        related_name='lead_dimensions'
    )
    column_dimension = models.ForeignKey(
        ContentType,
        null=True,
        on_delete=models.SET_NULL,
        related_name='column_dimension'
    )
    key_figures = models.JSONField(default=list)
    def __str__(self):
        return self.name
class PlanningLayoutLeadDimension(models.Model):
    bpslayout = models.ForeignKey(
        PlanningLayout,
        on_delete=models.CASCADE
    )
    contenttype = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )
    class Meta:
        unique_together = ('bpslayout', 'contenttype')
class PlanningRecord(models.Model):
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE)
    year = models.ForeignKey(Year, null=True, blank=True, on_delete=models.SET_NULL)
    version = models.ForeignKey(PlanVersion, null=True, blank=True, on_delete=models.SET_NULL)
    orgunit = models.ForeignKey(OrgUnit, null=True, blank=True, on_delete=models.SET_NULL)
    account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL)
    cbu     = models.ForeignKey(CBU,       null=True, blank=True, on_delete=models.SET_NULL)
    period = models.ForeignKey(Period, null=True, blank=True, on_delete=models.SET_NULL)
    dimension_values = models.JSONField(default=dict)
    key_figure_values = models.JSONField(default=dict)
    def __str__(self):
        parts = [str(self.layout)]
        if self.period: parts.append(str(self.period))
        return " | ".join(parts)
class Constant(models.Model):
    name = models.CharField(max_length=100, unique=True)
    value = models.FloatField()
    def __str__(self):
        return f"{self.name}={self.value}"
class SubFormula(models.Model):
    name = models.CharField(max_length=100, unique=True)
    expression = models.TextField()
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE)
    def __str__(self):
        return self.name
class Formula(models.Model):
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    loop_dimension = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    expression = models.TextField()
    def __str__(self):
        return self.name
class FormulaRun(models.Model):
    formula = models.ForeignKey(Formula, on_delete=models.CASCADE)
    run_at = models.DateTimeField(auto_now_add=True)
    preview = models.BooleanField(default=False)
    def __str__(self):
        return f"Run {self.id} of {self.formula.name}"
class FormulaRunEntry(models.Model):
    run = models.ForeignKey(FormulaRun, related_name='entries', on_delete=models.CASCADE)
    record = models.ForeignKey(PlanningRecord, on_delete=models.CASCADE)
    key = models.CharField(max_length=100)
    old_value = models.FloatField()
    new_value = models.FloatField()
    def __str__(self):
        return f"{self.record}: {self.key} {self.old_value} → {self.new_value}"
```

### `tests.py`
```python
from django.test import TestCase
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from bps.models import (
    Year, OrgUnit, Period, PlanningLayout, PlanningRecord,
    Constant, SubFormula, Formula, FormulaRun, FormulaRunEntry
)
from bps.formula_executor import FormulaExecutor
class FormulaExecutorTest(TestCase):
    def setUp(self):
        self.year = Year.objects.create(value=2025)
        self.org = OrgUnit.objects.create(name='OrgA')
        self.period = Period.objects.create(code='Jan', order=1)
        self.layout = PlanningLayout.objects.create(name='Layout1')
        PlanningRecord.objects.create(
            layout=self.layout, year=self.year, orgunit=self.org,
            key_figure_values={'k1':5}
        )
        PlanningRecord.objects.create(
            layout=self.layout, year=self.year, period=self.period,
            key_figure_values={'k1':3}
        )
        Constant.objects.create(name='CONST1', value=2)
        SubFormula.objects.create(
            name='SUB1', layout=self.layout,
            expression='[year, period].[k1] + CONST1'
        )
        period_ct = ContentType.objects.get_for_model(Period)
        self.formula = Formula.objects.create(
            layout=self.layout,
            name='FullTest',
            loop_dimension=period_ct,
            expression='[orgunit, period].[k1] = $SUB1 * CONST1'
        )
    def test_execute_and_audit(self):
        entries = FormulaExecutor(self.formula).execute()
        self.assertTrue(entries.exists())
        run = FormulaRun.objects.get(formula=self.formula)
        self.assertFalse(run.preview)
        self.assertEqual(entries.count(), FormulaRunEntry.objects.filter(run=run).count())
    def test_preview_does_not_persist(self):
        FormulaExecutor(self.formula, preview=True).execute()
        run = FormulaRun.objects.get(formula=self.formula, preview=True)
        self.assertTrue(run.preview)
        exists = PlanningRecord.objects.filter(layout=self.layout, orgunit=self.org, period=self.period).exists()
        self.assertFalse(exists)rec.key_figure_values.get('k1'), 3)
```

### `views.py`
```python
from django.shortcuts import render
```

