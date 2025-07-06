# bps/formula_executor.py
import re
import ast
import operator
from decimal import Decimal
from typing import Dict, Any
from django.apps import apps
from bps.models import (
    PlanningFact, Formula, Constant, SubFormula,
    FormulaRun, FormulaRunEntry, ConversionRate, UnitOfMeasure, PlanningSession
)

class FormulaExecutor:
    def __init__(self, formula: Formula, session: PlanningSession, period: str, preview: bool = False):
        self.formula = formula
        self.layout = formula.layout
        self.loop_dimension = formula.loop_dimension.model_class()
        self.base_expr = formula.expression
        self.preview = preview
        self.session = session
        self.period = period

    def execute(self):
        # create run log
        self.run = FormulaRun.objects.create(formula=self.formula, preview=self.preview)
        for loop_value in self.loop_dimension.objects.all():
            self._apply_formula(loop_value)
        return self.run.entries.all()

    def _apply_formula(self, loop_value):
        expr = self._expand_subformulas(self.base_expr)
        expr = self._replace_constants(expr)
        target_expr, source_expr = map(str.strip, expr.split('='))
        target_key_figure, target_dims = self._parse_target_expr(target_expr, loop_value)
        replaced_expr = self._replace_keys_with_values(source_expr, loop_value)

        result = self._safe_eval(replaced_expr)

        record = self._get_fact_record(self.session, self.period, target_dims, create_if_missing=not self.preview)

        old_val = self._get_current_value(record, target_key_figure)

        if not self.preview:
            self._assign_result_to_record(record, target_key_figure, result)

        FormulaRunEntry.objects.create(
            run=self.run,
            record=record,
            key=target_key_figure,
            old_value=old_val,
            new_value=result
        )

    def _expand_subformulas(self, expr: str) -> str:
        def repl(m):
            name = m.group(1)
            sub = SubFormula.objects.get(name=name, layout=self.layout)
            return f"({self._expand_subformulas(sub.expression)})"
        return re.sub(r"\$(\w+)", repl, expr)

    def _replace_constants(self, expr: str) -> str:
        def repl(m):
            const = Constant.objects.get(name=m.group(0))
            return str(const.value)
        return re.sub(r"\b[A-Z_][A-Z0-9_]*\b", repl, expr)

    def _parse_target_expr(self, expr: str, loop_value) -> (str, dict):
        pattern = r"\[(.*?)\]\.\?\[(.*?)\]"
        m = re.match(pattern, expr)
        if not m:
            raise ValueError(f"Invalid target expression format: {expr}")
        dims, kf = m.groups()
        dims_dict = {}
        for d in dims.split(','):
            dim_name, dim_val = d.split('=')
            dim_name = dim_name.strip()
            dim_val = dim_val.strip()
            if dim_val == "$LOOP":
                dim_val = loop_value.pk
            else:
                dim_val = int(dim_val)
            dims_dict[dim_name] = dim_val
        return kf.strip(), dims_dict

    def _replace_keys_with_values(self, expr: str, loop_value) -> str:
        pattern = r"\[(.*?)\]\.\?\[(.*?)\]"

        def repl(m):
            dims, k = m.groups()
            dims_dict = {}
            for d in dims.split(','):
                dim_name, dim_val = d.split('=')
                dim_name = dim_name.strip()
                dim_val = dim_val.strip()
                if dim_val == "$LOOP":
                    dim_val = loop_value.pk
                else:
                    dim_val = int(dim_val)
                dims_dict[dim_name] = dim_val

            fact = self._get_fact_record(self.session, self.period, dims_dict)
            if not fact:
                return "0"

            if k == 'amount':
                return str(fact.amount)
            elif k == 'quantity':
                return str(fact.quantity)
            elif fact.other_key_figure == k:
                return str(fact.other_value or 0)
            else:
                return "0"

        return re.sub(pattern, repl, expr)

    def _safe_eval(self, expr: str) -> Decimal:
        ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
        }
        def _eval(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, Decimal)):
                return Decimal(str(node.value))
            if isinstance(node, ast.Num):
                return Decimal(str(node.n))
            if isinstance(node, ast.BinOp):
                return ops[type(node.op)](_eval(node.left), _eval(node.right))
            if isinstance(node, ast.UnaryOp):
                return ops[type(node.op)](_eval(node.operand))
            raise ValueError("Unsupported expression")
        node = ast.parse(expr, mode='eval').body
        return round(_eval(node), 4)

    def _get_fact_record(self, session, period, dims: dict, create_if_missing=False):
        rec = PlanningFact.objects.filter(
            session=session,
            period=period,
            row_values=dims
        ).first()
        if not rec and create_if_missing:
            rec = PlanningFact.objects.create(
                request=self.run.formula,
                session=session,
                period=period,
                row_values=dims
            )
        return rec

    def _get_current_value(self, record, key_figure):
        if key_figure == 'amount':
            return record.amount
        elif key_figure == 'quantity':
            return record.quantity
        elif record.other_key_figure == key_figure:
            return record.other_value or 0
        else:
            return 0

    def _assign_result_to_record(self, record, key_figure, result):
        if key_figure == 'amount':
            record.amount = result
            record.amount_uom = UnitOfMeasure.objects.get_or_create(code='USD')[0]
        elif key_figure == 'quantity':
            record.quantity = result
            record.quantity_uom = UnitOfMeasure.objects.get_or_create(code='EA')[0]
        else:
            record.other_key_figure = key_figure
            record.other_value = result
        record.save()