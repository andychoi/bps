# bps/formula_executor.py
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
        # create run log
        self.run = FormulaRun.objects.create(formula=self.formula, preview=self.preview)
        # iterate loop dimension
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
        """
        Replace dimensional key references [Dim1,Dim2].[k] with actual numeric values from PlanningRecord.
        """
        pattern = r"\[(.*?)\]\.\?\[(.*?)\]"
        def repl(m):
            dims, k = m.groups()
            filter_kwargs = {}
            for d in dims.split(','):
                d = d.strip()
                Model = apps.get_model('bps', d.capitalize())
                # find the field on PlanningRecord that FK to this Model
                field_name = None
                for f in PlanningRecord._meta.get_fields():
                    if getattr(f, 'related_model', None) == Model:
                        field_name = f.name
                        break
                if not field_name:
                    raise ValueError(f"No FK on PlanningRecord for dimension {d}")
                # assign filter value
                if Model == self.loop_dimension:
                    filter_kwargs[field_name] = loop_value
                else:
                    filter_kwargs[field_name] = self._resolve_dimension_value(d)
            rec = self._get_record_by_key({'filter': filter_kwargs, 'k': k})
            return str(rec.key_figure_values.get(k, 0) if rec else 0)
        return re.sub(pattern, repl, expr)(pattern, repl, expr)

    def _safe_eval(self, expr: str) -> float:
        """
        Safely evaluate arithmetic expressions with +, -, *, /, **
        """
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
        """
        Parse target reference [Dim1,Dim2].[k] into filter kwargs mapping actual FK fields to values.
        """
        m = re.match(r"\[(.*?)\]\.\?\[(.*?)\]", expr)
        if not m:
            raise ValueError(f"Invalid expression format: {expr}")
        dims, k = m.groups()
        filter_kwargs = {}
        for d in dims.split(','):
            d = d.strip()
            Model = apps.get_model('bps', d.capitalize())
            # find FK field on PlanningRecord
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

    def _resolve_dimension(self, rec: PlanningRecord, dim_name: str, loop_value=None):
        """
        Return the actual dimension value (FK instance) for this record:
          1) if there's a real FK field, use rec.<field>
          2) else, look in rec.dimension_values[dim_name] as a PK
        """
        # first try real FK
        for f in PlanningRecord._meta.get_fields():
            if getattr(f, 'related_model', None):
                if f.related_model.__name__.lower() == dim_name.lower():
                    return getattr(rec, f.name)

        # fallback to JSON
        pk = rec.dimension_values.get(dim_name)
        Model = apps.get_model('bps', dim_name)
        return Model.objects.filter(pk=pk).first() if pk is not None else None
    

    def _get_record_by_key(self, key: Dict[str,Any], create_if_missing=False):
        qs = PlanningRecord.objects.filter(layout=self.layout)
        json_filters = {}

        for dim, val in key['filter'].items():
            # find an actual FK field
            fk_field = None
            for f in PlanningRecord._meta.get_fields():
                if getattr(f, 'related_model', None) and f.related_model == val.__class__:
                    fk_field = f.name
                    break

            if fk_field:
                qs = qs.filter(**{fk_field: val})
            else:
                # assume JSON-stored dimension
                json_filters[dim] = getattr(val, 'pk', val)

        if json_filters:
            # e.g. dimension_values__PriceType=3
            for dim, pk in json_filters.items():
                qs = qs.filter(**{f"dimension_values__{dim}": pk})

        rec = qs.first()
        if not rec and create_if_missing:
            # build new record
            rec = PlanningRecord(layout=self.layout,
                                 dimension_values={},
                                 key_figure_values={})
            # assign FKs & JSON dims
            for dim, val in key['filter'].items():
                fk_field = None
                for f in PlanningRecord._meta.get_fields():
                    if getattr(f, 'related_model', None) and f.related_model == val.__class__:
                        fk_field = f.name
                        break
                if fk_field:
                    setattr(rec, fk_field, val)
                else:
                    rec.dimension_values[dim] = getattr(val, 'pk', val)

            rec.save()
        return rec
