from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from django.urls import reverse
from bps.models.models import PlanningLayoutYear
from bps.models.models_dimension import Service, OrgUnit
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

        # periods / buckets
        grouping    = ly.period_groupings.filter(months_per_bucket=1).first()
        raw_buckets = grouping.buckets()
        buckets_js  = [
            {"code": b["code"], "name": b["name"], "periods": [p.code for p in b["periods"]]}
            for b in raw_buckets
        ]

        # drivers
        # This list is for the Django template loop to build filters
        drivers_for_template = []
        # This list will be serialized into JSON for Tabulator
        drivers_for_js = []

        # Separate the core dimensions (org_unit, service) from the dynamic ones
        dynamic_dims = ly.layout_dimensions.filter(is_row=True).order_by("order")

        for ld in dynamic_dims:
            Model = ld.content_type.model_class()
            qs    = Model.objects.all()
            # Use the model's verbose_name or a custom label field if available
            label = getattr(Model._meta, 'verbose_name', ld.content_type.model.title())

            driver_data = {
                "key":     ld.content_type.model, # e.g., 'skill', 'position'
                "label":   label,
                "choices": [{"id": o.pk, "name": str(o)} for o in qs],
            }
            drivers_for_template.append(driver_data)
            drivers_for_js.append(driver_data)


        # service & org-unit lookups
        services = list(Service.objects.filter(is_active=True).values("code", "name"))
        org_units = list(OrgUnit.objects.values("code", "name"))

        ctx.update({
            "layout_year": ly,
            "buckets_js":  json.dumps(buckets_js),
            "kf_codes":    json.dumps([kf.code for kf in ly.layout.key_figures.order_by("display_order")]),
            "drivers_for_template": drivers_for_template, # For the template loop
            "drivers_js":  json.dumps(drivers_for_js),   # For the script block
            "api_url":     reverse("bps_api:planning_pivot"),
            "update_url":  reverse("bps_api:planning_grid_update"),
            "services_js": json.dumps(services),
            "org_units_js":json.dumps(org_units),
        })
        return ctx