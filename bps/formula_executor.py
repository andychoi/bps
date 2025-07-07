import re, ast, operator, itertools
from decimal import Decimal
from typing import Any, Dict, List
from django.apps import apps
from django.db.models import Sum, Avg, Min, Max, Q
from bps.models import (
    PlanningFact, Formula, Constant, SubFormula,
    FormulaRun, FormulaRunEntry, ReferenceData
)

# Mapping for aggregation helpers
_AGG_FUNCS = {
    'SUM': Sum, 'AVG': Avg, 'MIN': Min, 'MAX': Max
}

"""
-- Top-down allocation:
FOREACH OrgUnit, Service:
  [OrgUnit=$OrgUnit,Service=$Service]?.[amount] =
    SUM:Revenue([Year=$REFYR,OrgUnit=$OrgUnit]) * ALLOC_RATE

-- Conditional example:
FOREACH OrgUnit:
  [OrgUnit=$OrgUnit]?.[amount] =
    IF([OrgUnit=$OrgUnit]?.[quantity] > 100, 1000, 500)

-- Cross-period growth:
FOREACH OrgUnit,Product:
  [OrgUnit=$OrgUnit,Product=$Product]?.[amount] =
    [Year=$REFYR,OrgUnit=$OrgUnit,Product=$Product]?.[amount] * (1 + GROWTH_RATE)
"""
class FormulaExecutor:
    _re_refdata = re.compile(r"REF\('([^']+)'\s*,\s*([^\)]+)\)")
    def __init__(self, formula: Formula, session, period: str, preview: bool=False):
        self.formula = formula
        self.session = session
        self.period  = period
        self.preview = preview
        self.run     = None

        # Pre‐compile regexes
        self._re_subf = re.compile(r"\$(\w+)")
        self._re_const= re.compile(r"\b[A-Z_][A-Z0-9_]*\b")
        self._re_ref  = re.compile(r"\[(.*?)\]\.\?\[(.*?)\]")
        # Build list of dimension classes to loop over
        self.dim_cts = list(formula.dimensions.all())

    def execute(self):
        self.run = FormulaRun.objects.create(formula=self.formula,
                                             preview=self.preview)
        # Build all combinations of dimension values
        loops = []
        for ct in self.dim_cts:
            Model = ct.model_class()
            loops.append([(ct, obj) for obj in Model.objects.all()])
        for combo in itertools.product(*loops):
            # combo is list of (ContentType, instance)
            dims_map = {ct.model: inst for ct,inst in combo}
            self._apply(dims_map)
        return self.run.entries.all()

    def _apply(self, dims_map: Dict[str,Any]):
        expr = self.formula.expression
        expr = self._expand_subformulas(expr)
        expr = self._replace_reference_data(expr, dims_map)   
        expr = self._replace_constants(expr)
        # Handle IF and CASE by rewriting to Python calls
        expr = self._rewrite_conditionals(expr)
        # Split target=source
        tgt, src = map(str.strip, expr.split('=',1))
        key_fig, tgt_dims = self._parse_ref(tgt, dims_map)
        # Replace all references in the source side
        src_eval = self._replace_refs_with_values(src, dims_map)
        # Evaluate arithmetic + aggregates
        result = self._safe_eval(src_eval, dims_map)
        # Fetch or create the fact record
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
        # IF(cond, t, f) → __if__(cond, t, f)
        expr = re.sub(r"\bIF\(", "__if__(", expr)
        # CASE WHEN a THEN b WHEN c THEN d ELSE e END → __case__([...])
        def case_repl(m):
            body = m.group(1)
            return f"__case__([{body}])"
        expr = re.sub(r"\bCASE\s+(.*?)\s+END", case_repl, expr, flags=re.S)
        return expr

    def __if__(self, cond, tval, fval):
        return tval if cond else fval

    def __case__(self, arms: List[str]):
        # arms: ["WHEN a THEN b","WHEN c THEN d","ELSE e"]
        for arm in arms:
            if arm.strip().upper().startswith("WHEN"):
                _, cond, _, val = re.split(r"\s+", arm, maxsplit=3)
                if self._safe_eval(cond, {}):
                    return self._safe_eval(val, {})
            elif arm.strip().upper().startswith("ELSE"):
                return self._safe_eval(arm.split(None,1)[1], {})
        return Decimal('0')

    def _parse_ref(self, token: str, dims_map: Dict[str,Any]):
        # returns (key_figure, {dim_field: val,...})
        m = self._re_ref.match(token)
        dims, kf = m.groups()
        fldmap = {}
        for d in dims.split(','):
            name,val = d.split('=')
            name,val = name.strip(), val.strip()
            if val == "$LOOP":
                # find which dimension matches name
                inst = dims_map[name]
            else:
                # literal PK or code
                inst = apps.get_model('bps',name).objects.get(pk=int(val))
            fldmap[name.lower()] = inst
        return kf, fldmap

    def _replace_refs_with_values(self, expr: str, dims_map: Dict[str,Any]):
        # handle aggregations and normal cell refs
        def repl(m):
            dims, k = m.groups()
            # parse dims dict
            fkwargs = {}
            for d in dims.split(','):
                n,v = d.split('=')
                n,v = n.strip(), v.strip()
                if v == "$LOOP":
                    inst = dims_map[n]
                else:
                    inst = apps.get_model('bps',n).objects.get(pk=int(v))
                fkwargs[n.lower()] = inst
            # detect aggregation: e.g. SUM([OrgUnit=..]?.[amount])
            # we look ahead in expr for SUM(REF)
            # Simplest approach: mark __SUM__[dims][kf]
            return f"__ref__('{k}',{fkwargs})"
        return self._re_ref.sub(repl, expr)

    def _safe_eval(self, expr: str, dims_map: Dict[str,Any]) -> Decimal:
        """
        Evaluate arithmetic, conditional and aggregation calls in a safe AST.
        """
        # Prepare eval namespace
        ns = {
            '__if__': self.__if__,
            '__case__': self.__case__,
            '__ref__': lambda k, kwargs: self._aggregate_or_fetch(k, kwargs),
            # allow basic python builtins if needed
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
        """
        If kf is an aggregation call, apply SUM/AVG/etc across 
        the filtered queryset of PlanningFact; otherwise fetch single value.
        """
        # detect if kf starts with SUM:,AVG: etc
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
        # else single record fetch
        rec = PlanningFact.objects.filter(
            session=self.session,
            period=self.period,
            key_figure__code=kf,
            **{f"{dim}":inst for dim,inst in fkwargs.items()}
        ).first()
        return rec.value if rec else Decimal('0')

    def _get_record(self, kf: str, dims: Dict[str,Any], create=False):
        """
        Fetch or create the PlanningFact record and return it.
        """
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
        """
        Finds REF('RefName', Dim=Value,…) calls and replaces them
        with a literal number from ReferenceData.fetch_reference_fact.
        """
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
            # assume it's sum:
            return str(agg.get('value__sum') or 0)
        return self._re_refdata.sub(repl, expr)    