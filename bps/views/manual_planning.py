# bps/views/manual_planning.py
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from django.urls import reverse
from bps.models.models_layout import PlanningLayoutYear, LayoutDimensionOverride
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
        # ---- Split layout dimensions by placement (template-level) ----
        all_dims_qs    = ly.layout.dimensions.select_related("content_type").order_by("order")
        header_dims_qs = all_dims_qs.filter(is_header=True)
        row_dims_qs    = all_dims_qs.filter(is_row=True)

        def _choices_for(dim):
            Model = dim.content_type.model_class()
            qs = Model.objects.all()

            # Apply per-year overrides (IDs or codes)
            ov = LayoutDimensionOverride.objects.filter(layout_year=ly, dimension=dim).first()
            if ov and ov.allowed_values:
                pks   = [v for v in ov.allowed_values if isinstance(v, int)]
                codes = [v for v in ov.allowed_values if isinstance(v, str)]
                if pks:
                    qs = qs.filter(pk__in=pks)
                if codes and hasattr(Model, "code"):
                    qs = qs.filter(code__in=codes)

            return [{"id": o.pk, "name": str(o)} for o in qs]

        def _driver_payload(qs):
            out = []
            for ld in qs:
                Model = ld.content_type.model_class()
                label = getattr(Model._meta, "verbose_name", ld.content_type.model.title())
                out.append({
                    "key":     ld.content_type.model,     # e.g. "orgunit"
                    "label":   str(label),
                    "choices": _choices_for(ld),
                })
            return out

        drivers_for_header = _driver_payload(header_dims_qs)
        drivers_for_rows   = _driver_payload(row_dims_qs)

        # ---- Default header selections from persisted layout-year config ----
        header_defaults = {}
        if isinstance(ly.header_dims, dict):
            header_keys = {d["key"] for d in drivers_for_header}
            for k, v in ly.header_dims.items():
                if k in header_keys:          # only keep keys that exist in current header dims
                    header_defaults[k] = v

        # ---- Key figures for this layout (order respected) ----
        pkf_qs   = ly.layout.key_figures.select_related("key_figure").order_by("display_order", "id")
        kf_codes = [pkf.key_figure.code for pkf in pkf_qs]

        # Per-key-figure UI precision (display_decimals) for cells & totals
        # (If a KF code is missing here, the client should fall back to 2.)
        kf_meta = {
            k.code: {"decimals": k.display_decimals}
            for k in KeyFigure.objects.filter(code__in=kf_codes)
        }

        # ---- Lookup data for common dims (used if they appear as row dims) ----
        services = list(Service.objects.filter(is_active=True).values("code", "name"))
        org_units = list(OrgUnit.objects.values("code", "name"))

        # only group when row dims have a group_priority
        grouping_dims_qs = (
            all_dims_qs
            .filter(is_row=True, group_priority__isnull=False)
            .order_by("group_priority")
        )

        def _field_for_key(key: str) -> str:
            if key == "orgunit":
                return "org_unit_code"
            if key == "service":
                return "service_code"
            return f"{key}_code"

        row_field_candidates = {
            _field_for_key(d["key"]) for d in _driver_payload(row_dims_qs)
        }

        configured_fields = [_field_for_key(ld.content_type.model) for ld in grouping_dims_qs]
        row_group_fields = [f for f in configured_fields if f in row_field_candidates]
        # NOTE: if no priorities are set, row_group_fields will be [], so the JS won’t enable grouping.

        # Read "start open" off layout_year first, then layout, else default False
        row_group_start_open = bool(
            getattr(ly, "group_start_open", getattr(ly.layout, "group_start_open", False))
        )

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

                # "row_group_enabled": row_group_enabled,
                "row_group_fields_js": json.dumps(row_group_fields),
                "row_group_start_open_js": json.dumps(row_group_start_open),           
            }
        )
        return ctx