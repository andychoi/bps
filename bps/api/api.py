from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.permissions import IsAuthenticated

from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response

from bps.models.models_layout import PlanningLayoutYear
from bps.models.models import PlanningFact, Period, KeyFigure, DataRequest
from bps.models.models_dimension import OrgUnit, Service
from bps.models.models_workflow import PlanningSession


class BulkUpdateSerializer(serializers.Serializer):
    layout  = serializers.IntegerField()
    updates = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField())
    )


class PlanningGridView(APIView):
    """
    GET /api/bps/grid/?layout=<layout_year_id>
    Returns a flat list of row-dicts for Tabulator, including:
      - org_unit, org_unit_code
      - service,  service_code
      - <each JSON row-dimension> + <that>_code
      - <period>_<key_figure> columns
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        ly_pk = request.query_params.get('layout')
        ly    = get_object_or_404(PlanningLayoutYear, pk=ly_pk)

        # 1) figure out all row-dimensions (including JSON ones like 'skill')
        row_dims = list(ly.layout_dimensions.filter(is_row=True))
        dim_keys = [ld.content_type.model for ld in row_dims]
        # for lookups
        dim_models = {
            ld.content_type.model: ld.content_type.model_class()
            for ld in row_dims
        }

        qs = (
            PlanningFact.objects
            .filter(session__scenario__layout_year=ly)
            .select_related('org_unit','service','period','key_figure')
        )

        rows = {}
        for fact in qs:
            org_code = fact.org_unit.code
            svc_code = fact.service.code if fact.service else ""
            # pull JSON dims from fact.extra_dimensions_json
            ed = fact.extra_dimensions_json or {}
            dim_codes = [ ed.get(k) for k in dim_keys ]
            # grouping key = tuple of org,svc + each dim code
            key = (org_code, svc_code, *dim_codes)

            # initialize row if first time
            if key not in rows:
                base = {
                    "org_unit":      fact.org_unit.name,
                    "org_unit_code": org_code,
                    "service":       fact.service.name if fact.service else None,
                    "service_code":  svc_code or None,
                }
                # for each JSON row-dimension, put display and code
                for dk in dim_keys:
                    code = ed.get(dk)
                    inst = dim_models[dk].objects.filter(pk=code).first() if code else None
                    base[dk] = str(inst) if inst else None
                    base[f"{dk}_code"] = code
                rows[key] = base

            # add the period_key_figure column
            col = f"{fact.period.code}_{fact.key_figure.code}"
            rows[key][col] = float(fact.value)

        return Response(list(rows.values()))


class PlanningGridBulkUpdateView(APIView):
    """
    POST/PATCH /api/bps/grid-update/
    Same as before; will pick up any JSON dims you include in the payload.
    """
    http_method_names = ["get","post","patch","options"]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        return self._handle(request)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        return self._handle(request)

    def _handle(self, request):
        data = BulkUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)

        ly = get_object_or_404(PlanningLayoutYear, pk=data.validated_data["layout"])
        errors, success = [], 0
        dr_by_sess = {}

        # reload row dimensions for lookup/validation
        row_dims = list(ly.layout_dimensions.filter(is_row=True))

        for upd in data.validated_data["updates"]:
            try:
                # core lookups
                org = OrgUnit.objects.get(code=upd["org_unit"])
                svc = Service.objects.get(code=upd.get("service")) if upd.get("service") else None
                per = Period.objects.get(code=upd["period"])
                kf  = KeyFigure.objects.get(code=upd["key_figure"])

                session = PlanningSession.objects.get(
                    scenario__layout_year=ly, org_unit=org
                )

                # collect extra dims
                extra = {}
                for ld in row_dims:
                    dk = ld.content_type.model
                    if dk in upd and upd[dk] is not None:
                        extra[dk] = upd[dk]

                # one DataRequest per session
                dr = dr_by_sess.get(session.pk)
                if not dr:
                    dr = DataRequest.objects.create(
                        session=session, description="Manual grid update"
                    )
                    dr_by_sess[session.pk] = dr

                # create or update the fact, including extra_dimensions_json
                fact, created = PlanningFact.objects.get_or_create(
                    session=session,
                    org_unit=org,
                    service=svc,
                    period=per,
                    key_figure=kf,
                    extra_dimensions_json=extra,
                    defaults={
                        "request":   dr,
                        "version":   ly.version,
                        "year":      ly.year,
                        "uom":       None,
                        "value":     Decimal(upd["value"]),
                        "ref_value": Decimal("0"),
                        "ref_uom":   None,
                    },
                )

                if not created:
                    fact.request = dr
                    fact.value   = Decimal(upd["value"])
                    if extra:
                        fact.extra_dimensions_json = extra
                        fact.save(update_fields=["request", "value", "extra_dimensions_json"])
                    else:
                        fact.save(update_fields=["request", "value"])

                success += 1

            except Exception as e:
                errors.append({"update": upd, "error": str(e)})

        if errors:
            return Response(
                {"updated": success, "errors": errors},
                status=status.HTTP_207_MULTI_STATUS,
            )
        return Response({"updated": success}, status=status.HTTP_200_OK)