import re
from decimal import Decimal
from django.db.models import Q
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

MONTH_ALIASES = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}
QTR_FIRST_MONTH = {"Q1": "01", "Q2": "04", "Q3": "07", "Q4": "10"}

def normalize_period_code(raw):
    if raw is None:
        raise ValueError("Missing period")
    s = str(raw).strip().upper()
    if s.startswith("M") and s[1:].isdigit():
        s = s[1:]
    if s in QTR_FIRST_MONTH:
        return QTR_FIRST_MONTH[s]
    if s[:3] in MONTH_ALIASES:
        return MONTH_ALIASES[s[:3]]
    if s.isdigit():
        i = int(s)
        if 1 <= i <= 12:
            return f"{i:02d}"
    if re.fullmatch(r"\d{2}", s):
        return s
    raise ValueError(f"Invalid period '{raw}'")

def parse_pk_or_code(val):
    if val is None or val == "":
        return None, None
    s = str(val).strip()
    if s.lower() in {"null", "(null)"}:
        return "NULL", None
    if s.isdigit():
        return "PK", int(s)
    return "CODE", s

class BulkUpdateSerializer(serializers.Serializer):
    # layout = serializers.IntegerField()   # Deprecated, use layout_year
    layout_year = serializers.IntegerField(required=False)  # new
    delete_zeros = serializers.BooleanField(required=False, default=True)
    delete_blanks = serializers.BooleanField(required=False, default=True)
    headers = serializers.DictField(
        child=serializers.JSONField(allow_null=True),
        required=False,
        default=dict,
    )
    updates = serializers.ListField(
        child=serializers.DictField(child=serializers.JSONField(allow_null=True))
    )

class PlanningGridView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        # accept layout_year (preferred) or old layout param for backward compat
        ly_pk = request.query_params.get("layout_year") or request.query_params.get("layout")
        ly = get_object_or_404(PlanningLayoutYear, pk=ly_pk)

        # OLD: row_dims = list(ly.layout_dimensions.filter(is_row=True))
        row_dims = list(
            ly.layout.dimensions.filter(is_row=True).select_related("content_type")
        )
        dim_keys   = [ld.content_type.model for ld in row_dims]
        dim_models = {ld.content_type.model: ld.content_type.model_class() for ld in row_dims}
        
        qs = (
            PlanningFact.objects
            .filter(session__scenario__layout_year=ly)
            .select_related("org_unit", "service", "period", "key_figure")
        )

        # header filters accept PK or code
        org_sel = request.query_params.get("header_orgunit")
        if org_sel:
            kind, v = parse_pk_or_code(org_sel)
            if kind == "PK":
                qs = qs.filter(org_unit_id=v)
            elif kind == "CODE":
                qs = qs.filter(org_unit__code=v)

        svc_sel = request.query_params.get("header_service")
        if svc_sel:
            kind, v = parse_pk_or_code(svc_sel)
            if kind == "PK":
                qs = qs.filter(service_id=v)
            elif kind == "CODE":
                qs = qs.filter(service__code=v)
            elif kind == "NULL":
                qs = qs.filter(service__isnull=True)

        # other header dims (only those that are also row dims)
        for param, val in request.query_params.items():
            if not param.startswith("header_"):
                continue
            key = param[len("header_"):]
            if key in {"orgunit", "service"}:
                continue
            if key not in dim_keys:
                continue
            if val is None or val == "":
                continue
            try:
                v_int = int(val)
            except (TypeError, ValueError):
                continue
            qs = qs.filter(extra_dimensions_json__contains={key: v_int})

        rows = {}
        for fact in qs:
            org_code = fact.org_unit.code
            svc_code = fact.service.code if fact.service else ""
            ed = fact.extra_dimensions_json or {}
            dim_codes = [ed.get(k) for k in dim_keys]
            key = (org_code, svc_code, *dim_codes)

            if key not in rows:
                base = {
                    "org_unit":      fact.org_unit.name,
                    "org_unit_code": org_code,
                    "service":       fact.service.name if fact.service else None,
                    "service_code":  svc_code or None,
                }
                for dk in dim_keys:
                    code = ed.get(dk)
                    inst = dim_models[dk].objects.filter(pk=code).first() if code else None
                    base[dk] = str(inst) if inst else None
                    base[f"{dk}_code"] = code
                rows[key] = base

            col = f"{fact.period.code}_{fact.key_figure.code}"
            rows[key][col] = float(fact.value)

        return Response(list(rows.values()))

class PlanningGridBulkUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "options"]

    @staticmethod
    def _org_from_any(val):
        if val in (None, "", "NULL", "(null)"):
            raise ValueError("Missing 'org_unit'")
        kind, v = parse_pk_or_code(val)
        if kind == "PK":
            return get_object_or_404(OrgUnit, pk=v)
        if kind == "CODE":
            return get_object_or_404(OrgUnit, code=v)
        raise ValueError("Invalid 'org_unit'")

    @staticmethod
    def _service_from_any(val):
        if val in (None, "", "NULL", "(null)"):
            return None
        kind, v = parse_pk_or_code(val)
        if kind == "PK":
            return get_object_or_404(Service, pk=v)
        if kind == "CODE":
            return get_object_or_404(Service, code=v)
        raise ValueError("Invalid 'service'")

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        return self._handle(request)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        return self._handle(request)

    def _handle(self, request):
        ser = BulkUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = ser.validated_data

        # accept layout_year or layout
        ly_id = payload.get("layout_year") or payload.get("layout")
        ly = get_object_or_404(PlanningLayoutYear, pk=ly_id)
        
        delete_zeros = payload.get("delete_zeros", True)
        delete_blanks = payload.get("delete_blanks", True)
        header_defaults = payload.get("headers", {}) or {}

        errors, updated, deleted = [], 0, 0
        dr_by_sess = {}

        row_dims = list(
            ly.layout.dimensions.filter(is_row=True).select_related("content_type")
        )
        row_dim_keys = [ld.content_type.model for ld in row_dims]

        for upd in payload["updates"]:
            try:
                # --- resolve org / service (accept PK or code) ---
                org_val = upd.get("org_unit") or header_defaults.get("orgunit") or header_defaults.get("org_unit")
                if not org_val:
                    raise ValueError("Missing 'org_unit' (row or headers)")
                org = self._org_from_any(org_val)

                svc_is_provided = ("service" in upd) or ("service" in header_defaults)
                svc_val = upd.get("service")
                if svc_val is None:
                    svc_val = header_defaults.get("service")
                svc = self._service_from_any(svc_val)

                # --- extra row dimensions (PKs or str) ---
                extra = {}
                for key in row_dim_keys:
                    val = upd.get(key)
                    if val is None:
                        val = header_defaults.get(key)
                    if val is not None:
                        try:
                            extra[key] = int(val)
                        except (TypeError, ValueError):
                            extra[key] = val

                # Session for this org in the selected layout-year
                session = PlanningSession.objects.get(
                    scenario__layout_year=ly, org_unit=org
                )

                # --- delete entire slice (fast path) ---
                if str(upd.get("delete_row")).lower() in {"1", "true", "yes"}:
                    qs = PlanningFact.objects.filter(
                        session__scenario__layout_year=ly,
                        org_unit=org,
                    )
                    # Only filter by service if the client actually provided it
                    if svc_is_provided:
                        qs = qs.filter(service=svc)
                    # tolerant match on extra dims
                    if extra:
                        cond = Q()
                        for k, v in extra.items():
                            cond &= (Q(extra_dimensions_json__contains={k: v}) |
                                     Q(extra_dimensions_json__contains={k: str(v)}))
                        qs = qs.filter(cond)
                    else:
                        qs = qs.filter(extra_dimensions_json={})

                    cnt = qs.count()
                    if cnt:
                        qs.delete()
                        deleted += cnt
                    continue

                # --- resolve period / key-figure for normal update or cell delete ---
                per_code_raw = upd.get("period")
                if not per_code_raw:
                    raise ValueError("Missing 'period' code")
                per_code = normalize_period_code(per_code_raw)
                per = get_object_or_404(Period, code=per_code)

                kf_code = upd.get("key_figure")
                if not kf_code:
                    raise ValueError("Missing 'key_figure' code")
                kf = get_object_or_404(KeyFigure, code=kf_code)

                raw_val = upd.get("value", None)
                is_blank = (raw_val is None) or (isinstance(raw_val, str) and raw_val.strip() == "")

                # --- delete-on-blank or zero ---
                if (delete_blanks and is_blank) or (delete_zeros and not is_blank and Decimal(str(raw_val)) == 0):
                    qs = PlanningFact.objects.filter(
                        session=session, org_unit=org, service=svc,
                        period=per, key_figure=kf, extra_dimensions_json=extra
                    )
                    cnt = qs.count()
                    if cnt:
                        qs.delete()
                        deleted += cnt
                    continue

                # --- upsert path ---
                val = Decimal(str(raw_val))

                dr = dr_by_sess.get(session.pk)
                if not dr:
                    dr = DataRequest.objects.create(
                        session=session, description="Manual grid update"
                    )
                    dr_by_sess[session.pk] = dr

                fact, created = PlanningFact.objects.get_or_create(
                    session=session,
                    org_unit=org,
                    service=svc,
                    period=per,
                    key_figure=kf,
                    extra_dimensions_json=extra,
                    defaults={
                        "request": dr,
                        "version": ly.version,
                        "year":    ly.year,
                        "uom":     kf.default_uom,
                        "value":   val,
                        "ref_value": Decimal("0"),
                        "ref_uom": None,
                    },
                )
                if not created:
                    fact.request = dr
                    fact.value   = val
                    if extra:
                        fact.extra_dimensions_json = extra
                        fact.save(update_fields=["request","value","extra_dimensions_json"])
                    else:
                        fact.save(update_fields=["request","value"])
                updated += 1

            except Exception as e:
                errors.append({"update": upd, "error": str(e)})

        result = {"updated": updated, "deleted": deleted}
        if errors:
            result["errors"] = errors
            return Response(result, status=status.HTTP_207_MULTI_STATUS)
        return Response(result, status=status.HTTP_200_OK)