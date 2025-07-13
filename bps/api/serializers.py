from rest_framework import serializers
from bps.models import PlanningFact, Period

class PlanningFactSerializer(serializers.ModelSerializer):
    org_unit   = serializers.SerializerMethodField()
    service    = serializers.SerializerMethodField()
    key_figure = serializers.SerializerMethodField()
    period     = serializers.SerializerMethodField()

    class Meta:
        model  = PlanningFact
        fields = ["id","value","ref_value","org_unit","service","key_figure","period"]

    def get_org_unit(self, obj):
        return {"id": obj.org_unit.id, "name": obj.org_unit.name}

    def get_service(self, obj):
        return obj.service and {"id": obj.service.id, "name": obj.service.name}

    def get_key_figure(self, obj):
        return {"id": obj.key_figure.id, "code": obj.key_figure.code}

    def get_period(self, obj):
        return {"id": obj.period.id, "code": obj.period.code, "name": obj.period.name}

class PlanningFactPivotRowSerializer(serializers.Serializer):
    org_unit   = serializers.CharField()
    service    = serializers.CharField(allow_null=True)
    key_figure = serializers.CharField()
    # Dynamically add month fields:
    def to_representation(self, instance):
        return instance