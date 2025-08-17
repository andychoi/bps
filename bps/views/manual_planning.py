# bps/views/manual_planning.py
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from django.urls import reverse
from urllib.parse import urlencode
import json

from bps.models.models_layout import PlanningLayoutYear, LayoutDimensionOverride
from bps.models.models_dimension import Service, OrgUnit
from bps.models.models import KeyFigure
from bps.models.models_workflow import PlanningSession


class ManualPlanningView(TemplateView):
    template_name = "bps/manual_planning.html"

    def get_context_data(self, layout_id, year_id, version_id, **kwargs):
        """
        Render the manual planning grid with:
          - bucket (period) metadata
          - row/header dimensions & choices
          - key figure metadata (display decimals)
          - header defaults (from layout-year AND optionally from a specific session)
          - API endpoints, with api_url pre-seeded to respect header defaults on first load
        """
        ctx = super().get_context_data(**kwargs)

        # ---- Resolve the PlanningLayoutYear we are editing ----
        ly = get_object_or_404(
            PlanningLayoutYear,
            layout_id=layout_id,
            year_id=year_id,
            version_id=version_id,
        )

        # ---- Period buckets (monthly grouping for columns) ----
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
        all_dims_qs = ly.layout.dimensions.select_related("content_type").order_by("order")
        header_dims_qs = all_dims_qs.filter(is_header=True)
        row_dims_qs = all_dims_qs.filter(is_row=True)
        column_dims_qs = all_dims_qs.filter(is_column=True)

        def _choices_for(dim):
            Model = dim.content_type.model_class()
            qs = Model.objects.all()

            # Apply per-year overrides (IDs or codes)
            ov = LayoutDimensionOverride.objects.filter(layout_year=ly, dimension=dim).first()
            if ov and ov.allowed_values:
                pks = [v for v in ov.allowed_values if isinstance(v, int)]
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
                out.append(
                    {
                        "key": ld.content_type.model,  # e.g. "orgunit"
                        "label": str(label),
                        "choices": _choices_for(ld),
                    }
                )
            return out

        drivers_for_header = _driver_payload(header_dims_qs)
        drivers_for_rows = _driver_payload(row_dims_qs)
        drivers_for_columns = _driver_payload(column_dims_qs)

        # ---- Default header selections from persisted layout-year config ----
        header_defaults = {}
        if isinstance(ly.header_dims, dict):
            header_keys = {d["key"] for d in drivers_for_header}
            for k, v in (ly.header_dims or {}).items():
                if k in header_keys:  # only keep keys that exist in current header dims
                    header_defaults[k] = v

        # ---- If launched from a specific PlanningSession, fold in its header slice ----
        # e.g., seed 'orgunit' header selection from the session
        sess_id = self.request.GET.get("session")
        if sess_id:
            sess = get_object_or_404(PlanningSession, pk=sess_id)
            if sess.scenario.layout_year_id == ly.id:
                header_models = set(
                    header_dims_qs.values_list("content_type__model", flat=True)
                )
                # Only set if this dimension is actually a header in the current layout config
                if "orgunit" in header_models:
                    header_defaults["orgunit"] = sess.org_unit_id

        # ---- Key figures for this layout (order respected) ----
        pkf_qs = ly.layout.key_figures.select_related("key_figure").order_by(
            "display_order", "id"
        )
        kf_codes = [pkf.key_figure.code for pkf in pkf_qs]

        # Per-key-figure UI precision (display_decimals) and year-dependency for cells & totals
        kf_meta = {}
        for pkf in pkf_qs:
            kf_meta[pkf.key_figure.code] = {
                "decimals": pkf.key_figure.display_decimals,
                "is_year_dependent": pkf.is_yearly
            }

        # ---- Lookup data for common dims (used if they appear as row dims) ----
        services = list(
            Service.objects.filter(is_active=True).values("code", "name")
        )
        org_units = list(
            OrgUnit.objects.filter(
                id__in=PlanningSession.objects.filter(
                    scenario__layout_year=ly
                ).values_list("org_unit_id", flat=True)
            ).values("code", "name")
        )

        # ---- Optional row grouping (when group_priority is set on row dims) ----
        grouping_dims_qs = (
            all_dims_qs.filter(is_row=True, group_priority__isnull=False).order_by(
                "group_priority"
            )
        )

        def _field_for_key(key: str) -> str:
            if key == "orgunit":
                return "org_unit_code"
            if key == "service":
                return "service_code"
            return f"{key}_code"

        row_field_candidates = {_field_for_key(d["key"]) for d in drivers_for_rows}

        if grouping_dims_qs.exists():
            configured_fields = [
                _field_for_key(ld.content_type.model) for ld in grouping_dims_qs
            ]
            row_group_fields = [
                f for f in configured_fields if f in row_field_candidates
            ]
        else:
            row_group_fields = []  # grouping OFF unless explicitly configured

        row_group_start_open = bool(
            getattr(ly, "group_start_open", getattr(ly.layout, "group_start_open", False))
        )

        # ---- Build initial grid API URL with layout_year + header_* selections
        #      so the first load already respects the slice (esp. when coming from a Session)
        params = {"layout_year": ly.pk}
        for k, v in (header_defaults or {}).items():
            if v is not None and v != "":
                params[f"header_{k}"] = v
        api_url = f"{reverse('bps_api:planning_grid')}?{urlencode(params)}"

        # ---- Compose context for template/JS ----
        ctx.update(
            {
                "layout_year": ly,

                # Column buckets and key figure metadata
                "buckets_js": json.dumps(buckets_js),
                "kf_codes": json.dumps(kf_codes),
                "kf_meta_js": json.dumps(kf_meta),

                # Drivers split by placement
                "header_drivers": drivers_for_header,  # for rendering in template
                "header_drivers_js": json.dumps(drivers_for_header),  # for client JS
                "row_drivers": drivers_for_rows,
                "row_drivers_js": json.dumps(drivers_for_rows),
                "column_drivers": drivers_for_columns,
                "column_drivers_js": json.dumps(drivers_for_columns),

                # Header defaults (already merged with Session, if any)
                "header_defaults_js": json.dumps(header_defaults or {}),

                # API endpoints
                "api_url": api_url,  # GET grid data; pre-seeded with layout_year + header_*
                "update_url": reverse("bps_api:planning_grid_update"),  # PATCH/POST updates

                # Lookup data for row dims
                "services_js": json.dumps(services),
                "org_units_js": json.dumps(org_units),

                # Row grouping config
                "row_group_fields_js": json.dumps(row_group_fields),
                "row_group_start_open_js": json.dumps(row_group_start_open),
            }
        )
        return ctx