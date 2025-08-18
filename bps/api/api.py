# bps/api/api.py
import re
from decimal import Decimal
from typing import Dict, Any, List
from django.core.exceptions import ObjectDoesNotExist

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.db import transaction
# from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response

from bps.models.models_layout import PlanningLayoutYear
from bps.models.models import PlanningFact, Period, KeyFigure, DataRequest
from bps.models.models_dimension import OrgUnit, Service
from bps.models.models_workflow import PlanningSession, PlanningScenario, ScenarioStep
from bps.models.models_extras import PlanningFactExtra, DimensionKey
from django.contrib.contenttypes.models import ContentType


MONTH_ALIASES = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}
QTR_FIRST_MONTH = {"Q1": "01", "Q2": "04", "Q3": "07", "Q4": "10"}


def normalize_period_code(raw):
    """Return 'MM' or None (for year-dependent)."""
    if raw is None:
        return None
    s = str(raw).strip().upper()
    if s == "" or s == "NULL":
        return None
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
    layout_year = serializers.IntegerField(required=False)
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
    """Returns grid rows for the manual planning UI, honoring header filters."""

    @staticmethod
    def _extra_matches(stored: dict | None, expected: dict | None) -> bool:
        if not expected:
            return True
        stored_lc = {str(k).lower(): v for k, v in (stored or {}).items()}
        for k, v in expected.items():
            sv = stored_lc.get(str(k).lower(), None)
            if (None if sv is None else str(sv)) != (None if v is None else str(v)):
                return False
        return True

    def get(self, request):
        ly_pk = request.query_params.get("layout_year") or request.query_params.get("layout")
        ly = get_object_or_404(PlanningLayoutYear, pk=ly_pk)

        # Determine JSON dims = all dims except orgunit/service
        all_dims = list(ly.layout.dimensions.select_related("content_type"))
        dim_keys = [ld.content_type.model for ld in all_dims]
        json_dim_keys = [k for k in dim_keys if k not in ("orgunit", "service")]

        # Base queryset with extra dimensions
        qs = (
            PlanningFact.objects
            .filter(session__scenario__layout_year=ly)
            .select_related("org_unit", "service", "period", "key_figure", "session__org_unit")
            .prefetch_related("extras__key", "extras__value_obj")
        )

        # Header filters
        org_sel = request.query_params.get("header_orgunit")
        if org_sel:
            kind, v = parse_pk_or_code(org_sel)
            if kind == "PK":
                qs = qs.filter(Q(org_unit_id=v) | Q(session__org_unit_id=v))
            elif kind == "CODE":
                qs = qs.filter(Q(org_unit__code=v) | Q(session__org_unit__code=v))

        svc_sel = request.query_params.get("header_service")
        if svc_sel:
            kind, v = parse_pk_or_code(svc_sel)
            if kind == "PK":
                qs = qs.filter(service_id=v)
            elif kind == "CODE":
                qs = qs.filter(service__code=v)
            elif kind == "NULL":
                qs = qs.filter(service__isnull=True)

        # Extra header filters using PlanningFactExtra
        extra_filters: Dict[str, Any] = {}
        for param, val in request.query_params.items():
            if not param.startswith("header_"):
                continue
            key = param[len("header_"):]
            if key in {"orgunit", "service"} or key not in json_dim_keys:
                continue
            if val is None or val == "":
                continue
            extra_filters[key] = val
            
            # Filter by extra dimensions
            try:
                dim_key = DimensionKey.objects.get(key=key)
                kind, v = parse_pk_or_code(val)
                if kind == "PK":
                    qs = qs.filter(extras__key=dim_key, extras__object_id=v)
                elif kind == "CODE":
                    # Find by code in the target model
                    Model = dim_key.content_type.model_class()
                    if hasattr(Model, 'code'):
                        obj = Model.objects.filter(code=v).first()
                        if obj:
                            qs = qs.filter(extras__key=dim_key, extras__object_id=obj.pk)
            except DimensionKey.DoesNotExist:
                continue

        # Lookup label helpers for JSON dims
        dim_models = {ld.content_type.model: ld.content_type.model_class() for ld in all_dims}
        pk_to_label: Dict[str, Dict[int, str]] = {}
        code_to_pk: Dict[str, Dict[str, int]] = {}
        pk_to_code: Dict[str, Dict[int, str]] = {}

        for key in json_dim_keys:
            Model = dim_models[key]
            if hasattr(Model, "code"):
                items = Model.objects.all().values("id", "code", "name")
                code_to_pk[key] = {str(it["code"]): it["id"] for it in items}
                pk_to_code[key] = {it["id"]: str(it["code"]) for it in items}
                pk_to_label[key] = {it["id"]: (it["name"] or str(it["code"])) for it in items}
            else:
                items = Model.objects.all().values("id", "name")
                code_to_pk[key] = {}
                pk_to_code[key] = {}
                pk_to_label[key] = {it["id"]: (it["name"] or str(it["id"])) for it in items}

        def resolve_extra_pk_and_label(key: str, raw):
            if raw is None or raw == "":
                return None, None
            if isinstance(raw, int) or (isinstance(raw, str) and raw.isdigit()):
                pk = int(raw)
                return pk, pk_to_label.get(key, {}).get(pk)
            pk = code_to_pk.get(key, {}).get(str(raw))
            if pk:
                return pk, pk_to_label.get(key, {}).get(pk)
            return None, None

        # Build rows using PlanningFactExtra
        rows = {}
        for fact in qs.iterator():
            org_code = fact.org_unit.code
            svc_code = fact.service.code if fact.service else ""
            
            # Get extra dimensions from PlanningFactExtra
            extras_dict = {}
            for extra in fact.extras.all():
                extras_dict[extra.key.key] = {
                    'pk': extra.object_id,
                    'obj': extra.value_obj
                }

            dim_pks = []
            dim_pk_by_key = {}
            dim_lbl_by_key = {}
            for key in json_dim_keys:
                extra_info = extras_dict.get(key)
                if extra_info:
                    pk = extra_info['pk']
                    obj = extra_info['obj']
                    lbl = getattr(obj, 'name', None) or getattr(obj, 'code', None) or str(obj)
                else:
                    pk = None
                    lbl = None
                
                dim_pks.append(pk)
                dim_pk_by_key[key] = pk
                dim_lbl_by_key[key] = lbl

            key_tuple = (org_code, svc_code, *dim_pks)
            if key_tuple not in rows:
                base = {
                    "org_unit":      fact.org_unit.name,
                    "org_unit_code": org_code,
                    "service":       fact.service.name if fact.service else None,
                    "service_code":  svc_code or None,
                }
                for k in json_dim_keys:
                    base[k] = dim_lbl_by_key[k]
                    base[f"{k}_code"] = dim_pk_by_key[k]
                rows[key_tuple] = base

            if fact.period:
                col = f"{fact.period.code}_{fact.key_figure.code}"
            else:
                col = f"YEAR_{fact.key_figure.code}"
            rows[key_tuple][col] = float(fact.value)

        return Response(list(rows.values()))

class PlanningGridBulkUpdateView(APIView):
    # permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "options"]

    @staticmethod
    def _org_from_any(val):
        if val in (None, "", "NULL", "(null)"):
            raise ValueError("Missing 'org_unit'")
        s = str(val).strip()
        if s.isdigit():
            try:
                return OrgUnit.objects.get(pk=int(s))
            except ObjectDoesNotExist:
                pass
        try:
            return OrgUnit.objects.get(code=s)
        except ObjectDoesNotExist:
            raise ValueError(f"OrgUnit not found for value '{val}'")

    @staticmethod
    def _service_from_any(val):
        if val in (None, "",):
            return None, None
        s = str(val).strip()
        if s.lower() in {"null", "(null)"}:
            return None, "NULL"
        if s.isdigit():
            try:
                return Service.objects.get(pk=int(s)), "VAL"
            except ObjectDoesNotExist:
                pass
        try:
            return Service.objects.get(code=s), "VAL"
        except ObjectDoesNotExist:
            raise ValueError(f"Service not found for value '{val}'")

    @staticmethod
    def _keyfigure_from_any(val):
        if val in (None, "",):
            raise ValueError("Missing 'key_figure'")
        s = str(val).strip()
        if s.isdigit():
            try:
                return KeyFigure.objects.get(pk=int(s))
            except ObjectDoesNotExist:
                pass
        try:
            return KeyFigure.objects.get(code__iexact=s)
        except ObjectDoesNotExist:
            raise ValueError(f"KeyFigure not found for value '{val}'")

    @staticmethod
    def _extra_matches(stored: dict | None, expected: dict | None,
                       *, code_to_pk: Dict[str, Dict[str, int]] | None = None,
                       pk_to_code: Dict[str, Dict[int, str]] | None = None) -> bool:
        if not expected:
            return True
        stored = stored or {}
        stored_lc = {str(k).lower(): v for k, v in stored.items()}
        code_to_pk = code_to_pk or {}
        pk_to_code = pk_to_code or {}
        for k, v in expected.items():
            key = str(k).lower()
            sv = stored_lc.get(key, None)
            if sv is None and v is None:
                continue
            if sv is None or v is None:
                return False
            if str(sv) == str(v):
                continue
            # tolerant PK<->code equivalence
            try:
                v_int = int(v)
            except (TypeError, ValueError):
                v_int = None
            if isinstance(sv, int) and v_int is None:
                if code_to_pk.get(key, {}).get(str(v)) == sv:
                    continue
            if isinstance(sv, str) and v_int is not None:
                if pk_to_code.get(key, {}).get(v_int) == sv:
                    continue
            return False
        return True

    def _resolve_dimension_value(self, key: str, val: Any) -> tuple[ContentType, int] | None:
        """Resolve dimension key/value to (content_type, object_id) for PlanningFactExtra."""
        try:
            dim_key = DimensionKey.objects.get(key=key)
            Model = dim_key.content_type.model_class()
            
            kind, v = parse_pk_or_code(val)
            if kind == "PK":
                if Model.objects.filter(pk=v).exists():
                    return dim_key.content_type, v
            elif kind == "CODE" and hasattr(Model, 'code'):
                obj = Model.objects.filter(code=v).first()
                if obj:
                    return dim_key.content_type, obj.pk
            return None
        except DimensionKey.DoesNotExist:
            raise ValueError(f"Unknown dimension key: {key}")
    
    def _collect_extras(self, upd: Dict[str, Any], header_defaults: Dict[str, Any],
                        json_dim_keys: list[str]) -> Dict[str, tuple[ContentType, int]]:
        """
        Collect extra dimensions from update data and headers.
        Returns dict of {key: (content_type, object_id)} for PlanningFactExtra creation.
        """
        extra: Dict[str, tuple[ContentType, int]] = {}
        raw_extra: Dict[str, Any] = {}

        # Handle nested format (backward compatibility)
        nested = upd.get("extra_dimensions_json") or {}
        for k, v in nested.items():
            if v is not None:
                raw_extra[k] = v

        # Handle flat format (preferred)
        for key in json_dim_keys:
            if key in raw_extra:
                continue
            val = upd.get(key)
            if val is None:
                val = header_defaults.get(key)
            if val is not None:
                raw_extra[key] = val

        # Resolve to (content_type, object_id)
        for key, val in raw_extra.items():
            resolved = self._resolve_dimension_value(key, val)
            if resolved:
                extra[key] = resolved

        return extra

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        return self._handle(request)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        return self._handle(request)

    def _build_delete_qs(
        self,
        ly: PlanningLayoutYear,
        org,
        *,
        period: Period | None = None,
        key_figure: KeyFigure | None = None,
        service_obj=None,
        service_flag: str | None = None,
        extra: Dict[str, Any] | None = None,
    ):
        filters = {"session__scenario__layout_year": ly, "org_unit": org}
        if period is not None:
            filters["period"] = period
        if key_figure is not None:
            filters["key_figure"] = key_figure

        qs = PlanningFact.objects.filter(**filters)

        if service_flag == "VAL":
            qs = qs.filter(service=service_obj)
        elif service_flag == "NULL":
            qs = qs.filter(service__isnull=True)

        # do NOT filter on JSON here; finalize matching in Python
        return qs

    def _handle(self, request):
        ser = BulkUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = ser.validated_data

        ly_id = payload.get("layout_year") or payload.get("layout") or request.query_params.get("layout_year")
        ly = get_object_or_404(PlanningLayoutYear, pk=ly_id)

        delete_zeros = payload.get("delete_zeros", True)
        delete_blanks = payload.get("delete_blanks", True)
        header_defaults: Dict[str, Any] = payload.get("headers", {}) or {}

        errors: List[Dict[str, Any]] = []
        updated, deleted = 0, 0

        # JSON dims (exclude OU/Service)
        all_dims = list(ly.layout.dimensions.select_related("content_type"))
        json_dim_keys = [
            ld.content_type.model
            for ld in all_dims
            if ld.content_type.model not in ("orgunit", "service")
        ]

        # PK<->code maps for tolerant JSON matching
        dim_models = {ld.content_type.model: ld.content_type.model_class() for ld in all_dims}
        code_to_pk: Dict[str, Dict[str, int]] = {}
        pk_to_code: Dict[str, Dict[int, str]] = {}
        for key in json_dim_keys:
            Model = dim_models[key]
            if hasattr(Model, "code"):
                items = Model.objects.all().values("id", "code")
                code_to_pk[key] = {str(it["code"]): it["id"] for it in items}
                pk_to_code[key] = {it["id"]: str(it["code"]) for it in items}
            else:
                code_to_pk[key] = {}
                pk_to_code[key] = {}

        updates_all: List[Dict[str, Any]] = payload["updates"]
        delete_updates = [u for u in updates_all if str(u.get("delete_row")).lower() in {"1", "true", "yes"}]
        upsert_updates = [u for u in updates_all if u not in delete_updates]

        def resolve_session_for(org):
            session = (
                PlanningSession.objects
                .filter(scenario__layout_year=ly, org_unit=org)
                .select_related("scenario")
                .first()
            )
            if not session:
                scenario = (
                    PlanningScenario.objects.filter(layout_year=ly, is_active=True)
                    .order_by("id").first()
                )
                if not scenario:
                    raise ValueError("No active scenario for this layout/year/version.")
                first_step = (
                    ScenarioStep.objects.filter(scenario=scenario).order_by("order").first()
                )
                if not first_step:
                    raise ValueError("Scenario has no steps configured.")
                session = PlanningSession.objects.create(
                    scenario=scenario,
                    org_unit=org,
                    created_by=request.user,
                    current_step=first_step,
                )
            return session

        # ---- Deletes -------------------------------------------------------
        for upd in delete_updates:
            try:
                org_val = upd.get("org_unit") or header_defaults.get("orgunit") or header_defaults.get("org_unit")
                if not org_val:
                    raise ValueError("Missing 'org_unit' (row or headers)")
                org = self._org_from_any(org_val)

                svc_val = upd.get("service")
                if svc_val is None:
                    svc_val = header_defaults.get("service")
                svc_obj, svc_flag = self._service_from_any(svc_val)

                expected_extra = self._collect_extras(upd, header_defaults, json_dim_keys)

                kf_raw = upd.get("key_figure")
                kf = self._keyfigure_from_any(kf_raw) if kf_raw else None

                per_raw = upd.get("period")
                per_code = normalize_period_code(per_raw)
                per = get_object_or_404(Period, code=per_code) if per_code else None

                qs = self._build_delete_qs(
                    ly, org,
                    period=per, key_figure=kf,
                    service_obj=svc_obj, service_flag=svc_flag,
                    extra=None,
                )

                # For deletes, we need to match extra dimensions
                ids = []
                for f in qs.prefetch_related('extras__key', 'extras__value_obj').iterator():
                    # Convert PlanningFactExtra to dict for matching
                    f_extras = {}
                    for extra in f.extras.all():
                        f_extras[extra.key.key] = extra.object_id
                    
                    if self._extra_matches(
                        f_extras, expected_extra,
                        code_to_pk=code_to_pk, pk_to_code=pk_to_code
                    ):
                        ids.append(f.id)

                if ids:
                    deleted += PlanningFact.objects.filter(id__in=ids).delete()[0]
                else:
                    errors.append({"update": upd, "error": "No facts matched for deletion"})

            except Exception as e:
                errors.append({"update": upd, "error": str(e)})

        # ---- Upserts / zero-or-blank-as-delete ----------------------------
        for upd in upsert_updates:
            try:
                org_val = upd.get("org_unit") or header_defaults.get("orgunit") or header_defaults.get("org_unit")
                if not org_val:
                    raise ValueError("Missing 'org_unit' (row or headers)")
                org = self._org_from_any(org_val)

                svc_val = upd.get("service")
                if svc_val is None:
                    svc_val = header_defaults.get("service")
                svc_obj, svc_flag = self._service_from_any(svc_val)

                extra = self._collect_extras(upd, header_defaults, json_dim_keys)

                per_raw = upd.get("period")
                per_code = normalize_period_code(per_raw)
                per = get_object_or_404(Period, code=per_code) if per_code else None

                kf_raw = upd.get("key_figure")
                if not kf_raw:
                    raise ValueError("Missing 'key_figure' code")
                kf = self._keyfigure_from_any(kf_raw)

                raw_val = upd.get("value", None)
                is_blank = (raw_val is None) or (isinstance(raw_val, str) and raw_val.strip() == "")

                # Delete-on-blank/zero with tolerant JSON match
                if (delete_blanks and is_blank) or (delete_zeros and not is_blank and Decimal(str(raw_val)) == 0):
                    qs = self._build_delete_qs(
                        ly, org,
                        period=per, key_figure=kf,
                        service_obj=svc_obj, service_flag=svc_flag,
                        extra=None,
                    )
                    ids = []
                    for f in qs.prefetch_related('extras__key', 'extras__value_obj').iterator():
                        # Convert PlanningFactExtra to dict for matching
                        f_extras = {}
                        for extra_obj in f.extras.all():
                            f_extras[extra_obj.key.key] = extra_obj.object_id
                        
                        if self._extra_matches(
                            f_extras, extra,
                            code_to_pk=code_to_pk, pk_to_code=pk_to_code
                        ):
                            ids.append(f.id)
                    if ids:
                        deleted += PlanningFact.objects.filter(id__in=ids).delete()[0]
                    else:
                        errors.append({"update": upd, "error": "No facts matched for zero/blank deletion"})
                    continue

                # Upsert
                session = resolve_session_for(org)
                val = Decimal(str(raw_val))

                base_qs = PlanningFact.objects.filter(
                    session=session,
                    org_unit=org,
                    period=per,
                    key_figure=kf,
                )
                if svc_flag == "VAL":
                    base_qs = base_qs.filter(service=svc_obj)
                elif svc_flag == "NULL":
                    base_qs = base_qs.filter(service__isnull=True)
                else:
                    base_qs = base_qs.filter(service__isnull=True)

                target = None
                for f in base_qs.prefetch_related('extras__key', 'extras__value_obj').iterator():
                    # Convert PlanningFactExtra to dict for matching
                    f_extras = {}
                    for extra_obj in f.extras.all():
                        f_extras[extra_obj.key.key] = extra_obj.object_id
                    
                    if self._extra_matches(
                        f_extras, extra,
                        code_to_pk=code_to_pk, pk_to_code=pk_to_code
                    ):
                        target = f
                        break

                dr = DataRequest.objects.create(session=session, description="Manual grid update")
                if target:
                    target.request = dr
                    target.value = val
                    target.save(update_fields=["request", "value"])
                    
                    # Update extra dimensions
                    target.extras.all().delete()
                    for key, (content_type, object_id) in extra.items():
                        dim_key = DimensionKey.objects.get(key=key)
                        PlanningFactExtra.objects.create(
                            fact=target,
                            key=dim_key,
                            content_type=content_type,
                            object_id=object_id
                        )
                else:
                    fact = PlanningFact.objects.create(
                        request=dr,
                        session=session,
                        org_unit=org,
                        service=(svc_obj if svc_flag == "VAL" else None),
                        period=per,
                        key_figure=kf,
                        version=ly.version,
                        year=ly.year,
                        uom=kf.default_uom,
                        value=val,
                        ref_value=Decimal("0"),
                        ref_uom=None,
                    )
                    
                    # Create extra dimensions
                    for key, (content_type, object_id) in extra.items():
                        dim_key = DimensionKey.objects.get(key=key)
                        PlanningFactExtra.objects.create(
                            fact=fact,
                            key=dim_key,
                            content_type=content_type,
                            object_id=object_id
                        )
                updated += 1

            except Exception as e:
                errors.append({"update": upd, "error": str(e)})

        result = {"updated": updated, "deleted": deleted}
        if errors:
            result["errors"] = errors
            return Response(result, status=status.HTTP_207_MULTI_STATUS)
        return Response(result, status=status.HTTP_200_OK)