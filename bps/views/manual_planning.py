from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from django.urls import reverse
from bps.models.models_layout import PlanningLayoutYear
from bps.models.models_dimension import Service, OrgUnit
from bps.models.models import KeyFigure
import json


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

        # ---- Monthly grouping for columns (buckets) ----
        grouping = ly.period_groupings.filter(months_per_bucket=1).first()
        raw_buckets = grouping.buckets() if grouping else []
        buckets_js = [
            {
                "code": b["code"],
                "name": b["name"],
                "periods": [p.code for p in b["periods"]],
            }
            for b in raw_buckets
        ]

        # ---- Split layout dimensions by placement ----
        # Header selections: BW-BPS style fixed slice
        # Row (lead) columns: editable per-row dimensions
        all_dims_qs = ly.layout_dimensions.order_by("order")
        header_dims_qs = all_dims_qs.filter(is_header=True)
        row_dims_qs = all_dims_qs.filter(is_row=True, is_header=False)

        def _driver_payload(qs):
            """
            Build a generic payload for either header or row dimensions:
            [
              {
                key: "orgunit" | "service" | "position" | ... (content_type.model)
                label: readable label (Model.verbose_name or fallback),
                choices: [{id, name}]
              },
              ...
            ]
            """
            out = []
            for ld in qs:
                Model = ld.content_type.model_class()
                # NOTE: you can inject filter_criteria/allowed_values here later if needed
                qs_all = Model.objects.all()
                # label prefers model verbose_name; fallback to content_type.model title-cased
                label = getattr(Model._meta, "verbose_name", ld.content_type.model.title())
                out.append(
                    {
                        "key": ld.content_type.model,  # e.g. "orgunit", "service", "position", ...
                        "label": str(label),
                        "choices": [{"id": o.pk, "name": str(o)} for o in qs_all],
                    }
                )
            return out

        drivers_for_header = _driver_payload(header_dims_qs)
        drivers_for_rows = _driver_payload(row_dims_qs)

        # ---- Default header selections from persisted layout-year config ----
        header_defaults = {}
        if isinstance(ly.header_dims, dict):
            header_keys = {d["key"] for d in drivers_for_header}
            for k, v in ly.header_dims.items():
                # only keep keys that exist as header dims (ignore legacy/custom keys)
                if k in header_keys:
                    header_defaults[k] = v

        # ---- Key figures for this layout (order respected) ----
        pkf_qs = ly.layout.key_figures.order_by("display_order")
        kf_codes = [pkf.code for pkf in pkf_qs]

        # Per-key-figure UI precision (display_decimals) for cells & totals
        # (If a KF code is missing here, the client should fall back to 2.)
        kf_meta = {
            k.code: {"decimals": k.display_decimals}
            for k in KeyFigure.objects.filter(code__in=kf_codes)
        }

        # ---- Lookup data for common dims (used if they appear as row dims) ----
        services = list(Service.objects.filter(is_active=True).values("code", "name"))
        org_units = list(OrgUnit.objects.values("code", "name"))

        ctx.update(
            {
                "layout_year": ly,
                "buckets_js": json.dumps(buckets_js),
                "kf_codes": json.dumps(kf_codes),
                "kf_meta_js": json.dumps(kf_meta),  # NEW: { CODE: {decimals:int}, ... }

                # Drivers split by placement
                "header_drivers": drivers_for_header,                    # for rendering <select>s in template
                "header_drivers_js": json.dumps(drivers_for_header),     # for client JS logic
                "row_drivers": drivers_for_rows,
                "row_drivers_js": json.dumps(drivers_for_rows),
                "header_defaults_js": json.dumps(header_defaults),

                # API endpoints
                "api_url": reverse("bps_api:planning_grid"),             # /api/bps/grid/
                "update_url": reverse("bps_api:planning_grid_update"),   # /api/bps/grid-update/

                # Only needed if the corresponding dim is used as a row dim
                "services_js": json.dumps(services),
                "org_units_js": json.dumps(org_units),
            }
        )
        return ctx