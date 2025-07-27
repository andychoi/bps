# api/utils.py
from collections import defaultdict, OrderedDict
from bps.models.models import Period

def pivot_facts_grouped(facts, use_ref_value=False):
    """
    Returns a list of dicts, each with:
      { "org_unit": ..., "service": ..., "key_figure": ...,
        "Jan": 123.4, "Feb": 98.7, … }
    """
    # build map: (org,service,key_figure) → {period_code → value}
    matrix = defaultdict(lambda: defaultdict(float))
    meta = {}
    for f in facts:
        key = (f.org_unit.name, (f.service.name if f.service else None), f.key_figure.code)
        val = float(f.ref_value if use_ref_value else f.value)
        matrix[key][f.period.code] += val
        meta[key] = {
            "org_unit":   f.org_unit.name,
            "service":    (f.service.name if f.service else None),
            "key_figure": f.key_figure.code,
        }
    # turn into list of ordered dicts
    periods = Period.objects.order_by("order").values_list("code", "name")
    out = []
    for key, row in matrix.items():
        entry = OrderedDict(meta[key])
        for code,name in periods:
            entry[name] = row.get(code, 0.0)
        out.append(entry)
    return out