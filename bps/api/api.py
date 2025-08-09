# bps/api/api.py
import re
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

# Add near the top (module level), after imports:
MONTH_ALIASES = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}
QTR_FIRST_MONTH = {"Q1": "01", "Q2": "04", "Q3": "07", "Q4": "10"}

def normalize_period_code(raw):
    """Return canonical two-digit Period.code from various aliases."""
    if raw is None:
        raise ValueError("Missing period")
    s = str(raw).strip().upper()

    # Accept "M01" / "M1"
    if s.startswith("M") and s[1:].isdigit():
        s = s[1:]

    # Accept "Q1".."Q4" → first month of quarter
    if s in QTR_FIRST_MONTH:
        return QTR_FIRST_MONTH[s]

    # Accept month names "JAN".."DEC"
    if s[:3] in MONTH_ALIASES:
        return MONTH_ALIASES[s[:3]]

    # Accept "1".."12" → "01".."12"
    if s.isdigit():
        i = int(s)
        if 1 <= i <= 12:
            return f"{i:02d}"

    # Already canonical "01".."12" just falls through if it got here
    if re.fullmatch(r"\d{2}", s):
        return s

    raise ValueError(f"Invalid period '{raw}'")

class BulkUpdateSerializer(serializers.Serializer):
    """
    Accepts:
      - layout: int (required)
      - delete_zeros: bool (optional, default True)
      - delete_blanks: bool (optional, default True)
      - updates: list[dict] (required)
        Each dict may include:
          org_unit (code), service (code or null),
          period (e.g. "01"), key_figure (code), value (number/string/null),
          plus any number of extra row-dimension keys (e.g. "position","skill",...)
    """
    layout = serializers.IntegerField()
    delete_zeros = serializers.BooleanField(required=False, default=True)
    delete_blanks = serializers.BooleanField(required=False, default=True)
    # allow arbitrary keys/values in each update row
    updates = serializers.ListField(
        child=serializers.DictField(child=serializers.JSONField(allow_null=True))
    )

# -------- Views --------

class PlanningGridView(APIView):
    """
    Same as your previous implementation (read-only grid data).
    """
    def get(self, request):
        ly_pk = request.query_params.get('layout')
        ly = get_object_or_404(PlanningLayoutYear, pk=ly_pk)

        row_dims = list(ly.layout_dimensions.filter(is_row=True))
        dim_keys = [ld.content_type.model for ld in row_dims]
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
    """
    Bulk write endpoint used by manual planning grid.
    Supports pruning zero/blank writes (delete instead of storing 0).
    Returns 200 on full success, 207 with per-row errors on partial failures.
    """
    http_method_names = ["get", "post", "patch", "options"]

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

        ly = get_object_or_404(PlanningLayoutYear, pk=payload["layout"])
        delete_zeros = payload.get("delete_zeros", True)
        delete_blanks = payload.get("delete_blanks", True)

        errors, updated, deleted = [], 0, 0
        dr_by_sess = {}

        # Row-dimension keys to pull from updates
        row_dims = list(ly.layout_dimensions.filter(is_row=True))
        row_dim_keys = [ld.content_type.model for ld in row_dims]

        for upd in payload["updates"]:
            try:
                # --- Base dimensions (codes) ---
                org_code = upd.get("org_unit")
                if not org_code:
                    raise ValueError("Missing 'org_unit' code")
                org = OrgUnit.objects.get(code=org_code)

                svc_code = upd.get("service")
                svc = Service.objects.get(code=svc_code) if svc_code else None

                per_code = upd.get("period")
                if not per_code:
                    raise ValueError("Missing 'period' code")
                per = Period.objects.get(code=per_code)

                kf_code = upd.get("key_figure")
                if not kf_code:
                    raise ValueError("Missing 'key_figure' code")
                kf = KeyFigure.objects.get(code=kf_code)

                # --- Extra row-dimensions (opaque to API; match by equality on JSON) ---
                extra = {}
                for key in row_dim_keys:
                    if key in upd and upd[key] is not None:
                        extra[key] = upd[key]

                # --- Find session for this org+layoutyear ---
                session = PlanningSession.objects.get(
                    scenario__layout_year=ly, org_unit=org
                )

                # --- Interpret value (blank vs number) ---
                raw_val = upd.get("value", None)
                is_blank = (raw_val is None) or (isinstance(raw_val, str) and raw_val.strip() == "")

                if delete_blanks and is_blank:
                    # Delete existing fact if any; skip creating blank
                    qs = PlanningFact.objects.filter(
                        session=session,
                        org_unit=org,
                        service=svc,
                        period=per,
                        key_figure=kf,
                        extra_dimensions_json=extra,
                    )
                    count = qs.count()
                    if count:
                        qs.delete()
                        deleted += count
                    continue  # done with this update

                # Coerce to Decimal
                try:
                    val = Decimal(str(raw_val))
                except (InvalidOperation, TypeError):
                    raise ValueError(f"Invalid numeric value: {raw_val!r}")

                if delete_zeros and val == 0:
                    qs = PlanningFact.objects.filter(
                        session=session,
                        org_unit=org,
                        service=svc,
                        period=per,
                        key_figure=kf,
                        extra_dimensions_json=extra,
                    )
                    count = qs.count()
                    if count:
                        qs.delete()
                        deleted += count
                    continue

                # --- Ensure a DataRequest tied to this session for auditing ---
                dr = dr_by_sess.get(session.pk)
                if not dr:
                    dr = DataRequest.objects.create(
                        session=session, description="Manual grid update"
                    )
                    dr_by_sess[session.pk] = dr

                # --- Upsert fact ---
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
                        "year": ly.year,
                        "uom": kf.default_uom,
                        "value": val,
                        "ref_value": Decimal("0"),
                        "ref_uom": None,
                    },
                )

                if not created:
                    fact.request = dr
                    fact.value = val
                    # Persist extra even if dict changed from {}
                    if extra:
                        fact.extra_dimensions_json = extra
                        fact.save(update_fields=["request", "value", "extra_dimensions_json"])
                    else:
                        fact.save(update_fields=["request", "value"])

                updated += 1

            except Exception as e:
                errors.append({"update": upd, "error": str(e)})

        result = {"updated": updated, "deleted": deleted}
        if errors:
            result["errors"] = errors
            return Response(result, status=status.HTTP_207_MULTI_STATUS)
        return Response(result, status=status.HTTP_200_OK)