# bps/api/views.py
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
import csv

from bps.models.models import PlanningFact, OrgUnit
from ..serializers import PlanningFactSerializer, PlanningFactCreateUpdateSerializer
from ..serializers import OrgUnitSerializer

class PlanningFactViewSet(viewsets.ModelViewSet):
    """
    Provides:
      * list:        GET    /api/facts/
      * retrieve:    GET    /api/facts/{id}/
      * create:      POST   /api/facts/
      * update:      PUT    /api/facts/{id}/
      * partial_update: PATCH /api/facts/{id}/
      * destroy:     DELETE /api/facts/{id}/
      * export:      GET    /api/facts/export/
    """
    queryset = PlanningFact.objects.select_related(
        'org_unit','service','period','key_figure'
    ).all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields   = ['org_unit__name','service__name']
    ordering_fields = ['period__order']
    
    def get_serializer_class(self):
        if self.action in ('create','update','partial_update'):
            return PlanningFactCreateUpdateSerializer
        return PlanningFactSerializer

    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        Return a CSV dump of the current filter/queryset
        """
        qs = self.filter_queryset(self.get_queryset())
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="facts.csv"'
        writer = csv.writer(resp)
        writer.writerow(['ID','OrgUnit','Service','Period','KeyFigure','Value','RefValue'])
        for f in qs:
            writer.writerow([
                f.id,
                f.org_unit.name,
                f.service.name if f.service else '',
                f.period.code,
                f.key_figure.code,
                f.value,
                f.ref_value,
            ])
        return resp
    
class OrgUnitViewSet(viewsets.ModelViewSet):
    """
    Provides endpoints for inline updating of OrgUnit.head_user:
      * list/retrieve (if you need them)
      * partial_update: PATCH /api/orgunits/{id}/
    """
    queryset = OrgUnit.objects.all()
    serializer_class = OrgUnitSerializer    