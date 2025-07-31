from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from bps.models.models import PlanningFact, Version
from .serializers import PlanningFactPivotRowSerializer
from .utils import pivot_facts_grouped

class PlanningFactPivotedAPIView(APIView):
    # permission_classes = [IsAuthenticated]
    # FIXME
    permission_classes = [AllowAny]

    def get(self, request):
        layout_year_id = request.query_params.get("layout")
        if not layout_year_id:
            return Response({"error": "Missing layout parameter"}, status=400)

        facts = PlanningFact.objects.filter(session__scenario__layout_year_id=layout_year_id)

        # Optional version filter
        version_code = request.query_params.get("version")
        if version_code:
            try:
                facts = facts.filter(version__code=version_code)
            except Version.DoesNotExist:
                return Response({"error": "Invalid version code"}, status=400)

        # Optional extra_dimensions_json filtering
        for k, v in request.query_params.items():
            if k.startswith("driver_"):
                driver_key = k.replace("driver_", "")
                facts = facts.filter(extra_dimensions_json__has_key=driver_key).filter(extra_dimensions_json__contains={driver_key: v})

        use_ref_value = request.query_params.get("ref") == "1"
        pivoted = pivot_facts_grouped(facts, use_ref_value=use_ref_value)
        serializer = PlanningFactPivotRowSerializer(pivoted, many=True)
        return Response(serializer.data)