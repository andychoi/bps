from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from bps.models import PlanningLayoutYear, PlanningFact, KeyFigure, Period
from .serializers import PlanningFactSerializer
from django.shortcuts import get_object_or_404

class PlanningGridAPIView(APIView):
    def get(self, request):
        layout_id = request.query_params.get("layout")
        if not layout_id:
            return Response({"error": "Missing layout param"}, status=status.HTTP_400_BAD_REQUEST)

        layout_year = get_object_or_404(PlanningLayoutYear, pk=layout_id)
        facts = (
            PlanningFact.objects
            .filter(session__layout_year=layout_year)
            .select_related("period", "key_figure", "org_unit", "service")
        )

        serializer = PlanningFactSerializer(facts, many=True)
        return Response(serializer.data)

class PlanningGridBulkUpdateAPIView(APIView):
    """
    Expects JSON: { updates: [ { id: <fact_id>, field: "M01"..., value: 123.4 }, … ] }
    """
    def patch(self, request):
        updates = request.data.get("updates")
        if not isinstance(updates, list):
            return Response({"error":"Expected list"}, status=status.HTTP_400_BAD_REQUEST)
        count = 0
        for upd in updates:
            fid   = upd.get("id")
            field = upd.get("field")
            val   = upd.get("value")
            if fid and field in ["value","ref_value"]:
                PlanningFact.objects.filter(id=fid).update(**{field: val})
                count += 1
        return Response({"updated": count}, status=status.HTTP_200_OK)