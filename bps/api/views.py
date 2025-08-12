# bps/api/views.py
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
import logging
from math import ceil
from django.core.paginator import Paginator

# import the layout‐year model
from bps.models.models_layout import PlanningLayoutYear
from bps.models.models import PlanningFact, Version
from bps.models.models_workflow import PlanningSession

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

log = logging.getLogger(__name__)

class SessionFactsPageAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            # Tabulator remote sends ?page=&size= by default
            try:
                page = int(request.GET.get("page", 1))
            except (TypeError, ValueError):
                page = 1
            try:
                size = int(request.GET.get("size", 25))
            except (TypeError, ValueError):
                size = 25
            if size <= 0:
                size = 25

            sess = get_object_or_404(PlanningSession, pk=pk)

            qs = (
                PlanningFact.objects
                .filter(session=sess)
                .select_related(
                    "period", "key_figure", "uom", "ref_uom",
                    "org_unit", "service", "account"
                )
                .order_by("period__order", "key_figure__code", "service__name")
            )

            paginator = Paginator(qs, size)
            page_obj  = paginator.get_page(page)

            rows = []
            for f in page_obj.object_list:
                # Safe number conversion (Decimal -> float)
                def f2(x):
                    try:
                        return float(x)
                    except Exception:
                        return None

                rows.append({
                    "id": f.id,
                    "org_unit":   getattr(f.org_unit, "name", None),
                    "service":    getattr(f.service, "name", None),
                    "account":    getattr(f.account, "name", None),
                    "period":     getattr(f.period, "code", None),
                    "key_figure": getattr(f.key_figure, "code", None),
                    "value":      f2(f.value),
                    "uom":        getattr(f.uom, "code", None),
                    "ref_value":  f2(f.ref_value),
                    "ref_uom":    getattr(f.ref_uom, "code", None),
                    "extra_dimensions": f.extra_dimensions_json or {},
                })

            return Response({
                # Tabulator remote expects these keys by default
                "last_page": max(1, paginator.num_pages),
                "last_row": paginator.count,
                "data": rows,
            })
        except Exception as e:
            # Log full stack trace to server logs; return readable JSON to client
            log.exception("SessionFactsPageAPIView failed")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )