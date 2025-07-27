# bps/api/serializers.py
from rest_framework import serializers
from bps.models.models import PlanningFact, PlanningSession, OrgUnit, UserMaster
from bps.models.models import OrgUnit


class PlanningFactSerializer(serializers.ModelSerializer):
    org_unit = serializers.CharField(source='org_unit.name', read_only=True)
    service  = serializers.CharField(source='service.name',  read_only=True)

    class Meta:
        model  = PlanningFact
        fields = [
            'id','org_unit','service',
            'period','key_figure','value','ref_value'
        ]
        read_only_fields = ['id','org_unit','service','period','key_figure']

class PlanningFactCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PlanningFact
        fields = ['service','value','ref_value']


class OrgUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OrgUnit
        fields = ['id','name','head_user']        