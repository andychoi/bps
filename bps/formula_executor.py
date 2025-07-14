# formula_executor.py
import re, ast, operator, itertools
from decimal import Decimal
from typing import Any, Dict, List
from django.apps import apps
from django.db.models import Sum, Avg, Min, Max, Q
from bps.models import (
    PlanningFact, Formula, Constant, SubFormula,
    FormulaRun, FormulaRunEntry, ReferenceData, Period
)

# Extendable aggregation functions
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
        # ContentType model abbreviations for looping dims
        self.dim_cts = list(formula.dimensions.all())

    def execute(self):
        # create a FormulaRun record
        self.run = FormulaRun.objects.create(formula=self.formula,
                                             preview=self.preview)
        # build loops over each dimension
        loops = []
        for ct in self.dim_cts:
            Model = ct.model_class()
            loops.append([(ct, obj) for obj in Model.objects.all()])

        # iterate all combinations
        for combo in itertools.product(*loops):
            dims_map = {ct.model: inst for ct,inst in combo}
            self._apply(dims_map)

        return self.run.entries.all()

    def _apply(self, dims_map: Dict[str,Any]):
        # prepare expression
        expr = self.formula.expression
        expr = self._expand_subformulas(expr)
        expr = self._replace_reference_data(expr, dims_map)
        expr = self._replace_constants(expr)
        expr = self._rewrite_conditionals(expr)

        # split LHS and RHS
        tgt, src = map(str.strip, expr.split('=',1))
        key_fig, tgt_dims = self._parse_ref(tgt, dims_map)

        # replace inline refs and evaluate
        src_eval = self._replace_refs_with_values(src, dims_map)
        result   = self._safe_eval(src_eval, dims_map)

        # get or create target record
        rec = self._get_record(key_fig, tgt_dims, create=not self.preview)
        old = getattr(rec, key_fig, 0)
        if not self.preview:
            setattr(rec, key_fig, result)
            rec.save()

        # log entry
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

    # conditional helpers
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
        # build namespace including new FOX functions
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
        # original aggregation or direct fetch
        return self._aggregate_or_fetch_for_period(kf, fkwargs, self.period)

    def _aggregate_or_fetch_for_period(self, kf: str, fkwargs: Dict[str,Any], period_code: str) -> Decimal:
        # handle SUM:, AVG:, etc.
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
        # direct fetch
        rec = PlanningFact.objects.filter(
            session=self.session,
            period__code=period_code,
            key_figure__code=kf,
            **{dim:inst for dim,inst in fkwargs.items()}
        ).first()
        return rec.value if rec else Decimal('0')

    def _shift(self, kf: str, offset: Any, dims_map: Dict[str,Any]) -> Decimal:
        # shift the period by offset and fetch
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
        # override one or more dimensions, then fetch
        dims = base_dims.copy()
        for dim_name, val in overrides.items():
            try:
                inst = apps.get_model('bps', dim_name).objects.get(pk=int(val))
                dims[dim_name] = inst
            except Exception:
                continue
        return self._aggregate_or_fetch_for_period(kf, dims, self.period)
