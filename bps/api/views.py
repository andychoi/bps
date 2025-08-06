# bps/api/views.py
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.permissions import IsAuthenticated, AllowAny

# import the layout‐year model
from bps.models.models_layout import PlanningLayoutYear
from bps.models.models import PlanningFact, Version

from .serializers import PlanningFactPivotRowSerializer
from .utils import pivot_facts_grouped

class PlanningFactPivotedAPIView(APIView):
    permission_classes = [AllowAny]
    renderer_classes   = [JSONRenderer]   # JSON only, no HTML render

    def get(self, request):
        ly_pk = request.query_params.get("layout")
        if not ly_pk:
            return Response({"error": "Missing layout parameter"}, status=400)

        # 1) Fetch all facts in one hit, pulling back only the fields we need
        qs = PlanningFact.objects.filter(
            session__scenario__layout_year_id=ly_pk
        ).select_related(
            "org_unit", "service", "period", "key_figure"
        ).values(
            "org_unit__name",
            "service__name",
            "period__code",
            "key_figure__code",
            "value",
        )

        # 2) Pivot in pure Python, operating on simple dicts not full models
        rows = {}
        for f in qs:
            org   = f["org_unit__name"]
            svc   = f["service__name"] or None
            key   = (org, svc)
            row   = rows.setdefault(key, {
                "org_unit": org,
                "service":  svc,
            })
            col   = f"{f['period__code']}_{f['key_figure__code']}"
            row[col] = float(f["value"])

        return Response(list(rows.values()))
    
class PlanningFactPivotedAPIView_OLD(APIView):
    permission_classes = [AllowAny]
    renderer_classes   = [JSONRenderer] 

    def get(self, request):
        # 1) lookup layout-year
        ly_pk = request.query_params.get("layout")
        if not ly_pk:
            return Response({"error": "Missing layout parameter"}, status=400)
        ly = get_object_or_404(PlanningLayoutYear, pk=ly_pk)

        # 2) base queryset: always filter by session → layout_year
        facts = PlanningFact.objects.filter(session__scenario__layout_year=ly)

        # 3) optional version filter
        version_code = request.query_params.get("version")
        if version_code:
            facts = facts.filter(version__code=version_code)

        # 4) build the set of valid driver keys from your layout-year
        #    these are the content_type.model names for dimensions marked is_row=True
        valid_driver_keys = {
            ld.content_type.model
            for ld in ly.layout_dimensions.filter(is_row=True)
        }

        # 5) apply any driver_* filters dynamically
        for param, val in request.query_params.items():
            if not param.startswith("driver_"):
                continue
            driver_key = param.replace("driver_", "", 1)  # e.g. "Position" or "Service"
            # only apply if it matches one of our row-dimensions
            if driver_key not in valid_driver_keys:
                continue
            # filter by JSON‐key exists, then contains the specific value
            facts = (
                facts
                .filter(extra_dimensions_json__has_key=driver_key)
                .filter(extra_dimensions_json__contains={driver_key: val})
            )

        # 6) pivot & serialize
        use_ref = request.query_params.get("ref") == "1"
        pivoted = pivot_facts_grouped(facts, use_ref_value=use_ref)
        return Response(pivoted)
        # serializer = PlanningFactPivotRowSerializer(pivoted, many=True)
        # return Response(serializer.data)