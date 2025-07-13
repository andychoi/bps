from decimal import Decimal
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction

from bps.models import (
    PlanningLayoutYear,
    PlanningFact, Period, KeyFigure,
    OrgUnit, Service
)

class PlanningGridRowSerializer(serializers.Serializer):
    """ We’ll dynamically build each row as a dict """
    org_unit   = serializers.CharField()
    service    = serializers.CharField(allow_null=True)
    # period_XX_KF fields will be in .data

class PlanningGridView(APIView):
    """
    GET /api/bps_planning_grid?layout=<pk>
    """
    def get(self, request):
        ly_pk = request.query_params.get('layout')
        ly    = get_object_or_404(PlanningLayoutYear, pk=ly_pk)

        facts = PlanningFact.objects.filter(session__layout_year=ly)
        rows  = {}
        for f in facts:
            key = (f.org_unit.code, f.service.code if f.service else "")
            row = rows.setdefault(key, {
                "org_unit": f.org_unit.name,
                "service":  f.service.name if f.service else None,
            })
            col = f"period_{f.period.code}_{f.key_figure.code}"
            row[col] = float(f.value)

        return Response({"data": list(rows.values())})
        

class BulkUpdateSerializer(serializers.Serializer):
    layout  = serializers.IntegerField()
    updates = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField())
    )


class PlanningGridBulkUpdateView(APIView):
    """
    POST /api/bps_planning_grid_update
    {
      "layout": <pk>,
      "updates": [
         {
           "org_unit":"Division 1",
           "service":"Run",
           "period":"02",
           "key_figure":"FTE",
           "value":"5.5"
         }, …
      ]
    }
    """
    @transaction.atomic
    def post(self, request):
        data = BulkUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)

        ly = get_object_or_404(PlanningLayoutYear, pk=data.validated_data["layout"])
        errors = []

        for upd in data.validated_data["updates"]:
            try:
                org = OrgUnit.objects.get(name=upd["org_unit"])
                svc = Service.objects.get(name=upd["service"]) if upd["service"] else None
                per = Period.objects.get(code=upd["period"])
                kf  = KeyFigure.objects.get(code=upd["key_figure"])

                fact = PlanningFact.objects.get(
                    session__layout_year=ly,
                    org_unit=org, service=svc,
                    period=per, key_figure=kf
                )
                fact.value = Decimal(upd["value"])
                fact.save()
            except Exception as e:
                errors.append({"update": upd, "error": str(e)})

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)