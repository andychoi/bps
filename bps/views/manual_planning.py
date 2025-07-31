#. views/manual_planning.py
from django.views.generic import TemplateView
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from bps.models.models import PlanningLayoutYear, Year, Version, Period
import json

class ManualPlanningSelectView(TemplateView):
    template_name = 'bps/manual_planning_select.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['layouts'] = PlanningLayoutYear.objects.select_related('layout','year','version')
        return ctx

class ManualPlanningView(TemplateView):
    template_name = "bps/manual_planning.html"

    def get_context_data(self, layout_id, year_id, version_id, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ly = get_object_or_404(
            PlanningLayoutYear,
            layout_id=layout_id,
            year_id=year_id,
            version_id=version_id,
        )

        # pick your “monthly” grouping
        grouping = ly.period_groupings.filter(months_per_bucket=1).first()
        raw_buckets = grouping.buckets()  # [{code,name,periods(model instances)}, …]

        # build a JSON-safe version (just use period.code)
        buckets_js = []
        for b in raw_buckets:
            buckets_js.append({
                "code":    b["code"],
                "name":    b["name"],
                "periods": [p.code for p in b["periods"]],
            })

        # drivers, kf_codes etc. (unchanged)…

        api_url    = reverse("bps_api:bps_planning_pivot")
        update_url = reverse("bps_api:bps_planning_grid_update")

        ctx.update({
            "layout_year": ly,
            "buckets_js":  json.dumps(buckets_js),
            "kf_codes":    json.dumps([kf.code for kf in ly.layout.key_figures.all()]),
            "api_url":     api_url,
            "update_url":  update_url,
            # …drivers as before, but JSON-dumped similarly if you use them in JS
        })
        return ctx