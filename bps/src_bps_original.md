# Python Project Summary: bps

## Folder Structure
```text
- bps/
  - access.py
  - admin.py
  - admin_access.py
  - apps.py
  - serializers.py
  - urls.py
  - documentation/
    - django-bps-design/
    - service-cost-planning/
  - utils/
    - tabulator.view.py
  - models/
    - admin_proxy.py
    - models.py
    - models_access.py
    - models_dimension.py
    - models_function.py
    - models_layout.py
    - models_period.py
    - models_resource.py
    - models_view.py
    - models_workflow.py
  - api/
    - api.py
    - serializers.py
    - urls.py
    - utils.py
    - views.py
    - views_lookup.py
    - views_manual.py
  - templates/
    - admin/
      - bps/
        - planning_dashboard.html
    - bps/
      - _action_reset.html
      - _paginator.html
      - _tabulator.html
      - base.html
      - constant_list.html
      - dashboard.html
      - data_request_detail.html
      - data_request_list.html
      - fact_list.html
      - formula_list.html
      - inbox.html
      - manual_planning.html
      - manual_planning_select.html
      - notifications.html
      - planning_function_list.html
      - reference_data_list.html
      - session_detail.html
      - session_list.html
      - subformula_list.html
      - variable_list.html
      - planner/
        - dashboard.html
  - views/
    - autocomplete.py
    - forms.py
    - formula_executor.py
    - manual_planning.py
    - views.py
    - views_decorator.py
    - views_planner.py
    - viewsets.py
```

---

### `access.py`
```python
from django.contrib.auth.models import Group
from django.db.models import Q
from .models.models_access import OrgUnitAccess, Delegation
from .models.models_dimension import OrgUnit
ENTERPRISE_GROUP = "Enterprise Planner"
SESSION_ACTING_AS = "bps_acting_as_user_id"
def is_enterprise_planner(user):
    return user.is_superuser or user.groups.filter(name=ENTERPRISE_GROUP).exists()
def get_effective_delegator(request):
    uid = request.session.get(SESSION_ACTING_AS)
    if not uid:
        return None
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        return User.objects.get(pk=uid)
    except User.DoesNotExist:
        return None
def can_act_as(user, delegator):
    return Delegation.objects.filter(delegatee=user, delegator=delegator).first()
def set_acting_as(request, delegator):
    request.session[SESSION_ACTING_AS] = delegator.pk
def clear_acting_as(request):
    request.session.pop(SESSION_ACTING_AS, None)
def allowed_orgunits_qs(user, request=None):
    if is_enterprise_planner(user):
        return OrgUnit.objects.all()
    delegator = get_effective_delegator(request) if request else None
    effective_user = delegator if (delegator and can_act_as(user, delegator) and can_act_as(user, delegator).is_active()) else user
    grants = OrgUnitAccess.objects.filter(user=effective_user).select_related("org_unit")
    if not grants.exists():
        return OrgUnit.objects.none()
    ids = set()
    for g in grants:
        if g.scope == OrgUnitAccess.SUBTREE:
            ids.update(g.org_unit.get_descendants(include_self=True).values_list("id", flat=True))
        else:
            ids.add(g.org_unit_id)
    return OrgUnit.objects.filter(id__in=list(ids))
def can_edit_ou(user, ou, request=None):
    if is_enterprise_planner(user):
        return True
    allowed = allowed_orgunits_qs(user, request).filter(pk=ou.pk).exists()
    if not allowed:
        return False
    grants = OrgUnitAccess.objects.filter(user=user, org_unit__in=[ou] + list(ou.get_ancestors())).order_by("-org_unit__level")
    return any(g.can_edit for g in grants)
```

### `api/api.py`
```python
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
    def get(self, request):
        ly_pk = request.query_params.get("layout_year") or request.query_params.get("layout")
        ly = get_object_or_404(PlanningLayoutYear, pk=ly_pk)
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
                org_val = upd.get("org_unit") or header_defaults.get("orgunit") or header_defaults.get("org_unit")
                if not org_val:
                    raise ValueError("Missing 'org_unit' (row or headers)")
                org = self._org_from_any(org_val)
                svc_is_provided = ("service" in upd) or ("service" in header_defaults)
                svc_val = upd.get("service")
                if svc_val is None:
                    svc_val = header_defaults.get("service")
                svc = self._service_from_any(svc_val)
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
                session = PlanningSession.objects.get(
                    scenario__layout_year=ly, org_unit=org
                )
                if str(upd.get("delete_row")).lower() in {"1", "true", "yes"}:
                    qs = PlanningFact.objects.filter(
                        session__scenario__layout_year=ly,
                        org_unit=org,
                    )
                    if svc_is_provided:
                        qs = qs.filter(service=svc)
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
```

### `api/serializers.py`
```python
from rest_framework import serializers
from bps.models.models import PlanningFact, Period
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
    def to_representation(self, instance):
        return instance
```

### `api/urls.py`
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import (
    PlanningGridView,
    PlanningGridBulkUpdateView,
)
from .views_manual import ManualPlanningGridAPIView
from ..views.viewsets import PlanningFactViewSet, OrgUnitViewSet
from .views import PlanningFactPivotedAPIView
from .views_lookup import header_options
app_name = "bps_api"
router = DefaultRouter()
router.register(r'facts',    PlanningFactViewSet,  basename='facts')
router.register(r'orgunits', OrgUnitViewSet,     basename='orgunits')
urlpatterns = [
    path("", include(router.urls)),
    path(
        "manual-grid/",
        ManualPlanningGridAPIView.as_view(),
        name="manual_planning_grid",
    ),
    path(
        "grid/",
        PlanningGridView.as_view(),
        name="planning_grid",
    ),
    path(
        "grid-update/",
        PlanningGridBulkUpdateView.as_view(),
        name="planning_grid_update",
    ),
    path(
        "pivot/",
        PlanningFactPivotedAPIView.as_view(),
        name="planning_pivot",
    ),
    path("api/layout/<int:layout_year_id>/header-options/<str:model_name>/", header_options, name="header-options"),
]
```

### `api/views.py`
```python
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.permissions import IsAuthenticated, AllowAny
from bps.models.models_layout import PlanningLayoutYear
from bps.models.models import PlanningFact, Version
from .serializers import PlanningFactPivotRowSerializer
from .utils import pivot_facts_grouped
class PlanningFactPivotedAPIView(APIView):
    permission_classes = [AllowAny]
    renderer_classes   = [JSONRenderer]
    def get(self, request):
        ly_pk = request.query_params.get("layout")
        if not ly_pk:
            return Response({"error": "Missing layout parameter"}, status=400)
        qs = PlanningFact.objects.filter(
            session__scenario__layout_year_id=ly_pk
        ).select_related(
            "org_unit", "service", "period", "key_figure"
        ).values(
            "org_unit__name",
            "service__name",
            "period__code",
            "key_figure__code",
            "value",
        )
        rows = {}
        for f in qs:
            org   = f["org_unit__name"]
            svc   = f["service__name"] or None
            key   = (org, svc)
            row   = rows.setdefault(key, {
                "org_unit": org,
                "service":  svc,
            })
            col   = f"{f['period__code']}_{f['key_figure__code']}"
            row[col] = float(f["value"])
        return Response(list(rows.values()))
class PlanningFactPivotedAPIView_OLD(APIView):
    permission_classes = [AllowAny]
    renderer_classes   = [JSONRenderer]
    def get(self, request):
        ly_pk = request.query_params.get("layout")
        if not ly_pk:
            return Response({"error": "Missing layout parameter"}, status=400)
        ly = get_object_or_404(PlanningLayoutYear, pk=ly_pk)
        facts = PlanningFact.objects.filter(session__scenario__layout_year=ly)
        version_code = request.query_params.get("version")
        if version_code:
            facts = facts.filter(version__code=version_code)
        valid_driver_keys = {
            ld.content_type.model
            for ld in ly.layout_dimensions.filter(is_row=True)
        }
        for param, val in request.query_params.items():
            if not param.startswith("driver_"):
                continue
            driver_key = param.replace("driver_", "", 1)
            if driver_key not in valid_driver_keys:
                continue
            facts = (
                facts
                .filter(extra_dimensions_json__has_key=driver_key)
                .filter(extra_dimensions_json__contains={driver_key: val})
            )
        use_ref = request.query_params.get("ref") == "1"
        pivoted = pivot_facts_grouped(facts, use_ref_value=use_ref)
        return Response(pivoted)
```

### `api/views_lookup.py`
```python
from django.http import JsonResponse, Http404
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from ..access import allowed_orgunits_qs
PAGE = 30
def header_options(request, layout_year_id, model_name):
    try:
        ct = ContentType.objects.get(model=model_name)
    except ContentType.DoesNotExist:
        raise Http404("Unknown dimension")
    Model = ct.model_class()
    q = request.GET.get("q", "")
    page = int(request.GET.get("page", 1))
    if model_name == "orgunit":
        qs = allowed_orgunits_qs(request.user, request)
    else:
        qs = Model.objects.all()
    if q:
        crit = Q(name__icontains=q) | Q(code__icontains=q)
        qs = qs.filter(crit) if hasattr(Model, "code") else qs.filter(name__icontains=q)
    total = qs.count()
    items = []
    for obj in qs.order_by("name" if hasattr(Model, "name") else "pk")[(page-1)*PAGE: page*PAGE]:
        text = getattr(obj, "code", None) or getattr(obj, "name", str(obj))
        items.append({"id": obj.pk, "text": text})
    return JsonResponse({
        "results": items,
        "pagination": {"more": page * PAGE < total},
    })
```

### `api/views_manual.py`
```python
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from bps.models.models import PlanningLayoutYear, PlanningFact, PlanningLayoutDimension, Version
from bps.models.models_layout import LayoutDimensionOverride
from .serializers import PlanningFactSerializer, PlanningFactPivotRowSerializer
from .utils import pivot_facts_grouped
class ManualPlanningGridAPIView(APIView):
    def get(self, request):
        layout_id = request.query_params.get('layout')
        year_id   = request.query_params.get('year')
        version   = request.query_params.get('version')
        use_ref   = request.query_params.get('ref') == '1'
        ly = get_object_or_404(PlanningLayoutYear, pk=layout_id)
        facts = PlanningFact.objects.filter(session__scenario__layout_year=ly)
        if year_id:
            facts = facts.filter(year_id=year_id)
        if version:
            facts = facts.filter(version__code=version)
        pivot = pivot_facts_grouped(facts, use_ref_value=use_ref)
        return Response(pivot)
    @transaction.atomic
    def post(self, request):
        payload = request.data
        layout_id = payload.get('layout')
        ly = get_object_or_404(PlanningLayoutYear, pk=layout_id)
        errors = []
        for upd in payload.get('updates', []):
            try:
                fact = PlanningFact.objects.get(pk=upd['id'], session__scenario__layout_year=ly)
                if upd['field'] not in ('value','ref_value'):
                    raise ValueError(f"Cannot edit field {upd['field']}")
                setattr(fact, upd['field'], Decimal(upd['value']))
                fact.save()
            except Exception as e:
                errors.append({'id': upd.get('id'), 'error': str(e)})
        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)
class PlanningGridAPIView(APIView):
    def get(self, request):
        base_id    = request.query_params.get("base") or request.query_params.get("layout")
        compare_id = request.query_params.get("compare")
        if not base_id:
            return Response(
                {"error": "Missing 'base' (or legacy 'layout') query parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        base_ly = get_object_or_404(PlanningLayoutYear, pk=base_id)
        allowed_versions = Version.objects.filter(
            Q(is_public=True) | Q(created_by=request.user)
        ).values_list("pk", flat=True)
        if base_ly.version_id not in allowed_versions:
            return Response(
                {"error": "You do not have permission to view the base layout."},
                status=status.HTTP_403_FORBIDDEN,
            )
        compare_ly = None
        if compare_id:
            compare_ly = get_object_or_404(PlanningLayoutYear, pk=compare_id)
            if compare_ly.version_id not in allowed_versions:
                return Response(
                    {"error": "You do not have permission to view the compare layout."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        base_qs = PlanningFact.objects.filter(
            session__scenario__layout_year=base_ly
        ).select_related("period", "key_figure", "org_unit", "service")
        compare_qs = None
        if compare_ly:
            compare_qs = PlanningFact.objects.filter(
                session__scenario__layout_year=compare_ly
            ).select_related("period", "key_figure", "org_unit", "service")
        rows = {}
        def ingest(qs, tag):
            for f in qs:
                org = f.org_unit.code
                svc = f.service.code if f.service else ""
                key = (org, svc)
                row = rows.setdefault(key, {
                    "org_unit": f.org_unit.name,
                    "service":  f.service.name if f.service else None,
                })
                col = f"{f.period.code}_{f.key_figure.code}"
                cell = row.setdefault(col, {})
                cell[tag] = float(f.value)
        ingest(base_qs,   "base")
        if compare_qs:
            ingest(compare_qs, "compare")
        return Response({"data": list(rows.values())})
class PlanningGridBulkUpdateAPIView(APIView):
    def patch(self, request):
        layout_id   = request.data.get("layout")
        action      = request.data.get("action_type", "DELTA").upper()
        version     = request.data.get("version")
        year_code   = request.data.get("year")
        updates     = request.data.get("updates", [])
        ly = get_object_or_404(PlanningLayoutYear, pk=layout_id)
        facts_qs = PlanningFact.objects.filter(session__scenario__layout_year=ly)
        if version:
            facts_qs = facts_qs.filter(version__code=version)
        if year_code:
            facts_qs = facts_qs.filter(year__code=year_code)
        if action == "RESET":
            facts_qs.update(value=0, ref_value=0)
        successful, errors = 0, []
        dims = { d.content_type.model: d for d in ly.layout.dimensions.all() }
        overrides = {
            ov.dimension_id: ov
            for ov in LayoutDimensionOverride.objects.filter(layout_year=ly).select_related("dimension")
        }
        for upd in updates:
            fact_id = upd.get("id")
            field   = upd.get("field")
            val      = upd.get("value")
            if field not in ("value", "ref_value") or not fact_id:
                errors.append({"update": upd, "error": "Invalid payload"})
                continue
            try:
                fact = PlanningFact.objects.select_related(
                    "org_unit", "service", "key_figure", "period"
                ).get(pk=fact_id, session__scenario__layout_year=ly)
            except PlanningFact.DoesNotExist:
                errors.append({"update": upd, "error": "Fact not found"})
                continue
            for ld in dims.values():
                if not ld.is_row:
                    continue
                model_name = ld.content_type.model
                inst = getattr(fact, model_name, None)
                if not inst:
                    continue
                ov = overrides.get(ld.id)
                if ov:
                    allowed = set(ov.allowed_values or [])
                    if allowed:
                        if inst.pk not in allowed and (not hasattr(inst, "code") or inst.code not in allowed):
                            raise ValueError(f"{model_name} {inst} not in allowed_values")
                    if ov.filter_criteria:
                        Model = ld.content_type.model_class()
                        if not Model.objects.filter(pk=inst.pk, **ov.filter_criteria).exists():
                            raise ValueError(f"{model_name} {inst} fails filter {ov.filter_criteria}")
                if ld.allowed_values and inst.pk not in ld.allowed_values:
                    raise ValueError(f"{model_name} {inst} not in allowed_values")
                if ld.filter_criteria:
                    Model = ld.content_type.model_class()
                    if not Model.objects.filter(pk=inst.pk, **ld.filter_criteria).exists():
                        raise ValueError(
                            f"{model_name} {inst} fails filter {ld.filter_criteria}"
                        )
            setattr(fact, field, Decimal(str(val)))
            fact.save(update_fields=[field])
            successful += 1
        if errors:
            return Response(
                {"updated": successful, "errors": errors},
                status=status.HTTP_207_MULTI_STATUS
            )
        return Response({"updated": successful}, status=status.HTTP_200_OK)
```

### `apps.py`
```python
from django.apps import AppConfig
class BpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bps"
```

### `models/models.py`
```python
from uuid import uuid4
from django.db import models, transaction
from django.contrib.postgres.fields import JSONField
from django.shortcuts import get_object_or_404
from django.db.models import Sum
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from treebeard.mp_tree import MP_Node
class TimestampModel(models.Model):
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    class Meta: abstract = True
class UnitOfMeasure(models.Model):
    code        = models.CharField(max_length=10, unique=True)
    name        = models.CharField(max_length=50)
    is_base     = models.BooleanField(default=False,
                                      help_text="Target unit for conversion rates")
    def __str__(self):
        return self.code
class ConversionRate(models.Model):
    from_uom = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE, related_name='conv_from')
    to_uom   = models.ForeignKey(UnitOfMeasure, on_delete=models.CASCADE, related_name='conv_to')
    factor   = models.DecimalField(max_digits=18, decimal_places=6,
                                   help_text="Multiply a from_uom value by this to get to_uom")
    class Meta:
        unique_together = ('from_uom','to_uom')
    def __str__(self):
        return f"1 {self.from_uom} → {self.factor} {self.to_uom}"
from .models_dimension import *
from .models_resource import *
class UserMaster(models.Model):
    user      = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True)
    def __str__(self):
        return self.user.get_full_name() or self.user.username
class KeyFigure(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    is_percent = models.BooleanField(default=False)
    default_uom = models.ForeignKey(UnitOfMeasure, null=True, on_delete=models.SET_NULL)
    display_decimals = models.PositiveSmallIntegerField(
        default=2,
        help_text="Number of decimal places to show for this key figure in grids and totals."
    )
    def __str__(self):
        return self.code
from .models_layout import *
from .models_period import *
from .models_workflow import *
class DataRequest(TimestampModel):
    ACTION_CHOICES = [
        ('DELTA',     'Delta'),
        ('OVERWRITE', 'Overwrite'),
        ('RESET',     'Reset to zero'),
        ('SUMMARY','Final summary'),
    ]
    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    session     = models.ForeignKey(PlanningSession, on_delete=models.CASCADE,
                                    related_name='requests')
    description = models.CharField(max_length=200, blank=True)
    action_type = models.CharField(max_length=20,choices=ACTION_CHOICES,default='DELTA',
        help_text="Delta: add on top of existing; Overwrite: replace; Reset: zero-out then write",
    )
    is_summary  = models.BooleanField(default=False,help_text="True if this request holds the final, rolled-up facts")
    def __str__(self): return f"{self.session} - {self.description or self.id}"
class PlanningFact(models.Model):
    request     = models.ForeignKey(DataRequest, on_delete=models.PROTECT)
    session     = models.ForeignKey(PlanningSession, on_delete=models.CASCADE)
    version     = models.ForeignKey(Version, on_delete=models.PROTECT)
    year        = models.ForeignKey(Year, on_delete=models.PROTECT)
    period      = models.ForeignKey(Period, on_delete=models.PROTECT)
    org_unit    = models.ForeignKey(OrgUnit, on_delete=models.PROTECT)
    service   = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT)
    account   = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT)
    extra_dimensions_json = models.JSONField(default=dict, help_text="Mapping of extra dimension name → selected dimension key: e.g. {'Position':123, 'SkillGroup':'Developer'}")
    key_figure  = models.ForeignKey(KeyFigure, on_delete=models.PROTECT)
    value       = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    uom         = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='+', null=True)
    ref_value   = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    ref_uom     = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='+', null=True)
    class Meta:
        indexes = [
            models.Index(fields=['session','period']),
            models.Index(fields=['session','org_unit','period']),
            models.Index(fields=['key_figure']),
        ]
    def __str__(self):
        return f"{self.key_figure}={self.value} | {self.service} | {self.period} | {self.org_unit}"
    def get_value_in(self, target_uom_code):
        if not self.uom:
            return None
        if self.uom.code == target_uom_code:
            return self.value
        to_uom = UnitOfMeasure.objects.get(code=target_uom_code, is_base=True)
        rate  = ConversionRate.objects.get(
            from_uom=self.uom,
            to_uom=to_uom
        ).factor
        return round(self.value * rate, 2)
from .models_view import *
class PlanningFactDimension(models.Model):
    fact       = models.ForeignKey(PlanningFact, on_delete=models.CASCADE, related_name="fact_dimensions")
    dimension = models.ForeignKey(PlanningLayoutDimension, on_delete=models.PROTECT)
    value_id   = models.PositiveIntegerField(help_text="PK of the chosen dimension value")
    class Meta:
        unique_together = (("fact", "dimension"),)
        indexes = [
            models.Index(fields=["dimension","value_id"]),
        ]
class DataRequestLog(TimestampModel):
    request     = models.ForeignKey(DataRequest, on_delete=models.CASCADE, related_name='log_entries')
    fact        = models.ForeignKey(PlanningFact, on_delete=models.CASCADE)
    old_value   = models.DecimalField(max_digits=18, decimal_places=2)
    new_value   = models.DecimalField(max_digits=18, decimal_places=2)
    def __str__(self):
        return f"{self.fact}: {self.old_value} → {self.new_value}"
class PlanningFunction(models.Model):
    FUNCTION_CHOICES = [
        ('COPY', 'Copy'),
        ('DISTRIBUTE', 'Distribute'),
        ('CURRENCY_CONVERT', 'Currency Convert'),
        ('REPOST',     'Re-Post'),
        ('RESET_SLICE',     'Reset Slice'),
    ]
    layout      = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE)
    name        = models.CharField(max_length=50)
    function_type = models.CharField(choices=FUNCTION_CHOICES, max_length=20)
    parameters   = models.JSONField(
        default=dict,
        help_text=
    )
    def execute(self, session):
        if self.function_type == 'COPY':
            return self._copy_data(session)
        if self.function_type == 'DISTRIBUTE':
            return self._distribute(session)
        if self.function_type == 'REPOST':
            return self._repost(session)
        if self.function_type == 'CURRENCY_CONVERT':
            return self._currency_convert(session)
        if self.function_type == 'RESET_SLICE':
            return self._reset_slice(session)
        return 0
    def _copy_data(self, session: PlanningSession) -> int:
        params = self.parameters
        src_version = session.layout_year.version
        tgt_version = get_object_or_404(Version, pk=params['to_version'])
        tgt_ly, _ = PlanningLayoutYear.objects.get_or_create(
            layout=session.layout_year.layout,
            year=session.layout_year.year,
            version=tgt_version,
        )
        tgt_sess, _ = PlanningSession.objects.get_or_create(
            layout_year=tgt_ly,
            org_unit=session.org_unit,
        )
        new_req = DataRequest.objects.create(
            session=tgt_sess,
            description=f"Copy from v{src_version.code}"
        )
        new_facts = []
        for fact in PlanningFact.objects.filter(session=session).iterator():
            new_facts.append(PlanningFact(
                request    = new_req,
                session    = tgt_sess,
                version    = tgt_version,
                year       = fact.year,
                period     = fact.period,
                org_unit   = fact.org_unit,
                service    = fact.service,
                account    = fact.account,
                extra_dimensions_json= fact.extra_dimensions_json,
                key_figure = fact.key_figure,
                value      = fact.value,
                uom        = fact.uom,
                ref_value  = fact.ref_value,
                ref_uom    = fact.ref_uom,
            ))
        PlanningFact.objects.bulk_create(new_facts)
        return len(new_facts)
    def _distribute(self, session: PlanningSession) -> int:
        by     = self.parameters['by']
        ref_nm = self.parameters['reference_data']
        ref    = get_object_or_404(ReferenceData, name=ref_nm)
        total = ref.fetch_reference_fact(**{by: None})['value__sum'] or 0
        if total == 0:
            return 0
        updated = 0
        with transaction.atomic():
            for fact in PlanningFact.objects.filter(session=session):
                proportion = fact.value / total
                fact.value = proportion * total
                fact.save(update_fields=['value'])
                updated += 1
        return updated
    def _currency_convert(self, session: PlanningSession) -> int:
        tgt_code = self.parameters['target_uom']
        tgt_uom  = get_object_or_404(UnitOfMeasure, code=tgt_code)
        conv_map = {
            (c.from_uom_id, c.to_uom_id): c.factor
            for c in ConversionRate.objects.filter(to_uom=tgt_uom)
        }
        updated = 0
        with transaction.atomic():
            for fact in PlanningFact.objects.filter(session=session):
                key = (fact.uom_id, tgt_uom.id)
                if key not in conv_map:
                    continue
                fact.value = round(fact.value * conv_map[key], 4)
                fact.uom   = tgt_uom
                fact.save(update_fields=['value','uom'])
                updated += 1
        return updated
    def _repost(self, session: PlanningSession) -> int:
        last_dr = session.requests.order_by('-created_at').first()
        if not last_dr:
            return 0
        new_dr = DataRequest.objects.create(
            session     = session,
            description = f"Re-Post of {last_dr.id}",
            created_by  = last_dr.created_by,
        )
        created = 0
        with transaction.atomic():
            for fact in PlanningFact.objects.filter(request=last_dr):
                fact.pk      = None
                fact.request = new_dr
                fact.save()
                created += 1
        return created
    def _reset_slice(self, session: PlanningSession) -> int:
        filters = self.parameters.get('filters', {})
        qs = PlanningFact.objects.filter(session=session, **filters)
        updated = qs.update(value=0, ref_value=0)
        return updated
class ReferenceData(models.Model):
    name = models.CharField(max_length=100)
    source_version = models.ForeignKey('Version', on_delete=models.CASCADE)
    source_year = models.ForeignKey('Year', on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    def fetch_reference_fact(self, **filters):
        return PlanningFact.objects.filter(
            session__scenario__layout_year__version=self.source_version,
            session__scenario__layout_year__year=self.source_year,
            **filters
        ).aggregate(Sum('value'))
class GlobalVariable(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    value = models.DecimalField(max_digits=18, decimal_places=6)
class Constant(models.Model):
    name  = models.CharField(max_length=100, unique=True)
    value = models.DecimalField(max_digits=18, decimal_places=6)
    def __str__(self):
        return f"{self.name} = {self.value}"
class SubFormula(models.Model):
    name = models.CharField(max_length=100)
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE, related_name='subformulas')
    expression = models.TextField(
        help_text="Expression using other constants/sub-formulas, e.g. [Year=2025]?.[Qty] * TAX_RATE"
    )
    class Meta:
        unique_together = ('layout', 'name')
    def __str__(self):
        return f"{self.name} ({self.layout})"
class Formula(models.Model):
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    expression = models.TextField(help_text="Supports conditional logic, loops, and aggregation.")
    dimensions = models.ManyToManyField(ContentType, help_text="Multiple dimensions for looping")
    reference_version = models.ForeignKey('Version', null=True, blank=True, on_delete=models.SET_NULL)
    reference_year = models.ForeignKey('Year', null=True, blank=True, on_delete=models.SET_NULL)
    def __str__(self):
        return f"{self.name} ({self.layout})"
class FormulaRun(models.Model):
    formula   = models.ForeignKey(Formula, on_delete=models.CASCADE)
    run_at    = models.DateTimeField(auto_now_add=True)
    preview   = models.BooleanField(default=False)
    run_by    = models.ForeignKey(settings.AUTH_USER_MODEL,
                                  null=True, on_delete=models.SET_NULL)
    def __str__(self): return f"Run
class FormulaRunEntry(models.Model):
    run        = models.ForeignKey(FormulaRun, related_name='entries', on_delete=models.CASCADE)
    record     = models.ForeignKey('PlanningFact', on_delete=models.CASCADE)
    key        = models.CharField(max_length=100)
    old_value  = models.DecimalField(max_digits=18, decimal_places=6)
    new_value  = models.DecimalField(max_digits=18, decimal_places=6)
    def __str__(self): return f"{self.record} :: {self.key}: {self.old_value} → {self.new_value}"
```

### `models/models_access.py`
```python
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import Q
from .models_dimension import OrgUnit
User = settings.AUTH_USER_MODEL
class OrgUnitAccess(models.Model):
    EXACT = "EXACT"
    SUBTREE = "SUBTREE"
    SCOPE_CHOICES = [(EXACT, "Exact"), (SUBTREE, "Subtree")]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ou_access")
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.CASCADE, related_name="user_access")
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default=SUBTREE)
    can_edit = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ("user", "org_unit", "scope")
    def __str__(self):
        return f"{self.user} → {self.org_unit} [{self.scope}]"
    def units_qs(self):
        base = OrgUnit.objects.filter(pk=self.org_unit_id)
        if self.scope == self.SUBTREE:
            return base.union(self.org_unit.get_descendants())
        return base
    @classmethod
    def scope_for_user(cls, user, *, include_delegations=True):
        qs = OrgUnit.objects.none()
        for access in cls.objects.filter(user=user).select_related("org_unit"):
            qs = qs.union(access.units_qs())
        if include_delegations:
            now = timezone.now()
            dels = Delegation.objects.filter(
                delegatee=user,
                active=True
            ).filter(
                Q(starts_at__isnull=True) | Q(starts_at__lte=now),
                Q(ends_at__isnull=True)   | Q(ends_at__gte=now),
            ).select_related("delegator")
            if dels.exists():
                delegator_ids = list(dels.values_list("delegator_id", flat=True))
                for access in cls.objects.filter(user_id__in=delegator_ids).select_related("org_unit"):
                    qs = qs.union(access.units_qs())
        return qs.distinct()
    @classmethod
    def can_edit_orgunit(cls, user, org_unit, *, include_delegations=True):
        anc_ids = list(org_unit.get_ancestors().values_list("id", flat=True)) + [org_unit.id]
        base = cls.objects.filter(user=user, can_edit=True).filter(
            Q(scope=cls.EXACT, org_unit_id=org_unit.id) |
            Q(scope=cls.SUBTREE, org_unit_id__in=anc_ids)
        )
        if base.exists():
            return True
        if include_delegations:
            now = timezone.now()
            delegator_ids = list(
                Delegation.objects.filter(
                    delegatee=user, active=True
                ).filter(
                    Q(starts_at__isnull=True) | Q(starts_at__lte=now),
                    Q(ends_at__isnull=True)   | Q(ends_at__gte=now),
                ).values_list("delegator_id", flat=True)
            )
            if delegator_ids:
                via_del = cls.objects.filter(user_id__in=delegator_ids, can_edit=True).filter(
                    Q(scope=cls.EXACT, org_unit_id=org_unit.id) |
                    Q(scope=cls.SUBTREE, org_unit_id__in=anc_ids)
                )
                if via_del.exists():
                    return True
        return False
class Delegation(models.Model):
    delegator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="delegations_out")
    delegatee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="delegations_in")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    note = models.CharField(max_length=200, blank=True)
    class Meta:
        unique_together = ("delegator", "delegatee")
    def is_active(self):
        now = timezone.now()
        if not self.active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True
    def __str__(self):
        return f"{self.delegator} → {self.delegatee}"
```

### `models/models_dimension.py`
```python
from django.conf import settings
from django.db import models, transaction
from treebeard.mp_tree import MP_Node
class InfoObject(models.Model):
    code        = models.CharField(max_length=20, unique=True)
    name        = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    order       = models.IntegerField(default=0,
                      help_text="Controls ordering in UIs")
    class Meta:
        abstract = True
        ordering = ['order', 'code']
    def __str__(self):
        return self.name
class Year(InfoObject):
    pass
class Version(InfoObject):
    is_public = models.BooleanField(default=True, help_text="Public versions are visible to everyone; private only to creator")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="For private versions, track the owner"
    )
    class Meta(InfoObject.Meta):
        ordering = ['order', 'code']
class OrgUnit(MP_Node, InfoObject):
    head_user      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bps_orgunits_headed',
        related_query_name='bps_orgunit_headed',
        help_text="OrgUnit lead who must draft and approve"
    )
    cc_code    = models.CharField(max_length=10, blank=True)
    node_order_by = ['order', 'code']
class CBU(InfoObject):
    group       = models.CharField(max_length=50, blank=True)
    TIER_CHOICES = [('1','Tier-1'),('2','Tier-2'),('3','Tier-3')]
    tier        = models.CharField(max_length=1, choices=TIER_CHOICES)
    region      = models.CharField(max_length=50, blank=True)
    is_active   = models.BooleanField(default=True)
    node_order_by = ['group', 'code']
    def __str__(self):
        return f"{self.code} - {self.name}"
class Account(InfoObject):
    pass
class Service(InfoObject):
    category         = models.CharField(max_length=50)
    subcategory      = models.CharField(max_length=50)
    related_services = models.ManyToManyField('self', blank=True)
    orgunit      = models.ForeignKey('OrgUnit',on_delete=models.SET_NULL,null=True, blank=True)
    is_active        = models.BooleanField(default=True)
    class Meta:
        ordering = ['category','subcategory','code']
    def __str__(self):
        return f"{self.code} – {self.name}"
class CostCenter(InfoObject):
    pass
class InternalOrder(InfoObject):
    cc_code    = models.CharField(max_length=10, blank=True)
class PriceType(InfoObject):
    pass
```

### `models/models_function.py`
```python
from django.db import models, transaction
```

### `models/models_layout.py`
```python
from django.db import models, transaction
from django.contrib.contenttypes.models import ContentType
from .models_dimension import Year, Version, OrgUnit
SHORT_LABELS = {
    "orgunit": "OU",
    "service": "Srv",
    "internalorder": "IO",
    "position": "Pos",
    "skill": "Skill",
}
EXCLUDE_FROM_CONTEXT = {"year", "version", "period"}
def _resolve_value(Model, raw):
    if not raw:
        return None
    if isinstance(raw, int):
        return Model.objects.filter(pk=raw).first()
    if hasattr(Model, "code"):
        return Model.objects.filter(code=raw).first()
    return Model.objects.filter(pk=raw).first()
class PlanningLayout(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    domain = models.CharField(max_length=100)
    default = models.BooleanField(default=False)
    def __str__(self):
        return self.code
class PlanningLayoutDimension(models.Model):
    layout        = models.ForeignKey(
        PlanningLayout, related_name="dimensions", on_delete=models.CASCADE
    )
    content_type  = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    is_row        = models.BooleanField(default=False)
    is_column     = models.BooleanField(default=False)
    is_header     = models.BooleanField(
        default=False,
        help_text="If true, UI should render a header selector for this dimension."
    )
    order         = models.PositiveSmallIntegerField(default=0,
                      help_text="Defines the sequence in the grid")
    group_priority = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="1,2,3… to enable nested row grouping (lower = outer); leave blank to not group by this dimension."
    )
    class Meta:
        ordering = ["order", "id"]
        unique_together = ("layout", "content_type", "is_row", "is_column", "is_header")
class PlanningLayoutYear(models.Model):
    layout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE, related_name='per_year')
    year   = models.ForeignKey(Year, on_delete=models.CASCADE)
    version= models.ForeignKey(Version, on_delete=models.CASCADE)
    org_units = models.ManyToManyField(OrgUnit, blank=True)
    header_dims = models.JSONField(default=dict, help_text="e.g. {'Company':3,'Region':'NA'}")
    class Meta:
        unique_together = ('layout','year','version')
    def __str__(self):
        return f"{self.layout.name} – {self.year.code} / {self.version.code}"
    def header_defaults(self):
        base = dict(self.header_dims or {})
        return base
    def header_pairs(self, *, use_short_labels=True, short_values=True, exclude=EXCLUDE_FROM_CONTEXT):
        pairs = []
        defaults = self.header_defaults()
        dims = self.layout.dimensions.filter(is_header=True).select_related("content_type").order_by("order")
        for dim in dims:
            ct = dim.content_type
            key = ct.model
            if key in (exclude or set()):
                continue
            Model = ct.model_class()
            label = SHORT_LABELS.get(key, Model._meta.verbose_name.title() if not use_short_labels else key[:3].title())
            raw = defaults.get(key)
            inst = _resolve_value(Model, raw)
            if not inst:
                val = "All"
            else:
                val = getattr(inst, "code", None) or getattr(inst, "name", str(inst))
            pairs.append((label, val))
        return pairs
    def header_string(self, exclude=EXCLUDE_FROM_CONTEXT):
        return " · ".join(f"{k}: {v}" for k, v in self.header_pairs(exclude=exclude))
class LayoutDimensionOverride(models.Model):
    layout_year      = models.ForeignKey(PlanningLayoutYear, related_name="dimension_overrides", on_delete=models.CASCADE)
    dimension = models.ForeignKey(PlanningLayoutDimension, related_name="overrides", on_delete=models.CASCADE)
    allowed_values   = models.JSONField(blank=True, default=list)
    filter_criteria  = models.JSONField(blank=True, default=dict)
    header_selection = models.PositiveIntegerField(null=True, blank=True)
    order_override   = models.PositiveSmallIntegerField(null=True, blank=True)
    class Meta:
        unique_together = ("layout_year", "dimension")
class PlanningKeyFigure(models.Model):
    layout        = models.ForeignKey(PlanningLayout, related_name="key_figures", on_delete=models.CASCADE)
    key_figure    = models.ForeignKey('bps.KeyFigure', on_delete=models.CASCADE)
    is_editable   = models.BooleanField(default=True)
    is_computed   = models.BooleanField(default=False)
    formula       = models.TextField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    class Meta:
        ordering = ["display_order", "id"]
        unique_together = ("layout", "key_figure")
```

### `models/models_period.py`
```python
from django.db import models, transaction
class Period(models.Model):
    code   = models.CharField(max_length=2, unique=True)
    name   = models.CharField(max_length=10)
    order  = models.PositiveSmallIntegerField()
    def __str__(self):
        return self.name
class PeriodGrouping(models.Model):
    layout_year = models.ForeignKey('bps.PlanningLayoutYear', on_delete=models.CASCADE,
                                    related_name='period_groupings')
    months_per_bucket = models.PositiveSmallIntegerField(choices=[(1,'Monthly'),(3,'Quarterly'),(6,'Half-Year')])
    label_prefix = models.CharField(max_length=5, default='')
    class Meta:
        unique_together = ('layout_year','months_per_bucket')
    def buckets(self):
        months = list(Period.objects.order_by('order'))
        size = self.months_per_bucket
        buckets = []
        for i in range(0, 12, size):
            group = months[i:i+size]
            if size == 1:
                code = group[0].code
                name = group[0].name
            else:
                idx = (i // size) + 1
                code = f"{self.label_prefix}{idx}"
                name = code
            buckets.append({'code': code, 'name': name, 'periods': group})
        return buckets
```

### `models/models_resource.py`
```python
from django.db import models, transaction
from .models_dimension import *
class Skill(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    def __str__(self): return self.name
class RateCard(models.Model):
    RESOURCE_CHOICES = [('EMP', 'Employee'), ('CON','Contractor'), ('MSP','MSP')]
    year = models.ForeignKey('Year', on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT)
    level             = models.CharField(max_length=20)
    resource_type       = models.CharField(max_length=20, choices=RESOURCE_CHOICES)
    country           = models.CharField(max_length=50)
    efficiency_factor = models.DecimalField(default=1.00, max_digits=5, decimal_places=2,
                                            help_text="0.00-1.00")
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    class Meta:
        unique_together = ('year','skill','level','resource_type','country')
        ordering = ['skill','level','resource_type','country']
        verbose_name = "Rate Card Template"
        verbose_name_plural = "Rate Card Templates"
    def __str__(self):
        return (f"{self.resource_type} | {self.skill} ({self.level}) @ "
                f"{self.country}")
class Resource(models.Model):
    RESOURCE_TYPES = [
        ('EMP', 'Employee'),
        ('CON', 'Contractor'),
        ('MSP','MSP Staff'),
    ]
    unique_id         = models.CharField(max_length=100, unique=True)
    display_name      = models.CharField(max_length=255)
    resource_type     = models.CharField(max_length=3, choices=RESOURCE_TYPES)
    current_skill     = models.ForeignKey(Skill,  on_delete=models.SET_NULL, null=True)
    current_level     = models.CharField(max_length=20, blank=True, null=True)
    country           = models.CharField(max_length=50, blank=True)
    def __str__(self):
        return self.display_name
class Employee(Resource):
    employee_id       = models.CharField(max_length=20, unique=True)
    hire_date         = models.DateField()
    annual_salary     = models.DecimalField(max_digits=12, decimal_places=2)
class Vendor(models.Model):
    name = models.CharField(max_length=255, unique=True)
    vendor_type = models.CharField(max_length=20, choices=RateCard.RESOURCE_CHOICES[1:])
    def __str__(self):
        return self.name
class Contractor(Resource):
    vendor            = models.ForeignKey(Vendor, on_delete=models.PROTECT)
    contract_id       = models.CharField(max_length=50, unique=True)
    contract_start    = models.DateField()
    contract_end      = models.DateField()
class MSPStaff(Resource):
    pass
class Position(InfoObject):
    code        = models.CharField(max_length=20)
    year        = models.ForeignKey(Year, on_delete=models.CASCADE)
    skill       = models.ForeignKey(Skill, on_delete=models.PROTECT)
    level       = models.CharField(max_length=20)
    orgunit     = models.ForeignKey(OrgUnit, on_delete=models.PROTECT, null=True, blank=True)
    fte         = models.FloatField(default=1.0)
    is_open     = models.BooleanField(default=False)
    intended_resource_type = models.CharField(
        max_length=20,
        choices=RateCard.RESOURCE_CHOICES,
        default='EMP',
        help_text="Intended category for this position (Employee, Contractor, MSP). Used for budgeting if 'is_open' is True."
    )
    filled_by_resource = models.ForeignKey(Resource, on_delete=models.SET_NULL, null=True, blank=True,
                                            help_text="The specific person filling this position.")
    class Meta(InfoObject.Meta):
        unique_together = ('year', 'code')
        ordering = ['year__code', 'order', 'code']
    def __str__(self):
        status = 'Open' if self.is_open else 'Filled'
        return f"[{self.year.code}] {self.code} ({self.skill}/{self.level}) - {status}"
```

### `models/models_view.py`
```python
from django.db import models
class PivotedPlanningFact(models.Model):
    version = models.CharField(max_length=50)
    year = models.IntegerField()
    org_unit = models.CharField(max_length=50)
    service = models.CharField(max_length=50)
    account = models.CharField(max_length=50)
    extra_dimensions_json = models.JSONField()
    key_figure = models.CharField(max_length=50)
    v01 = models.FloatField(null=True, blank=True)
    v02 = models.FloatField(null=True, blank=True)
    v03 = models.FloatField(null=True, blank=True)
    v04 = models.FloatField(null=True, blank=True)
    v05 = models.FloatField(null=True, blank=True)
    v06 = models.FloatField(null=True, blank=True)
    v07 = models.FloatField(null=True, blank=True)
    v08 = models.FloatField(null=True, blank=True)
    v09 = models.FloatField(null=True, blank=True)
    v10 = models.FloatField(null=True, blank=True)
    v11 = models.FloatField(null=True, blank=True)
    v12 = models.FloatField(null=True, blank=True)
    r01 = models.FloatField(null=True, blank=True)
    r02 = models.FloatField(null=True, blank=True)
    r03 = models.FloatField(null=True, blank=True)
    r04 = models.FloatField(null=True, blank=True)
    r05 = models.FloatField(null=True, blank=True)
    r06 = models.FloatField(null=True, blank=True)
    r07 = models.FloatField(null=True, blank=True)
    r08 = models.FloatField(null=True, blank=True)
    r09 = models.FloatField(null=True, blank=True)
    r10 = models.FloatField(null=True, blank=True)
    r11 = models.FloatField(null=True, blank=True)
    r12 = models.FloatField(null=True, blank=True)
    total_value = models.FloatField(null=True, blank=True)
    total_reference = models.FloatField(null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'pivoted_planningfact'
```

### `models/models_workflow.py`
```python
from django.db import models, transaction
from django.conf import settings
from .models_dimension import OrgUnit
class PlanningStage(models.Model):
    code       = models.CharField(max_length=20, unique=True)
    name       = models.CharField(max_length=100)
    order      = models.PositiveSmallIntegerField(
                   help_text="Determines execution order. Lower=earlier.")
    can_run_in_parallel = models.BooleanField(
                   default=False,
                   help_text="If True, this step may execute alongside others.")
    class Meta:
        ordering = ['order']
    def __str__(self):
        return f"{self.order}: {self.name}"
class PlanningScenario(models.Model):
    code        = models.CharField(max_length=50, unique=True)
    name        = models.CharField(max_length=200)
    layout_year = models.ForeignKey('bps.PlanningLayoutYear', on_delete=models.CASCADE)
    org_units   = models.ManyToManyField(OrgUnit, through='ScenarioOrgUnit')
    stages      = models.ManyToManyField(PlanningStage, through='ScenarioStage')
    functions   = models.ManyToManyField('bps.PlanningFunction', through='ScenarioFunction')
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
class ScenarioOrgUnit(models.Model):
    scenario   = models.ForeignKey(PlanningScenario, on_delete=models.CASCADE)
    org_unit   = models.ForeignKey(OrgUnit, on_delete=models.CASCADE)
    order      = models.PositiveSmallIntegerField()
    class Meta:
        unique_together = ('scenario','org_unit')
        ordering = ['order']
class ScenarioStage(models.Model):
    scenario = models.ForeignKey(PlanningScenario, on_delete=models.CASCADE)
    stage    = models.ForeignKey(PlanningStage, on_delete=models.CASCADE)
    order    = models.PositiveSmallIntegerField()
    class Meta:
        unique_together = ('scenario','stage')
        ordering = ['order']
class ScenarioStep(models.Model):
    scenario    = models.ForeignKey(PlanningScenario, on_delete=models.CASCADE)
    stage       = models.ForeignKey(PlanningStage, on_delete=models.CASCADE)
    layout      = models.ForeignKey('bps.PlanningLayout', on_delete=models.PROTECT)
    order       = models.PositiveSmallIntegerField()
    class Meta:
        unique_together = ('scenario','stage', 'layout')
        ordering = ['order']
class ScenarioFunction(models.Model):
    scenario  = models.ForeignKey(PlanningScenario, on_delete=models.CASCADE)
    function  = models.ForeignKey('bps.PlanningFunction', on_delete=models.CASCADE)
    order     = models.PositiveSmallIntegerField()
    class Meta:
        unique_together = ('scenario','function')
        ordering = ['order']
class PlanningSession(models.Model):
    scenario      = models.ForeignKey(PlanningScenario, on_delete=models.CASCADE, related_name='sessions')
    org_unit    = models.ForeignKey(OrgUnit, on_delete=models.CASCADE,
                                    help_text="Owner of this session")
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    class Status(models.TextChoices):
        DRAFT     = 'D','Draft'
        FEEDBACK  = 'B','Return Back'
        COMPLETED = 'C','Completed'
        REVIEW    = 'R','Review'
        FROZEN    = 'F','Frozen'
    status      = models.CharField(max_length=1,
                                   choices=Status.choices,
                                   default=Status.DRAFT)
    frozen_by   = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='+')
    frozen_at   = models.DateTimeField(null=True, blank=True)
    current_step = models.ForeignKey(ScenarioStep, on_delete=models.PROTECT)
    class Meta:
        unique_together = ('scenario','org_unit')
    def __str__(self):
        return f"{self.org_unit.name} - {self.layout_year}"
    @property
    def layout_year(self):
        return self.scenario.layout_year
    def can_edit(self, user):
        if self.status == self.Status.DRAFT and user == self.org_unit.head_user:
            return True
        return False
    def complete(self, user):
        if user == self.org_unit.head_user:
            self.status = self.Status.COMPLETED
            self.save()
    def freeze(self, user):
        self.status    = self.Status.FROZEN
        self.frozen_by = user
        self.frozen_at = models.functions.Now()
        self.save()
```

### `serializers.py`
```python
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
```

### `templates/admin/bps/planning_dashboard.html`
```html
{% extends "admin/change_list.html" %}
{% load static %}
{% block content_title %}<h1>{{ title }}</h1>{% endblock %}
{% block result_list %}
<div class="dashboard">
  <div class="cards">
    <div class="card">
      <h3>1) Create/Review Layouts</h3>
      <p>Define template, dimensions, and key figures.</p>
      <a class="button" href="{% url 'admin:bps_planninglayout_changelist' %}">Open Layouts</a>
    </div>
    <div class="card">
      <h3>2) Instantiate Year/Version</h3>
      <p>Create PlanningLayoutYear and set header defaults & period groupings.</p>
      <a class="button" href="{% url 'admin:bps_planninglayoutyear_changelist' %}">Open Layout Years</a>
    </div>
    <div class="card">
      <h3>3) Scenarios & Org Units</h3>
      <p>Create scenarios, attach org units, and steps.</p>
      <a class="button" href="{% url 'admin:bps_planningscenario_changelist' %}">Open Scenarios</a>
    </div>
    <div class="card">
      <h3>4) Quick Actions</h3>
      <p><a href="{% url 'admin:bps_period_changelist' %}">Periods</a> •
         <a href="{% url 'admin:bps_year_changelist' %}">Years</a> •
         <a href="{% url 'admin:bps_version_changelist' %}">Versions</a> •
         <a href="{% url 'admin:bps_orgunit_changelist' %}">Org Units</a></p>
    </div>
  </div>
  <h2>Current Layouts</h2>
  <table class="listing">
    <thead><tr><th>Code</th><th>Name</th><th>#Dims</th><th>#KFs</th><th>Actions</th></tr></thead>
    <tbody>
      {% for l in layouts %}
      <tr>
        <td>{{ l.code }}</td>
        <td>{{ l.name }}</td>
        <td>{{ l.n_dims }}</td>
        <td>{{ l.n_kf }}</td>
        <td>
          <a href="{% url 'admin:bps_planninglayout_change' l.pk %}">Edit</a> •
          <a href="{% url 'admin:bps_planninglayoutyear_changelist' %}?layout__id__exact={{ l.pk }}">Year/Version</a>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

### `templates/bps/_action_reset.html`
```html
<button class="btn btn-sm btn-danger" onclick="resetData()">
  🔄 Reset All
</button>
<script>
function resetData() {
  if (!confirm("This will zero out all existing values before saving. Continue?")) return;
  fetch("{% url 'bps_api:planning_grid_update' %}", {
    method: "PATCH",
    headers: {
      "Content-Type":"application/json",
      "X-CSRFToken":"{{ csrf_token }}"
    },
    body: JSON.stringify({
      layout:   {{ layout.id }},
      action_type: "RESET",
      updates: []  // no individual cells needed, reset happens before manual edits
    })
  }).then(_=>{
    table.replaceData();  // reload the grid
    alert("All values have been reset to zero.");
  });
}
</script>
```

### `templates/bps/_paginator.html`
```html
{% if is_paginated %}
<div class="d-flex align-items-center flex-wrap gap-2 my-2">
  <nav aria-label="Pagination">
    <ul class="pagination pagination-sm mb-0">
      {# First / Prev #}
      <li class="page-item {% if not page_obj.has_previous %}disabled{% endif %}">
        <a class="page-link"
           href="?page=1{% if sanitized_query %}&{{ sanitized_query }}{% endif %}">First</a>
      </li>
      <li class="page-item {% if not page_obj.has_previous %}disabled{% endif %}">
        {% if page_obj.has_previous %}
          <a class="page-link"
             href="?page={{ page_obj.previous_page_number }}{% if sanitized_query %}&{{ sanitized_query }}{% endif %}">Prev</a>
        {% else %}
          <span class="page-link">Prev</span>
        {% endif %}
      </li>
      {# Numbered window: current-3 .. current+3, with edge links + ellipses #}
      {% with start=page_obj.number|add:"-3" end=page_obj.number|add:"3" %}
        {# clamp bounds in logic below #}
        {# Show page 1 and leading ellipsis if window starts after 2 #}
        {% if start|add:"-1" > 1 %}
          <li class="page-item">
            <a class="page-link"
               href="?page=1{% if sanitized_query %}&{{ sanitized_query }}{% endif %}">1</a>
          </li>
          {% if start > 2 %}
            <li class="page-item disabled"><span class="page-link">…</span></li>
          {% endif %}
        {% endif %}
        {# Main window #}
        {% for num in page_obj.paginator.page_range %}
          {% if num >= start and num <= end and num >= 1 and num <= page_obj.paginator.num_pages %}
            <li class="page-item {% if page_obj.number == num %}active{% endif %}">
              {% if page_obj.number == num %}
                <span class="page-link">{{ num }}</span>
              {% else %}
                <a class="page-link"
                   href="?page={{ num }}{% if sanitized_query %}&{{ sanitized_query }}{% endif %}">{{ num }}</a>
              {% endif %}
            </li>
          {% endif %}
        {% endfor %}
        {# Trailing ellipsis and last page if window ends before last-1 #}
        {% if end|add:"1" < page_obj.paginator.num_pages %}
          {% if end < page_obj.paginator.num_pages|add:"-1" %}
            <li class="page-item disabled"><span class="page-link">…</span></li>
          {% endif %}
          <li class="page-item">
            <a class="page-link"
               href="?page={{ page_obj.paginator.num_pages }}{% if sanitized_query %}&{{ sanitized_query }}{% endif %}">{{ page_obj.paginator.num_pages }}</a>
          </li>
        {% endif %}
      {% endwith %}
      {# Next / Last #}
      <li class="page-item {% if not page_obj.has_next %}disabled{% endif %}">
        {% if page_obj.has_next %}
          <a class="page-link"
             href="?page={{ page_obj.next_page_number }}{% if sanitized_query %}&{{ sanitized_query }}{% endif %}">Next</a>
        {% else %}
          <span class="page-link">Next</span>
        {% endif %}
      </li>
      <li class="page-item {% if not page_obj.has_next %}disabled{% endif %}">
        <a class="page-link"
           href="?page={{ page_obj.paginator.num_pages }}{% if sanitized_query %}&{{ sanitized_query }}{% endif %}">Last</a>
      </li>
    </ul>
  </nav>
  <form method="get" class="ms-auto d-flex align-items-center gap-2">
    {# Preserve existing query params except page/page_size #}
    {% for key, value in request.GET.items %}
      {% if key != 'page' and key != 'page_size' %}
        <input type="hidden" name="{{ key }}" value="{{ value }}">
      {% endif %}
    {% endfor %}
    <input type="hidden" name="page" value="1">
    <label for="pg-size" class="form-label mb-0 small text-nowrap">Rows per page</label>
    <select id="pg-size" name="page_size" class="form-select form-select-sm" onchange="this.form.submit()">
      {% for size in page_sizes %}
        <option value="{{ size }}" {% if page_size == size %}selected{% endif %}>{{ size }}</option>
      {% endfor %}
    </select>
  </form>
</div>
{% endif %}
```

### `templates/bps/_tabulator.html`
```html
{# templates/bps/_tabulator.html #}
<link
  rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/tabulator-tables@6.3.1/dist/css/tabulator_bootstrap5.min.css"
/>
<div
  id="tabulator-app"
  data-api-url="{{ api_url }}"
  data-detail-tmpl="{{ detail_url }}"
  data-change-tmpl="{{ change_url }}"
  data-create-url="{{ create_url }}"
  data-export-url="{{ export_url }}"
  data-owner-update-tmpl="{{ owner_update_url }}"
  data-orgunit-update-tmpl="{{ orgunit_update_url }}"
  data-user-autocomplete-url="{{ user_ac_url }}"
  data-orgunit-autocomplete-url="{{ orgunit_ac_url }}"
></div>
<script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js"></script>
<script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/tabulator-tables@6.3/dist/js/tabulator.min.js"></script>
<script>
// --- CSRF helper ---
function getCookie(name) {
  let v = null;
  document.cookie.split(';').forEach(c => {
    c = c.trim();
    if (c.startsWith(name + '=')) {
      v = decodeURIComponent(c.slice(name.length + 1));
    }
  });
  return v;
}
const csrftoken = getCookie("csrftoken");
// --- style for editable cells ---
const style = document.createElement("style");
style.innerHTML = `
  .tabulator-cell.editable-cell {
    background-color: #fff8dc !important;
  }
`;
document.head.appendChild(style);
// --- generic autocomplete editor factory ---
function makeAutocompleteEditor(endpoint) {
  return function(cell, onRendered, success, cancel) {
    const input = document.createElement("input");
    input.type = "search";
    input.placeholder = "Search…";
    input.value = cell.getValue()?.display || "";
    Object.assign(input.style, {
      padding: "4px",
      width: "100%",
      boxSizing: "border-box"
    });
    onRendered(() => input.focus());
    let list;
    const lookup = async term => {
      const res = await axios.get(endpoint, {
        params: { q: term },
        withCredentials: true,
        headers: { "X-CSRFToken": csrftoken }
      });
      return res.data.results.map(u => ({
        label: u.text,
        value: u.id
      }));
    };
    const showList = async () => {
      const items = await lookup(input.value);
      if (list) list.remove();
      list = document.createElement("div");
      list.className = "list-group";
      Object.assign(list.style, {
        position: "absolute",
        zIndex: 10000,
        maxHeight: "150px",
        overflowY: "auto"
      });
      items.forEach(it => {
        const a = document.createElement("a");
        a.className = "list-group-item list-group-item-action";
        a.innerText = it.label;
        a.onclick = () => {
          success({ id: it.value, display: it.label });
          list.remove();
        };
        list.appendChild(a);
      });
      document.body.appendChild(list);
      const r = input.getBoundingClientRect();
      list.style.top = `${r.bottom}px`;
      list.style.left = `${r.left}px`;
      document.addEventListener("click", () => list.remove(), {
        once: true
      });
    };
    input.addEventListener("input", showList);
    input.addEventListener("blur", () => setTimeout(cancel, 150));
    return input;
  };
}
// --- mount Tabulator inside Vue ---
const { createApp, onMounted } = Vue;
createApp({
  setup() {
    const el = document.getElementById("tabulator-app");
    // pull in the data-attributes
    const API        = el.dataset.apiUrl;
    const DETAIL_TPL = el.dataset.detailTmpl;
    const CHANGE_TPL = el.dataset.changeTmpl;
    const CREATE_URL = el.dataset.createUrl;
    const EXPORT_URL = el.dataset.exportUrl;
    const OWNER_TPL  = el.dataset.ownerUpdateTmpl;
    const OU_TPL     = el.dataset.orgunitUpdateTmpl;
    const USER_AC    = el.dataset.userAutocompleteUrl;
    const OU_AC      = el.dataset.orgunitAutocompleteUrl;
    // simple helper to replace the placeholder "0" in e.g. ".../0/" with a real id
    function makeUrl(tmpl, id) {
      return tmpl.replace(/\/0\//, `/${id}/`);
    }
    const userEditor    = makeAutocompleteEditor(USER_AC);
    const orgunitEditor = makeAutocompleteEditor(OU_AC);
    onMounted(() => {
      el.innerHTML = `
<div class="container-fluid mt-2">
  <div class="d-flex justify-content-between mb-3">
    <h4>Planning Data</h4>
    <div class="btn-toolbar">
      <input id="grid-search" class="form-control me-2" placeholder="Search…">
      <button id="btn-add" class="btn btn-primary me-2">
        <i class="bi bi-plus-lg"></i> Add
      </button>
      <button id="btn-export" class="btn btn-secondary">
        <i class="bi bi-download"></i> Export
      </button>
    </div>
  </div>
  <div id="grid-table"></div>
</div>`;
      const table = new Tabulator("#grid-table", {
        layout: "fitDataStretch",
        ajaxURL: API,
        ajaxConfig: { credentials: "include" },
        pagination: "remote",
        paginationSize: 20,
        paginationDataSent: { page: "page", size: "page_size" },
        paginationDataReceived: { last_page: "last_page" },
        ajaxResponse: (url, params, res) => ({
          data: res.results,
          last_page: Math.ceil(res.count / params.size)
        }),
        columns: [
          { title: "#", formatter: "rownum", width: 50 },
          {
            title: "Org Unit",
            field: "org_unit",
            formatter: cell => cell.getValue()?.display || ""
          },
          {
            title: "Service",
            field: "service",
            formatter: cell => cell.getValue()?.display || ""
          },
          { title: "Key Figure", field: "key_figure" },
          {
            title: "Value",
            field: "value",
            editor: "input",
            cellEdited: cell => {
              const d = cell.getRow().getData();
              axios
                .patch(
                  makeUrl(CHANGE_TPL, d.id),
                  { [cell.getField()]: cell.getValue() },
                  {
                    withCredentials: true,
                    headers: { "X-CSRFToken": csrftoken }
                  }
                )
                .catch(() => cell.restoreOldValue());
            }
          }
        ]
      });
      // wire up search
      document
        .getElementById("grid-search")
        .addEventListener("input", e => {
          table.setFilter("service", "like", e.target.value);
          table.setPage(1);
        });
      // "Add" goes straight to your create-URL
      document
        .getElementById("btn-add")
        .addEventListener("click", () => (window.location = CREATE_URL));
      // Export CSV
      document
        .getElementById("btn-export")
        .addEventListener("click", () =>
          table.download("csv", "planning_export.csv")
        );
    });
  }
}).mount("#tabulator-app");
</script>
```

### `templates/bps/base.html`
```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Enterprise Planning{% endblock %}</title>
    <link href="{% static 'css/bootstrap.min.css' %}" rel="stylesheet">
    <link href="{% static 'css/bootstrap-icons.css' %}" rel="stylesheet">
    <link href="{% static 'css/custom.css' %}" rel="stylesheet">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light bg-light shadow-sm">
        <div class="container-fluid">
            <a class="navbar-brand" href="{% url 'bps:dashboard' %}">CorpPlanner</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarMain" aria-controls="navbarMain" aria-expanded="false" aria-label="Toggle navigation">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarMain">
                <ul class="navbar-nav me-auto mb-2 mb-lg-0">
                    {% block nav_links %}
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'bps:inbox' %}"><i class="bi bi-inbox"></i> Inbox</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'bps:notifications' %}"><i class="bi bi-bell"></i> Notifications</a>
                    </li>
                    {% endblock %}
                </ul>
                <ul class="navbar-nav ms-auto mb-2 mb-lg-0">
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="userDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                            <i class="bi bi-person-circle"></i> {{ request.user.get_full_name }}
                        </a>
                        <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="userDropdown">
                            <li><a class="dropdown-item" href="{% url 'bps:profile' %}">Profile</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item" href="{% url 'logout' %}">Logout</a></li>
                        </ul>
                    </li>
                </ul>
            </div>
        </div>
    </nav>
    <div class="container-fluid mt-3">
        {% if breadcrumbs %}
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                {% for crumb in breadcrumbs %}
                <li class="breadcrumb-item {% if forloop.last %}active{% endif %}" {% if forloop.last %}aria-current="page"{% endif %}>
                    {% if not forloop.last %}
                    <a href="{{ crumb.url }}">{{ crumb.title }}</a>
                    {% else %}
                    {{ crumb.title }}
                    {% endif %}
                </li>
                {% endfor %}
            </ol>
        </nav>
        {% endif %}
        {% if messages %}
            {% for message in messages %}
            <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                {{ message }}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
            {% endfor %}
        {% endif %}
        {% block content %}{% endblock %}
    </div>
    <script src="{% static 'js/bootstrap.bundle.min.js' %}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### `templates/bps/constant_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<h1>Constants</h1>
<form method="post" class="mb-4">{% csrf_token %}
  {{ form|crispy }}
</form>
<table class="table">
  <thead><tr><th>Name</th><th>Value</th></tr></thead>
  <tbody>
    {% for c in consts %}
      <tr><td>{{ c.name }}</td><td>{{ c.value }}</td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

### `templates/bps/dashboard.html`
```html
{% extends "bps/base.html" %}
{% load static %}
{% block content %}
<div class="container py-4">
  <h1 class="mb-4">Planning Dashboard</h1>
  <div class="row mb-4">
    <div class="col-md-4">
      <div class="card">
        <div class="card-header">Select Planning Year</div>
        <div class="card-body p-3">
          <form method="get">
            <select name="year" class="form-select" onchange="this.form.submit()">
              {% for y in all_years %}
                <option value="{{ y }}" {% if y == selected_year %}selected{% endif %}>
                  {{ y }}
                </option>
              {% endfor %}
            </select>
          </form>
        </div>
      </div>
    </div>
  </div>
  <div class="row gy-4">
    <div class="col-md-6">
      <div class="card h-100">
        <div class="card-header bg-warning text-white">Incomplete Planning Tasks</div>
        <ul class="list-group list-group-flush">
          {% for sess in incomplete_sessions %}
            <li class="list-group-item">
              <a href="{% url 'bps:session_detail' sess.pk %}">
                {{ sess.org_unit.name }} &dash; {{ sess.layout_year.layout.name }}
              </a>
            </li>
          {% empty %}
            <li class="list-group-item">None—everything is up to date!</li>
          {% endfor %}
        </ul>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card h-100">
        <div class="card-header bg-info text-white">Available Layouts</div>
        <div class="card-body">
          <div class="row row-cols-1 row-cols-md-2 g-3">
            {% for ly in layouts %}
              <div class="col">
                <div class="card h-100">
                  <div class="card-body p-2">
                    <h5 class="card-title mb-1">{{ ly.layout.name }}</h5>
                    <p class="card-text small mb-0">Version: {{ ly.version.code }}</p>
                  </div>
                  <div class="card-footer text-end">
                    <a href="{% url 'bps:session_list' %}?layout_year={{ ly.pk }}"
                       class="btn btn-sm btn-outline-primary">
                       Open
                    </a>
                  </div>
                </div>
              </div>
            {% empty %}
              <p class="text-muted">No layouts defined for {{ selected_year }}.</p>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card">
        <div class="card-header bg-success text-white">Planning Functions</div>
        <div class="card-body">
          <div class="list-group">
            <a href="{% url 'bps:manual_planning_select' %}" class="list-group-item list-group-item-action">
              🧮 Manual Planning Grid
            </a>
            {% for fn in planning_funcs %}
              <a href="{{ fn.url }}" class="list-group-item list-group-item-action">
                {{ fn.name }}
              </a>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card">
        <div class="card-header bg-secondary text-white">Admin</div>
        <div class="card-body">
          <div class="list-group">
            {% for link in admin_links %}
              <a href="{{ link.url }}" class="list-group-item list-group-item-action">
                {{ link.name }}
              </a>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

### `templates/bps/data_request_detail.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <h1>Data Request {{ dr.id }}</h1>
  <form method="post" class="mb-4">{% csrf_token %}
    {{ form|crispy }}
    <button type="submit" class="btn btn-primary">Update</button>
    <a href="{% url 'bps:data_request_list' %}" class="btn btn-link">Back to list</a>
  </form>
  <h2>Facts</h2>
  <table class="table table-striped">
    <thead>
      <tr><th>Period</th><th>Key Figure</th><th>Value</th><th>UoM</th><th>Ref Value</th><th>Ref UoM</th></tr>
    </thead>
    <tbody>
      {% for f in facts %}
        <tr>
          <td>{{ f.period.code }}</td>
          <td>{{ f.key_figure.code }}</td>
          <td>{{ f.value }}</td>
          <td>{{ f.uom.code|default:"–" }}</td>
          <td>{{ f.ref_value }}</td>
          <td>{{ f.ref_uom.code|default:"–" }}</td>
        </tr>
      {% empty %}
        <tr><td colspan="6">No facts recorded yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
  <a href="{% url 'bps:fact_list' dr.pk %}" class="btn btn-success">Add/Edit Facts</a>
</div>
{% endblock %}
```

### `templates/bps/data_request_list.html`
```html
{% extends "bps/base.html" %}
{% block content %}
<div class="container my-4">
  <h1>Data Requests</h1>
  <ul class="list-group mt-3">
    {% for dr in data_requests %}
      <li class="list-group-item d-flex justify-content-between align-items-center">
        <a href="{% url 'bps:data_request_detail' dr.pk %}">
          {{ dr.id }} – {{ dr.description|default:"(no description)" }}
        </a>
        <span class="badge bg-secondary">
          {{ dr.created_at|date:"Y-m-d H:i" }}
        </span>
      </li>
    {% empty %}
      <li class="list-group-item">No data requests found.</li>
    {% endfor %}
  </ul>
</div>
{% endblock %}
```

### `templates/bps/fact_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <h1>Facts for Request {{ dr.id }}</h1>
  <form method="post" class="row g-3 align-items-end mb-4">{% csrf_token %}
    <div class="col-md-2">
      {{ form.session|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.period|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.quantity|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.quantity_uom|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.amount|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.amount_uom|as_crispy_field }}
    </div>
    <div class="col-md-3">
      {{ form.other_key_figure|as_crispy_field }}
    </div>
    <div class="col-md-3">
      {{ form.other_value|as_crispy_field }}
    </div>
    <div class="col-md-2">
      <button type="submit" class="btn btn-primary">Save Fact</button>
      <a href="{% url 'bps:data_request_detail' dr.pk %}" class="btn btn-link">Done</a>
    </div>
  </form>
  <table class="table table-bordered">
    <thead>
      <tr>
        <th>Period</th><th>Qty</th><th>UoM</th>
        <th>Amount</th><th>UoM</th><th>Other</th><th>Value</th>
      </tr>
    </thead>
    <tbody>
      {% for f in facts %}
      <tr>
        <td>{{ f.period }}</td>
        <td>{{ f.quantity }}</td>
        <td>{{ f.quantity_uom }}</td>
        <td>{{ f.amount }}</td>
        <td>{{ f.amount_uom }}</td>
        <td>{{ f.other_key_figure }}</td>
        <td>{{ f.other_value }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="7">No facts yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

### `templates/bps/formula_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<h1>Formulas</h1>
<form method="post" class="mb-4">{% csrf_token %}
  {{ form|crispy }}
</form>
<table class="table">
  <thead><tr><th>Name</th><th>Loop Dim</th><th>Expression</th><th>Actions</th></tr></thead>
  <tbody>
    {% for f in formulas %}
      <tr>
        <td>{{ f.name }}</td>
        <td>{{ f.loop_dimension.model }}</td>
        <td><code>{{ f.expression }}</code></td>
        <td>
          <a href="{% url 'formula_run' f.pk %}?period=01" class="btn btn-sm btn-primary">
            Run
          </a>
        </td>
      </tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

### `templates/bps/inbox.html`
```html
{% extends "bps/base.html" %}
{% block content %}
<div class="container my-4">
  <h1>Inbox</h1>
  <p class="text-muted">(Nothing to show yet.)</p>
  {# Replace with a list of actionable items when you wire it up #}
</div>
{% endblock %}
```

### `templates/bps/manual_planning.html`
```html
{# bps/manual_planning.html #}
{% extends "bps/base.html" %}
{% load static %}
{% block title %}
Manual Planning – {{ layout_year.layout.name }} ({{ layout_year.year.code }}/{{ layout_year.version.code }})
{% endblock %}
{% block content %}
<div class="container-fluid mt-3">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2>
      Manual Planning – {{ layout_year.layout.name }}
      <small class="text-muted">({{ layout_year.year.code }}/{{ layout_year.version.code }})</small>
    </h2>
    <div>
      <button class="btn btn-primary me-2" id="btn-save">Save Changes</button>
      <a class="btn btn-outline-secondary" href="{% url 'admin:bps_planninglayout_change' layout_year.layout.pk %}">Edit Layout</a>
      <button id="btn-xlsx">Export Excel</button>
    </div>
  </div>
  {% if header_drivers %}
  <div class="card mb-3">
    <div class="card-header">Header Selection</div>
    <div class="card-body">
      <div class="row g-3 align-items-end">
        {% for hdr in header_drivers %}
        <div class="col-auto">
          <label class="form-label" for="hdr-{{ hdr.key }}">{{ hdr.label }}</label>
          <select id="hdr-{{ hdr.key }}" class="form-select header-select" data-key="{{ hdr.key }}">
            <option value="">(All)</option>
            {% for opt in hdr.choices %}
            <option value="{{ opt.id }}">{{ opt.name }}</option>
            {% endfor %}
          </select>
        </div>
        {% endfor %}
        <div class="col-auto">
          <button id="btn-apply-headers" class="btn btn-outline-primary">Apply</button>
        </div>
      </div>
    </div>
  </div>
  {% endif %}
  <div class="row mb-2">
    <div id="manual-planning-toolbar" class="col-auto align-self-end mb-2">
      <button id="add-row-btn" class="btn btn-sm btn-outline-primary">Add Row</button>
    </div>
  </div>
  <div id="planning-grid"></div>
</div>
{% endblock %}
{% block extra_js %}
<link href="https://cdn.jsdelivr.net/npm/tabulator-tables@6.3.1/dist/css/tabulator.min.css" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/tabulator-tables@6.3.1/dist/js/tabulator.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xlsx/dist/xlsx.full.min.js"></script>
<script>
(function(){
  // ---- Context from server ----
  const apiURL         = "{{ api_url }}";          // /api/bps/grid/
  const updateURL      = "{{ update_url }}";       // /api/bps/grid-update/
  const layoutId       = {{ layout_year.pk }};
  const buckets        = {{ buckets_js|safe }};
  const kfCodes        = {{ kf_codes|safe }};
  const kfMeta         = {{ kf_meta_js|safe }};
  const headerDrivers  = {{ header_drivers_js|safe }};
  const rowDrivers     = {{ row_drivers_js|safe }};
  const headerDefaults = {{ header_defaults_js|safe }};
  const services       = {{ services_js|safe }};
  const orgUnits       = {{ org_units_js|safe }};
  // Grouping config provided by server (may be [])
  const rowGroupFields = {{ row_group_fields_js|safe }} || [];
  const rowGroupStartOpen = {{ row_group_start_open_js|safe }};
  // ---- Helpers ----
  const toMap = (rows, vKey, lKey) =>
    rows.reduce((acc, r) => (acc[String(r[vKey])] = String(r[lKey]), acc), {});
  const orgUnitMap = toMap(orgUnits, "code", "name");
  const serviceMap = toMap(services, "code", "name");
  const driverMaps = {};
  rowDrivers.forEach(d => { driverMaps[d.key] = toMap(d.choices, "id", "name"); });
  const headerMaps = {};
  headerDrivers.forEach(d => { headerMaps[d.key] = toMap(d.choices, "id", "name"); });
  const bucketFirstPeriodMap = Object.fromEntries(
    buckets.map(b => [b.code, (b.periods && b.periods[0]) || b.code])
  );
  const rowKeys = rowDrivers.map(d => d.key);
  const hasOrgUnitCol = rowKeys.includes("orgunit");
  const hasServiceCol = rowKeys.includes("service");
  function safeLookup(map) {
    return function(cell) {
      const v = cell.getValue();
      if (v == null || v === "") return "";
      const k = String(v);
      return Object.prototype.hasOwnProperty.call(map, k) ? map[k] : "";
    };
  }
  function listEditorParams(valuesMap) {
    return {
      values: valuesMap,
      autocomplete: true,
      listOnEmpty: true,
      allowEmpty: true,
      clearable: true,
      sortValuesList: "asc",
      verticalNavigation: "table",
    };
  }
  function readHeaderSelections() {
    const selected = {};
    document.querySelectorAll(".header-select").forEach(sel => {
      const key = sel.dataset.key;
      const val = sel.value || "";
      selected[key] = val || null;
    });
    return selected;
  }
  function setHeaderDefaults() {
    Object.entries(headerDefaults || {}).forEach(([key, val]) => {
      const el = document.getElementById(`hdr-${key}`);
      if (el && val != null) el.value = String(val);
    });
  }
  // ---- Columns (dimensions) ----
  const dimCols = [];
  if (hasOrgUnitCol) {
    dimCols.push({
      title: "Org Unit",
      field: "org_unit_code",
      width: 220,
      frozen: true,
      editor: "list",
      editorParams: listEditorParams(orgUnitMap),
      formatter: safeLookup(orgUnitMap),
      headerFilter: "list",
      headerFilterParams: { values: orgUnitMap, autocomplete: true, clearable: true },
      headerTooltip: "Search Org Units",
    });
  }
  if (hasServiceCol) {
    dimCols.push({
      title: "Service",
      field: "service_code",
      width: 220,
      editor: "list",
      editorParams: listEditorParams(serviceMap),
      formatter: safeLookup(serviceMap),
      headerFilter: "list",
      headerFilterParams: { values: serviceMap, autocomplete: true, clearable: true },
      headerTooltip: "Search Services",
    });
  }
  dimCols.push(
    ...rowDrivers
      .filter(d => d.key !== "orgunit" && d.key !== "service")
      .map(d => ({
        title: d.label,
        field: `${d.key}_code`,
        width: 180,
        editor: "list",
        editorParams: listEditorParams(driverMaps[d.key] || {}),
        formatter: safeLookup(driverMaps[d.key] || {}),
        headerFilter: "list",
        headerFilterParams: { values: driverMaps[d.key] || {}, autocomplete: true, clearable: true },
        headerTooltip: `Search ${d.label}`,
      }))
  );
  // ---- Columns (values) — KEY FIGURE column groups ----
  const valueColsGrouped = kfCodes.map(kf => ({
    title: kf,
    columns: buckets.map(b => ({
      title: b.name,
      field: `${b.code}_${kf}`,
      editor: overwriteNumberEditor,
      hozAlign: "right",
      bottomCalc: "sum",
      formatter: "money",
      formatterParams: { symbol: "", precision: (kfMeta?.[kf]?.decimals ?? 2) },
    })),
  }));
  // Simple overwrite-on-first-key editor
  function overwriteNumberEditor(cell, onRendered, success, cancel) {
    const input = document.createElement("input");
    input.type = "text";
    input.inputMode = "decimal";
    const curr = cell.getValue();
    input.value = (curr == null ? "" : curr);
    let firstKeyReplacePending = true;
    function isPrintable(e){ return e.key && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey; }
    onRendered(() => { input.focus({preventScroll:true}); input.select(); setTimeout(()=>{try{input.select()}catch(_){}}) });
    input.addEventListener("keydown",(e)=>{
      if (e.key === "Enter"){ success(input.value); return; }
      if (e.key === "Escape"){ cancel(); return; }
      if (firstKeyReplacePending && isPrintable(e)){
        input.value = e.key;
        try{ input.setSelectionRange(input.value.length, input.value.length);}catch(_){}
        firstKeyReplacePending = false;
        e.preventDefault();
        return;
      }
    });
    input.addEventListener("blur", () => success(input.value));
    return input;
  }
  // Build query params for server request
  function buildAjaxParams() {
    const params = { layout: layoutId };
    const hdr = readHeaderSelections();
    Object.entries(hdr).forEach(([k,v]) => { if (v != null && v !== "") params[`header_${k}`] = v; });
    return params;
  }
  // Helpful group header label: translate codes to display text
  function labelForGroup(field, raw) {
    if (raw == null || raw === "") return "(blank)";
    const key = String(raw);
    if (field === "org_unit_code") return orgUnitMap[key] || key;
    if (field === "service_code")  return serviceMap[key]  || key;
    const dimKey = field.endsWith("_code") ? field.slice(0, -5) : field; // remove _code
    const map = driverMaps[dimKey] || {};
    return map[key] || key;
  }
  // ---- Tabulator init ----
  const tableOptions = {
    layout: "fitColumns",
    ajaxURL: apiURL,
    ajaxConfig: { credentials: "include" },
    ajaxParams: buildAjaxParams(),
    ajaxResponse: (_url, _params, res) => res,  // API returns array of rows
    columns: [
      {
        title: "",
        field: "_actions",
        width: 48,
        headerSort: false,
        hozAlign: "center",
        frozen: true,
        formatter: () => "🗑️",
        cellClick: (_e, cell) => deleteRow(cell.getRow()),
        tooltip: "Delete row (blank all values in this slice)",
      },
      ...dimCols,
      ...valueColsGrouped,  // grouped value columns by Key Figure
    ],
    pagination: "local",
    paginationSize: 50,
    history: true,
    validationMode: "highlight",
  };
  // Enable grouping only if configured
  const rowGroupingOn = Array.isArray(rowGroupFields) && rowGroupFields.length > 0;
  if (rowGroupingOn) {
    tableOptions.groupBy = rowGroupFields.length === 1 ? rowGroupFields[0] : rowGroupFields;
    tableOptions.groupStartOpen = !!rowGroupStartOpen;
    tableOptions.groupToggleElement = "header";
    tableOptions.groupClosedShowCalcs = true;
    tableOptions.groupHeader = function(value, count, _data, group) {
      const field = typeof group.getField === "function" ? group.getField() : "";
      const label = labelForGroup(field, value);
      return `${label} <span class="text-muted">(${count})</span>`;
    };
  }
  const table = new Tabulator("#planning-grid", tableOptions);
  // Header defaults + Apply
  setHeaderDefaults();
  const btnApply = document.getElementById("btn-apply-headers");
  if (btnApply) {
    btnApply.addEventListener("click", (e) => {
      e.preventDefault();
      table.setData(apiURL, buildAjaxParams());
    });
  }
  // ---- Export / Add Row ----
  document.getElementById("btn-xlsx").addEventListener("click", () => {
    table.download("xlsx", `${window.ply_code || "planning"}.xlsx`, {sheetName: "Plan"});
  });
  const blankRow = (() => {
    const base = {};
    if (hasOrgUnitCol) base["org_unit_code"] = null;
    if (hasServiceCol) base["service_code"] = null;
    rowDrivers
      .filter(d => d.key !== "orgunit" && d.key !== "service")
      .forEach(d => { base[`${d.key}_code`] = null; });
    buckets.forEach(b => { kfCodes.forEach(kf => { base[`${b.code}_${kf}`] = null; }); });
    return base;
  })();
  document.getElementById("add-row-btn").addEventListener("click", async () => {
    try {
      const row = await table.addRow({ ...blankRow }, true);
      const firstDim = dimCols[0];
      if (firstDim) row.getCell(firstDim.field).edit();
    } catch (e) { console.error(e); }
  });
  // ---- Save edited numeric cells ----
  const VALUE_FIELDS = buckets.flatMap(b => kfCodes.map(kf => `${b.code}_${kf}`));
  document.getElementById("btn-save").addEventListener("click", () => {
    const editedCells = table.getEditedCells();
    const valueCells = editedCells.filter(c => VALUE_FIELDS.includes(c.getField()));
    if (!valueCells.length) { alert("No numeric changes to save."); return; }
    const headerSelected = readHeaderSelections();
    const updates = [];
    const missingOrgRows = new Set();
    for (const cell of valueCells) {
      const row = cell.getRow();
      const d = row.getData();
      const field = cell.getField();
      const sep = field.indexOf("_");
      const bucketCode = field.slice(0, sep);
      const kf = field.slice(sep + 1);
      const period = bucketFirstPeriodMap[bucketCode] || bucketCode;
      const base = { layout: layoutId };
      const orgFromRow = hasOrgUnitCol ? d.org_unit_code : null;
      const orgFromHdr = headerSelected.orgunit || null;
      base.org_unit = orgFromRow || orgFromHdr || null;
      if (!base.org_unit) {
        missingOrgRows.add(row.getPosition(true));
        continue;
      }
      const svcFromRow = hasServiceCol ? d.service_code : null;
      const svcFromHdr = headerSelected.service || null;
      base.service = svcFromRow || svcFromHdr || null;
      rowDrivers
        .filter(dr => dr.key !== "orgunit" && dr.key !== "service")
        .forEach(dr => { base[dr.key] = d[`${dr.key}_code`] ?? null; });
      headerDrivers
        .filter(hd => hd.key !== "orgunit" && hd.key !== "service")
        .forEach(hd => { base[hd.key] = headerSelected[hd.key] ?? null; });
      updates.push({ ...base, period, key_figure: kf, value: cell.getValue() });
    }
    if (!updates.length) {
      if (missingOrgRows.size) {
        alert("Org Unit is required (from header or row) before saving.\nRows: " + [...missingOrgRows].join(", "));
      } else {
        alert("No valid changes to save.");
      }
      return;
    }
    fetch(updateURL, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
      body: JSON.stringify({
        layout: layoutId,
        headers: headerSelected,
        delete_zeros: true,
        delete_blanks: true,
        updates,
      }),
    })
    .then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (res.status === 207 || (Array.isArray(data.errors) && data.errors.length)) {
        const msg = [
          "Some updates failed:",
          ...(data.errors || []).slice(0, 10).map(e => `• ${e.error}`),
          (data.errors || []).length > 10 ? `…and ${data.errors.length - 10} more` : ""
        ].join("\n");
        alert(msg);
        table.replaceData();  // reload
        return;
      }
      if (!res.ok) throw new Error(data.detail || "Save failed");
      alert(`All changes saved. Updated ${data.updated ?? "some"} cells.`);
      table.setData(apiURL, buildAjaxParams());
    })
    .catch((err) => { console.error(err); alert("Save failed."); });
  });
  // ---- Delete entire row slice (all months/KFs) ----
  function deleteRow(row) {
    const d = row.getData();
    const headerSelected = readHeaderSelections();
    const orgUnit = (hasOrgUnitCol ? d.org_unit_code : null) || headerSelected.orgunit || null;
    if (!orgUnit) { alert("Org Unit is required (from header or row) to delete this slice."); return; }
    const service = (hasServiceCol ? d.service_code : null) || headerSelected.service || null;
    const base = { layout: layoutId, org_unit: orgUnit, service };
    rowDrivers
      .filter(dr => dr.key !== "orgunit" && dr.key !== "service")
      .forEach(dr => { base[dr.key] = d[`${dr.key}_code`] ?? null; });
    headerDrivers
      .filter(hd => hd.key !== "orgunit" && hd.key !== "service")
      .forEach(hd => { base[hd.key] = headerSelected[hd.key] ?? null; });
    const updates = [];
    for (const field of VALUE_FIELDS) {
      const sep = field.indexOf("_");
      const bucketCode = field.slice(0, sep);
      const kf = field.slice(sep + 1);
      const period = bucketFirstPeriodMap[bucketCode] || bucketCode;
      updates.push({ ...base, period, key_figure: kf, value: "" });
    }
    if (!updates.length) return;
    if (!confirm("Delete this entire row (all months/key figures) from this header slice?")) return;
    fetch(updateURL, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
      body: JSON.stringify({
        layout: layoutId,
        headers: headerSelected,
        delete_zeros: true,
        delete_blanks: true,
        updates,
      }),
    })
    .then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg = (data && (data.detail || (data.errors && JSON.stringify(data.errors)))) || res.statusText;
        throw new Error(msg);
      }
      try { table.deleteRow(row); } catch (_) { table.replaceData(); }
    })
    .catch(err => { console.error(err); alert("Failed to delete row."); });
  }
  function getCookie(name) {
    let v = null;
    document.cookie.split(';').forEach(c => {
      c = c.trim();
      if (c.startsWith(name + '=')) v = decodeURIComponent(c.slice(name.length + 1));
    });
    return v;
  }
})();
</script>
{% endblock %}
```

### `templates/bps/manual_planning_select.html`
```html
{# manual_planning_select.html #}
{% extends "bps/base.html" %}
{% block content %}
<h2>Select Manual Planning</h2>
<form id="select-form">
  <div class="mb-3">
    <label for="layout" class="form-label">Layout/Year/Version</label>
    <select id="layout" class="form-select">
      {% for ly in layouts %}
      <option value="{{ ly.layout.id }}|{{ ly.year.id }}|{{ ly.version.id }}">
        {{ ly.layout.name }} - {{ ly.year.code }}/{{ ly.version.code }}
      </option>
      {% endfor %}
    </select>
  </div>
  <button class="btn btn-primary">Launch</button>
</form>
<script>
  document.getElementById('select-form').addEventListener('submit', e=>{
    e.preventDefault();
    let [l,y,v] = document.getElementById('layout').value.split('|');
    window.location.href = `{% url 'bps:manual_planning' 0 0 0 %}`
      .replace('/0/0/0/', `/${l}/${y}/${v}/`);
  });
</script>
{% endblock %}
```

### `templates/bps/notifications.html`
```html
{% extends "bps/base.html" %}
{% block content %}
<div class="container my-4">
  <h1>Notifications</h1>
  <p class="text-muted">You have no new notifications.</p>
  {# Replace with real notification stream when ready #}
</div>
{% endblock %}
```

### `templates/bps/planner/dashboard.html`
```html
{% extends "admin/base_site.html" %}
{% block content %}
<h1>Planner Dashboard</h1>
{% if effective_delegator %}
  <div class="alert">Acting as <b>{{ effective_delegator.get_username }}</b>.
    <a href="{% url 'planner-act-as-stop' %}">Stop</a>
  </div>
{% endif %}
{% if is_enterprise %}
  <p><b>Enterprise Planner</b>: you can access <i>all</i> Org Units and make changes.</p>
{% else %}
  <h3>Delegations</h3>
  {% if delegations %}
    <ul>
      {% for d in delegations %}
        <li>From <b>{{ d.delegator.get_username }}</b>
          <a href="{% url 'planner-act-as' d.delegator.id %}">Act as</a>
        </li>
      {% endfor %}
    </ul>
  {% else %}
    <p>No active delegations.</p>
  {% endif %}
{% endif %}
<h3>Allowed Org Units</h3>
<div id="ou-list"></div>
<script>
fetch("{% url 'api-allowed-ous' %}")
  .then(r => r.json())
  .then(({results}) => {
    const el = document.getElementById("ou-list");
    if (!results.length){ el.innerHTML = "<i>None</i>"; return; }
    const ul = document.createElement("ul");
    results.forEach(r => {
      const li = document.createElement("li");
      li.textContent = `${r.code || ''} ${r.name}`;
      ul.appendChild(li);
    });
    el.appendChild(ul);
  });
</script>
{% endblock %}
```

### `templates/bps/planning_function_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h1 class="mb-0">Planning Functions</h1>
    <a href="{% url 'bps:dashboard' %}" class="btn btn-outline-secondary">← Back to Dashboard</a>
  </div>
  <div class="card mb-4">
    <div class="card-header">Add / Edit Function</div>
    <div class="card-body">
      <form method="post" class="mb-0">{% csrf_token %}
        {{ form|crispy }}
      </form>
    </div>
  </div>
  <div class="card">
    <div class="card-header">Defined Functions</div>
    <div class="card-body p-0">
      <div class="table-responsive">
        <table class="table table-striped table-hover mb-0 align-middle">
          <thead class="table-light">
            <tr>
              <th>Name</th>
              <th>Layout</th>
              <th>Type</th>
              <th>Parameters (JSON)</th>
              <th class="text-end">Actions</th>
            </tr>
          </thead>
          <tbody>
            {% for fn in functions %}
              <tr>
                <td class="fw-semibold">{{ fn.name }}</td>
                <td><code>{{ fn.layout.code }}</code></td>
                <td>{{ fn.get_function_type_display }}</td>
                <td><code class="small">{{ fn.parameters|default:"{}" }}</code></td>
                <td class="text-end">
                  <button
                    type="button"
                    class="btn btn-sm btn-primary"
                    data-bs-toggle="modal"
                    data-bs-target="#runModal"
                    data-fn-id="{{ fn.id }}"
                    data-fn-name="{{ fn.name }}"
                  >
                    Run…
                  </button>
                </td>
              </tr>
            {% empty %}
              <tr><td colspan="5" class="text-muted text-center py-4">No planning functions defined.</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
<div class="modal fade" id="runModal" tabindex="-1" aria-labelledby="runModalLabel" aria-hidden="true">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="runModalLabel">Run Function</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <div class="mb-2">
          <div class="form-text">Function</div>
          <div id="run-fn-name" class="fw-semibold"></div>
        </div>
        <label for="run-session-id" class="form-label">Session ID</label>
        <input type="number" min="1" class="form-control" id="run-session-id" placeholder="Enter PlanningSession ID">
        <div class="form-text">
          Tip: open <a href="{% url 'bps:session_list' %}" target="_blank">Sessions</a> in a new tab to copy the ID.
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
        <button type="button" class="btn btn-primary" id="run-confirm-btn">Run</button>
      </div>
    </div>
  </div>
</div>
{% endblock %}
{% block extra_js %}
<script>
(function(){
  // URL template like /functions/run/0/0/, replace with real ids at runtime
  const RUN_URL_TEMPLATE = "{% url 'bps:run_function' 0 0 %}";
  const runModalEl = document.getElementById('runModal');
  const fnNameEl   = document.getElementById('run-fn-name');
  const sessInput  = document.getElementById('run-session-id');
  const confirmBtn = document.getElementById('run-confirm-btn');
  let currentFnId = null;
  runModalEl.addEventListener('show.bs.modal', event => {
    const btn = event.relatedTarget;
    currentFnId = btn.getAttribute('data-fn-id');
    const fnName = btn.getAttribute('data-fn-name') || '';
    fnNameEl.textContent = fnName;
    sessInput.value = '';
    setTimeout(()=>sessInput.focus(), 200);
  });
  confirmBtn.addEventListener('click', () => {
    const sessId = (sessInput.value || '').trim();
    if (!sessId) { sessInput.focus(); return; }
    // Build /functions/run/<fn>/<session>/
    const url = RUN_URL_TEMPLATE.replace('/0/0/', `/${currentFnId}/${sessId}/`);
    window.location.href = url;
  });
})();
</script>
{% endblock %}
```

### `templates/bps/reference_data_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <h1>Reference Data</h1>
  <form method="post" class="mb-4">{% csrf_token %}
    {{ form|crispy }}
  </form>
  <table class="table table-hover">
    <thead>
      <tr>
        <th>Name</th>
        <th>Version</th>
        <th>Year</th>
        <th>Description</th>
      </tr>
    </thead>
    <tbody>
      {% for ref in references %}
      <tr>
        <td>{{ ref.name }}</td>
        <td>{{ ref.source_version.code }}</td>
        <td>{{ ref.source_year.code }}</td>
        <td>{{ ref.description|default:"–" }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="4">No reference data found.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

### `templates/bps/session_detail.html`
```html
{# templates/bps/session_detail.html #}
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
  {# -- Breadcrumbs -- #}
  {% if breadcrumbs %}
    <nav aria-label="breadcrumb">
      <ol class="breadcrumb">
        {% for crumb in breadcrumbs %}
          <li class="breadcrumb-item {% if forloop.last %}active{% endif %}"
              {% if forloop.last %}aria-current="page"{% endif %}>
            {% if not forloop.last %}
              <a href="{{ crumb.url }}">{{ crumb.title }}</a>
            {% else %}
              {{ crumb.title }}
            {% endif %}
          </li>
        {% endfor %}
      </ol>
    </nav>
  {% endif %}
  <div class="d-flex justify-content-between align-items-center mb-4">
    <h1>{{ sess.org_unit.name }} — {{ sess.scenario.name }}</h1>
    <a
      href="{% url 'bps:manual_planning' sess.layout_year.layout.id sess.layout_year.year.id sess.layout_year.version.id %}"
      class="btn btn-outline-primary"
    >
      📝 Open Manual Planning Grid
    </a>
  </div>
  {# -- Only show “Start Session” if it hasn’t been started yet -- #}
  {% if can_edit %}
    <form method="post" class="mb-4">
      {% csrf_token %}
      {{ form|crispy }}
      <button name="start" class="btn btn-success">Start Session</button>
    </form>
  {% endif %}
  {# -- Raw Facts (paginated) -- #}
  <h2 class="mt-4">Raw Facts</h2>
  <div class="table-responsive">
    <table class="table table-striped">
      <thead>
        <tr>
          <th>Period</th>
          <th>Key Figure</th>
          <th>Value</th>
          <th>UoM</th>
          <th>Service</th>
        </tr>
      </thead>
      <tbody>
        {% if facts %}
          {% for f in facts %}
            <tr>
              <td>{{ f.period.code }}</td>
              <td>{{ f.key_figure.code }}</td>
              <td>{{ f.value }}</td>
              <td>{{ f.uom.code|default:"–" }}</td>
              <td>{{ f.service.name|default:"–" }}</td>
            </tr>
          {% endfor %}
        {% else %}
          <tr>
            <td colspan="5" class="text-center text-muted">No facts recorded yet.</td>
          </tr>
        {% endif %}
      </tbody>
    </table>
  </div>
  {% if is_paginated %}
    {% include "bps/_paginator.html" with page_obj=facts_page paginator=paginator page_size=page_size page_sizes=page_sizes %}
  {% endif %}
  {# -- Advance to Next Step (staff only) -- #}
  <form method="post" action="{% url 'bps:advance_step' sess.pk %}">
    {% csrf_token %}
    <button class="btn btn-primary"
            {% if not can_advance %}disabled{% endif %}>
      Next Step →
    </button>
  </form>
{% endblock %}
```

### `templates/bps/session_list.html`
```html
{% extends "bps/base.html" %}
{% load static %}
{% block content %}
<div class="container my-4">
  <h1>All Planning Sessions</h1>
  <table class="table table-hover">
    <thead>
      <tr>
        <th>Org Unit</th>
        <th>Layout / Year • Version</th>
        <th>Status</th>
        <th>Created At</th>
      </tr>
    </thead>
    <tbody>
      {% for sess in sessions %}
      <tr>
        <td>
          <a href="{% url 'bps:session_detail' sess.pk %}">
            {{ sess.org_unit.name }}
          </a>
        </td>
        <td>{{ sess.layout_year.layout.name }} / {{ sess.layout_year.year.code }} • {{ sess.layout_year.version.code }}</td>
        <td>{{ sess.get_status_display }}</td>
        <td>{{ sess.created_at|date:"Y-m-d H:i" }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="4">No sessions found.</td></tr>
      {% endfor %}
    </tbody>
  </table>
{% endblock %}
```

### `templates/bps/subformula_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<h1>Sub-Formulas</h1>
<form method="post" class="mb-4">{% csrf_token %}
  {{ form|crispy }}
</form>
<table class="table">
  <thead><tr><th>Name</th><th>Expression</th></tr></thead>
  <tbody>
    {% for s in subs %}
      <tr><td>{{ s.name }}</td><td><code>{{ s.expression }}</code></td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

### `templates/bps/variable_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <h1>Global Variables</h1>
  <form method="post" class="row g-3 align-items-end mb-4">{% csrf_token %}
    <div class="col-md-4">
      {{ form.name|as_crispy_field }}
    </div>
    <div class="col-md-4">
      {{ form.value|as_crispy_field }}
    </div>
    <div class="col-md-8">
      {{ form.description|as_crispy_field }}
    </div>
    <div class="col-md-2">
      <button type="submit" class="btn btn-primary">Add Variable</button>
    </div>
  </form>
  <table class="table table-hover">
    <thead>
      <tr><th>Name</th><th>Value</th><th>Description</th></tr>
    </thead>
    <tbody>
      {% for v in consts %}
      <tr>
        <td>{{ v.name }}</td>
        <td>{{ v.value }}</td>
        <td>{{ v.description }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="3">No variables defined.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

### `urls.py`
```python
from django.urls import path, include
from .views.views import (
    ScenarioDashboardView, PlanningSessionListView, PlanningSessionDetailView, AdvanceStepView,
    DashboardView, ProfileView, InboxView, NotificationsView,
    ManualPlanningSelectView,
    PlanningSessionListView, PlanningSessionDetailView, AdvanceStageView,
    ConstantListView, SubFormulaListView, FormulaListView, FormulaRunView,
    CopyActualView, DistributeKeyView,
    PlanningFunctionListView, RunPlanningFunctionView,
    ReferenceDataListView, DataRequestListView, DataRequestDetailView,
    FactListView, VariableListView,
)
from .views.manual_planning import ManualPlanningView
from .api.views_lookup import header_options
from .views.autocomplete import (
    LayoutAutocomplete, ContentTypeAutocomplete,
    YearAutocomplete, PeriodAutocomplete,
    OrgUnitAutocomplete, CBUAutocomplete,
    AccountAutocomplete, InternalOrderAutocomplete,
    UnitOfMeasureAutocomplete, LayoutYearAutocomplete,
    ServiceAutocomplete, KeyFigureAutocomplete, VersionAutocomplete,
)
from .views.views_planner import PlannerDashboard, act_as_start, act_as_stop, api_allowed_ous
app_name = "bps"
urlpatterns = [
    path("scenario/<slug:code>/", ScenarioDashboardView.as_view(), name="scenario_dashboard"),
    path("session/", PlanningSessionListView.as_view(), name="session_list"),
    path("session/<int:pk>/", PlanningSessionDetailView.as_view(), name="session_detail"),
    path("session/<int:pk>/advance/", AdvanceStepView.as_view(), name="advance_step"),
    path("",                 DashboardView.as_view(),    name="dashboard"),
    path("profile/",         ProfileView.as_view(),      name="profile"),
    path("inbox/",           InboxView.as_view(),        name="inbox"),
    path("notifications/",   NotificationsView.as_view(),name="notifications"),
    path(
        "planning/manual/select/",
        ManualPlanningSelectView.as_view(),
        name="manual_planning_select",
    ),
    path(
        "planning/manual/<int:layout_id>/<int:year_id>/<int:version_id>/",
        ManualPlanningView.as_view(),
        name="manual_planning",
    ),
    path("constants/",       ConstantListView.as_view(),       name="constant_list"),
    path("subformulas/",     SubFormulaListView.as_view(),     name="subformula_list"),
    path("formulas/",        FormulaListView.as_view(),        name="formula_list"),
    path("formulas/run/<int:pk>/", FormulaRunView.as_view(),     name="formula_run"),
    path("copy-actual/",     CopyActualView.as_view(),         name="copy_actual"),
    path("distribute-key/",  DistributeKeyView.as_view(),      name="distribute_key"),
    path("functions/",       PlanningFunctionListView.as_view(), name="planning_function_list"),
    path("functions/run/<int:pk>/<int:session_id>/",
         RunPlanningFunctionView.as_view(),                   name="run_function"),
    path("reference-data/",  ReferenceDataListView.as_view(),  name="reference_data_list"),
    path("data-requests/",               DataRequestListView.as_view(),       name="data_request_list"),
    path("data-requests/<uuid:pk>/",     DataRequestDetailView.as_view(),     name="data_request_detail"),
    path("requests/<uuid:request_id>/facts/", FactListView.as_view(),            name="fact_list"),
    path("variables/",      VariableListView.as_view(),      name="variable_list"),
    path("planner/", PlannerDashboard.as_view(), name="planner-dashboard"),
    path("planner/act-as/<int:user_id>/", act_as_start, name="planner-act-as"),
    path("planner/act-as/stop/", act_as_stop, name="planner-act-as-stop"),
    path("api/allowed-ous/", api_allowed_ous, name="api-allowed-ous"),
    path("autocomplete/layout/",      LayoutAutocomplete.as_view(),      name="layout-autocomplete"),
    path("autocomplete/contenttype/", ContentTypeAutocomplete.as_view(), name="contenttype-autocomplete"),
    path("autocomplete/year/",        YearAutocomplete.as_view(),        name="year-autocomplete"),
    path("autocomplete/period/",      PeriodAutocomplete.as_view(),      name="period-autocomplete"),
    path("autocomplete/orgunit/",     OrgUnitAutocomplete.as_view(),     name="orgunit-autocomplete"),
    path("autocomplete/cbu/",         CBUAutocomplete.as_view(),         name="cbu-autocomplete"),
    path("autocomplete/account/",     AccountAutocomplete.as_view(),     name="account-autocomplete"),
    path("autocomplete/internalorder/", InternalOrderAutocomplete.as_view(), name="internalorder-autocomplete"),
    path("autocomplete/uom/",         UnitOfMeasureAutocomplete.as_view(), name="uom-autocomplete"),
    path("autocomplete/layoutyear/",  LayoutYearAutocomplete.as_view(),   name="layoutyear-autocomplete"),
    path("autocomplete/service/",      ServiceAutocomplete.as_view(),    name="service-autocomplete"),
    path("autocomplete/keyfigure/",    KeyFigureAutocomplete.as_view(),  name="keyfigure-autocomplete"),
    path("autocomplete/version/",      VersionAutocomplete.as_view(),    name="version-autocomplete"),
]
```

### `views/autocomplete.py`
```python
from dal_select2.views import Select2QuerySetView
from dal_select2.widgets import ModelSelect2, ModelSelect2Multiple
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from ..models.models import (
    PlanningLayout,
    Year,
    Period,
    OrgUnit,
    Account,
    InternalOrder,
    CBU,
    UnitOfMeasure,
    PriceType,
    PlanningLayoutYear,
    KeyFigure
)
from ..models.models_dimension import Service, Version
class ServiceAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = Service.objects.filter(is_active=True)
        if self.q: qs = qs.filter(Q(code__icontains=self.q)|Q(name__icontains=self.q))
        return qs
class KeyFigureAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = KeyFigure.objects.all()
        if self.q: qs = qs.filter(Q(code__icontains=self.q)|Q(name__icontains=self.q))
        return qs
class VersionAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = Version.objects.all()
        if self.q: qs = qs.filter(Q(code__icontains=self.q)|Q(name__icontains=self.q))
        return qs
class LayoutAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = PlanningLayout.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs
class ContentTypeAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = ContentType.objects.all()
        if self.q:
            qs = qs.filter(
                Q(model__icontains=self.q) |
                Q(app_label__icontains=self.q)
            )
        return qs
class YearAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = Year.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs
class PeriodAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = Period.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs
class OrgUnitAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = OrgUnit.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs
class AccountAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = Account.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs
class InternalOrderAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = InternalOrder.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs
class CBUAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = CBU.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs
class PriceTypeAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = PriceType.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs
class UnitOfMeasureAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = UnitOfMeasure.objects.all()
        if self.q:
            qs = qs.filter(
                Q(code__icontains=self.q) |
                Q(name__icontains=self.q)
            )
        return qs
class LayoutYearAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = PlanningLayoutYear.objects.select_related('layout', 'year', 'version')
        if self.q:
            qs = qs.filter(
                Q(layout__name__icontains=self.q) |
                Q(year__code__icontains=self.q) |
                Q(version__code__icontains=self.q)
            )
        return qs
```

### `views/forms.py`
```python
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
from dal_select2.widgets import ModelSelect2
from django.contrib.contenttypes.models import ContentType
from ..models.models import (
    Constant, SubFormula, Formula, PlanningFunction, ReferenceData,
    PlanningLayoutYear, PeriodGrouping, PlanningSession,
    DataRequest, PlanningFact, Year, Version, OrgUnit
)
class FactForm(forms.ModelForm):
    class Meta:
        model = PlanningFact
        fields = [
            'service', 'account', 'extra_dimensions_json',
            'key_figure', 'value', 'uom',
            'ref_value', 'ref_uom'
        ]
        widgets = {
            'service': ModelSelect2(url='bps:service-autocomplete'),
            'account': ModelSelect2(url='bps:account-autocomplete'),
            'key_figure': ModelSelect2(url='bps:keyfigure-autocomplete'),
            'uom': ModelSelect2(url='bps:uom-autocomplete'),
            'ref_uom': ModelSelect2(url='bps:uom-autocomplete'),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Row(
                Column('service',   css_class='col-md-4'),
                Column('account',   css_class='col-md-4'),
                Column('extra_dimensions_json', css_class='col-md-4'),
            ),
            Row(
                Column('key_figure', css_class='col-md-4'),
                Column('value',      css_class='col-md-4'),
                Column('uom',        css_class='col-md-4'),
            ),
            Row(
                Column('ref_value', css_class='col-md-4'),
                Column('ref_uom',   css_class='col-md-4'),
            ),
            Submit('save', 'Save Fact')
        )
class ConstantForm(forms.ModelForm):
    class Meta:
        model = Constant
        fields = ['name', 'value']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'name', 'value',
            Submit('save','Save Constant')
        )
class SubFormulaForm(forms.ModelForm):
    class Meta:
        model = SubFormula
        fields = ['layout', 'name', 'expression']
        widgets = {
            'layout': ModelSelect2(url='bps:layout-autocomplete'),
            'expression': forms.Textarea(attrs={'rows':3})
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Row(Column('layout', css_class='col-md-4'),
                Column('name', css_class='col-md-4')),
            'expression',
            Submit('save', 'Save Sub-Formula')
        )
class FormulaForm(forms.ModelForm):
    loop_dimension = forms.ModelChoiceField(
        queryset=ContentType.objects.all(),
        widget=ModelSelect2(url='bps:contenttype-autocomplete')
    )
    class Meta:
        model = Formula
        fields = ['layout', 'name', 'loop_dimension', 'expression']
        widgets = {
            'layout': ModelSelect2(url='bps:layout-autocomplete'),
            'expression': forms.Textarea(attrs={'rows':4}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Row(Column('layout', css_class='col-md-4'),
                Column('name', css_class='col-md-4')),
            'loop_dimension',
            'expression',
            Submit('save', 'Save Formula')
        )
class PlanningFunctionForm(forms.ModelForm):
    class Meta:
        model = PlanningFunction
        fields = ['layout', 'name', 'function_type', 'parameters']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Row(
                Column('layout', css_class='col-md-4'),
                Column('name', css_class='col-md-4'),
                Column('function_type', css_class='col-md-4'),
            ),
            'parameters',
            Submit('save','Save Function')
        )
class ReferenceDataForm(forms.ModelForm):
    class Meta:
        model = ReferenceData
        fields = ['name', 'source_version', 'source_year', 'description']
        widgets = {
            'source_version': ModelSelect2(url='bps:version-autocomplete'),
            'source_year'   : ModelSelect2(url='bps:year-autocomplete'),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-4'),
                Column('source_version', css_class='col-md-4'),
                Column('source_year', css_class='col-md-4'),
            ),
            'description',
            Submit('save','Save Reference')
        )
class PlanningSessionForm(forms.ModelForm):
    class Meta:
        model = PlanningSession
        fields = ['org_unit']
        widgets = {
           'org_unit'   : ModelSelect2(url='bps:orgunit-autocomplete'),
        }
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
          Row(
              Column('org_unit',    css_class='col-md-6')
        ),
          Submit('start','Start Planning')
        )
class PeriodSelector(forms.Form):
    grouping = forms.ModelChoiceField(
        queryset=PeriodGrouping.objects.none(),
        label="Period Grouping"
    )
    def __init__(self, *a, session:PlanningSession, **kw):
        super().__init__(*a,**kw)
        qs = session.layout_year.period_groupings.all()
        self.fields['grouping'].queryset = qs
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'grouping',
            Submit('apply','Apply')
        )
```

### `views/formula_executor.py`
```python
import re, ast, operator, itertools
from decimal import Decimal
from typing import Any, Dict, List
from django.apps import apps
from django.db.models import Sum, Avg, Min, Max, Q
from bps.models.models import (
    PlanningFact, Formula, Constant, SubFormula,
    FormulaRun, FormulaRunEntry, ReferenceData, Period
)
from bps.models.models import KeyFigure, DataRequest
_AGG_FUNCS = {
    'SUM': Sum,
    'AVG': Avg,
    'MIN': Min,
    'MAX': Max,
}
class FormulaExecutor:
    _re_refdata = re.compile(r"REF\('([^']+)'\s*,\s*([^\)]+)\)")
    _re_subf   = re.compile(r"\$(\w+)")
    _re_const  = re.compile(r"\b[A-Z_][A-Z0-9_]*\b")
    _re_ref    = re.compile(r"\[(.*?)\]\.\?\[(.*?)\]")
    def __init__(self, formula: Formula, session, period: str, preview: bool=False):
        self.formula = formula
        self.session = session
        self.period  = period
        self.preview = preview
        self.run     = None
        self.dim_cts = list(formula.dimensions.all())
    def execute(self):
        self.run = FormulaRun.objects.create(formula=self.formula,
                                             preview=self.preview)
        loops = []
        for ct in self.dim_cts:
            Model = ct.model_class()
            loops.append([(ct, obj) for obj in Model.objects.all()])
        for combo in itertools.product(*loops):
            dims_map = {ct.model: inst for ct,inst in combo}
            self._apply(dims_map)
        return self.run.entries.all()
    def _apply(self, dims_map: Dict[str,Any]):
        expr = self.formula.expression
        expr = self._expand_subformulas(expr)
        expr = self._replace_reference_data(expr, dims_map)
        expr = self._replace_constants(expr)
        expr = self._rewrite_conditionals(expr)
        tgt, src = map(str.strip, expr.split('=',1))
        key_fig, tgt_dims = self._parse_ref(tgt, dims_map)
        src_eval = self._replace_refs_with_values(src, dims_map)
        result   = self._safe_eval(src_eval, dims_map)
        rec = self._get_record(key_fig, tgt_dims, create=not self.preview)
        old = getattr(rec, key_fig, 0)
        if not self.preview:
            setattr(rec, key_fig, result)
            rec.save()
        FormulaRunEntry.objects.create(
            run=self.run, record=rec,
            key=key_fig, old_value=old, new_value=result
        )
    def _expand_subformulas(self, expr: str) -> str:
        def repl(m):
            sub = SubFormula.objects.get(name=m.group(1),
                                         layout=self.formula.layout)
            return f"({self._expand_subformulas(sub.expression)})"
        return self._re_subf.sub(repl, expr)
    def _replace_constants(self, expr: str) -> str:
        def repl(m):
            val = Constant.objects.get(name=m.group(0)).value
            return str(val)
        return self._re_const.sub(repl, expr)
    def _rewrite_conditionals(self, expr: str) -> str:
        expr = re.sub(r"\bIF\(", "__if__(", expr)
        def case_repl(m):
            body = m.group(1)
            return f"__case__([{body}])"
        expr = re.sub(r"\bCASE\s+(.*?)\s+END", case_repl, expr, flags=re.S)
        return expr
    def __if__(self, cond, tval, fval):
        return tval if cond else fval
    def __case__(self, arms: List[str]):
        for arm in arms:
            text = arm.strip()
            if text.upper().startswith("WHEN"):
                _, cond, _, val = re.split(r"\s+", text, maxsplit=3)
                if self._safe_eval(cond, {}):
                    return self._safe_eval(val, {})
            elif text.upper().startswith("ELSE"):
                return self._safe_eval(text.split(None,1)[1], {})
        return Decimal('0')
    def _parse_ref(self, token: str, dims_map: Dict[str,Any]):
        m = self._re_ref.match(token)
        dims, kf = m.groups()
        fldmap = {}
        for d in dims.split(','):
            name,val = d.split('=')
            name,val = name.strip(), val.strip()
            if val == '$LOOP':
                inst = dims_map[name]
            else:
                inst = apps.get_model('bps',name).objects.get(pk=int(val))
            fldmap[name.lower()] = inst
        return kf, fldmap
    def _replace_refs_with_values(self, expr: str, dims_map: Dict[str,Any]) -> str:
        def repl(m):
            dims, k = m.groups()
            fkwargs = {}
            for d in dims.split(','):
                n,v = d.split('=')
                n,v = n.strip(), v.strip()
                if v == '$LOOP':
                    inst = dims_map[n]
                else:
                    inst = apps.get_model('bps',n).objects.get(pk=int(v))
                fkwargs[n.lower()] = inst
            return f"__ref__('{k}',{fkwargs})"
        return self._re_ref.sub(repl, expr)
    def _safe_eval(self, expr: str, dims_map: Dict[str,Any]) -> Decimal:
        def shift_func(k, offset):
            return self._shift(k, offset, dims_map)
        def lookup_func(k, **overrides):
            return self._lookup(k, dims_map, overrides)
        ns = {
            '__if__': self.__if__,
            '__case__': self.__case__,
            '__ref__': lambda k, kwargs: self._aggregate_or_fetch(k, kwargs),
            'SHIFT': shift_func,
            'LOOKUP': lookup_func,
        }
        node = ast.parse(expr, mode='eval').body
        def _eval(n):
            if isinstance(n, ast.Call):
                func = _eval(n.func)
                args = [_eval(a) for a in n.args]
                kwargs = {kw.arg: _eval(kw.value) for kw in n.keywords}
                return func(*args, **kwargs)
            if isinstance(n, ast.BinOp):
                return {
                  ast.Add: operator.add,
                  ast.Sub: operator.sub,
                  ast.Mult: operator.mul,
                  ast.Div: operator.truediv,
                  ast.Pow: operator.pow,
                }[type(n.op)](_eval(n.left), _eval(n.right))
            if isinstance(n, ast.UnaryOp):
                return operator.neg(_eval(n.operand))
            if isinstance(n, ast.Name):
                return ns[n.id]
            if isinstance(n, ast.Constant):
                return Decimal(str(n.value))
            raise ValueError(f"Unsupported AST node: {n}")
        return Decimal(str(round(_eval(node),4)))
    def _aggregate_or_fetch(self, kf: str, fkwargs: Dict[str,Any]) -> Decimal:
        return self._aggregate_or_fetch_for_period(kf, fkwargs, self.period)
    def _aggregate_or_fetch_for_period(self, kf: str, fkwargs: Dict[str,Any], period_code: str) -> Decimal:
        for fn, aggfunc in _AGG_FUNCS.items():
            if kf.upper().startswith(fn + ':'):
                real_kf = kf.split(':',1)[1]
                agg = aggfunc('value')
                qs = PlanningFact.objects.filter(
                    session=self.session,
                    period__code=period_code,
                    key_figure__code=real_kf,
                    **{dim:inst for dim,inst in fkwargs.items()}
                ).aggregate(agg)
                return Decimal(str(qs[f"value__{fn.lower()}"] or 0))
        rec = PlanningFact.objects.filter(
            session=self.session,
            period__code=period_code,
            key_figure__code=kf,
            **{dim:inst for dim,inst in fkwargs.items()}
        ).first()
        return rec.value if rec else Decimal('0')
    def _shift(self, kf: str, offset: Any, dims_map: Dict[str,Any]) -> Decimal:
        all_codes = list(Period.objects.order_by('order').values_list('code', flat=True))
        try:
            idx = all_codes.index(self.period)
        except ValueError:
            return Decimal('0')
        ni = idx + int(offset)
        if ni < 0 or ni >= len(all_codes):
            return Decimal('0')
        new_period = all_codes[ni]
        return self._aggregate_or_fetch_for_period(kf, dims_map, new_period)
    def _lookup(self, kf: str, base_dims: Dict[str,Any], overrides: Dict[str,Any]) -> Decimal:
        dims = base_dims.copy()
        for dim_name, val in overrides.items():
            try:
                inst = apps.get_model('bps', dim_name).objects.get(pk=int(val))
                dims[dim_name] = inst
            except Exception:
                continue
        return self._aggregate_or_fetch_for_period(kf, dims, self.period)
    def _replace_reference_data(self, expr: str, _dims_map) -> str:
        def repl(m):
            name = m.group(1)
            tail = m.group(2)
            return f"__refdata__('{name}', {{{tail}}})"
        return self._re_refdata.sub(repl, expr)
    def _get_record(self, kf_code: str, dims: dict, create: bool):
        period = Period.objects.get(code=self.period)
        kf     = KeyFigure.objects.get(code=kf_code)
        known = {}
        extra = {}
        for k, inst in dims.items():
            if k in ("orgunit", "org_unit"):   known["org_unit"] = inst
            elif k in ("service",):            known["service"]  = inst
            elif k in ("account",):            known["account"]  = inst
            else:                              extra[k] = inst.pk
        base = dict(session=self.session, period=period, key_figure=kf, **known)
        fact = PlanningFact.objects.filter(**base, extra_dimensions_json=extra).first()
        if fact:
            return fact
        if not create:
            return PlanningFact(**base, extra_dimensions_json=extra, value=Decimal("0"))
        return PlanningFact.objects.create(
            request=self.session.requests.order_by('-created_at').first() or
                    DataRequest.objects.create(session=self.session, description="Formula write"),
            version=self.session.layout_year.version,
            year=self.session.layout_year.year,
            uom=None, ref_uom=None,
            extra_dimensions_json=extra, **base
        )
```

### `views/manual_planning.py`
```python
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from django.urls import reverse
from bps.models.models_layout import PlanningLayoutYear, LayoutDimensionOverride
from bps.models.models_dimension import Service, OrgUnit
from bps.models.models import KeyFigure
import json
class ManualPlanningView(TemplateView):
    template_name = "bps/manual_planning.html"
    def get_context_data(self, layout_id, year_id, version_id, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ly = get_object_or_404(
            PlanningLayoutYear,
            layout_id=layout_id,
            year_id=year_id,
            version_id=version_id,
        )
        grouping = ly.period_groupings.filter(months_per_bucket=1).first()
        raw_buckets = grouping.buckets() if grouping else []
        buckets_js = [
            {
                "code": b["code"],
                "name": b["name"],
                "periods": [p.code for p in b["periods"]],
            }
            for b in raw_buckets
        ]
        all_dims_qs    = ly.layout.dimensions.select_related("content_type").order_by("order")
        header_dims_qs = all_dims_qs.filter(is_header=True)
        row_dims_qs    = all_dims_qs.filter(is_row=True)
        def _choices_for(dim):
            Model = dim.content_type.model_class()
            qs = Model.objects.all()
            ov = LayoutDimensionOverride.objects.filter(layout_year=ly, dimension=dim).first()
            if ov and ov.allowed_values:
                pks   = [v for v in ov.allowed_values if isinstance(v, int)]
                codes = [v for v in ov.allowed_values if isinstance(v, str)]
                if pks:
                    qs = qs.filter(pk__in=pks)
                if codes and hasattr(Model, "code"):
                    qs = qs.filter(code__in=codes)
            return [{"id": o.pk, "name": str(o)} for o in qs]
        def _driver_payload(qs):
            out = []
            for ld in qs:
                Model = ld.content_type.model_class()
                label = getattr(Model._meta, "verbose_name", ld.content_type.model.title())
                out.append({
                    "key":     ld.content_type.model,
                    "label":   str(label),
                    "choices": _choices_for(ld),
                })
            return out
        drivers_for_header = _driver_payload(header_dims_qs)
        drivers_for_rows   = _driver_payload(row_dims_qs)
        header_defaults = {}
        if isinstance(ly.header_dims, dict):
            header_keys = {d["key"] for d in drivers_for_header}
            for k, v in ly.header_dims.items():
                if k in header_keys:
                    header_defaults[k] = v
        pkf_qs   = ly.layout.key_figures.select_related("key_figure").order_by("display_order", "id")
        kf_codes = [pkf.key_figure.code for pkf in pkf_qs]
        kf_meta = {
            k.code: {"decimals": k.display_decimals}
            for k in KeyFigure.objects.filter(code__in=kf_codes)
        }
        services = list(Service.objects.filter(is_active=True).values("code", "name"))
        org_units = list(OrgUnit.objects.values("code", "name"))
        grouping_dims_qs = all_dims_qs.filter(group_priority__isnull=False).order_by("group_priority")
        if not grouping_dims_qs.exists():
            grouping_dims_qs = all_dims_qs.filter(is_row=True).order_by("order")
        def _field_for_key(key: str) -> str:
            if key == "orgunit":
                return "org_unit_code"
            if key == "service":
                return "service_code"
            return f"{key}_code"
        row_field_candidates = {
            _field_for_key(d["key"]) for d in _driver_payload(row_dims_qs)
        }
        if grouping_dims_qs.exists():
            configured_fields = [_field_for_key(ld.content_type.model) for ld in grouping_dims_qs]
            row_group_fields = [f for f in configured_fields if f in row_field_candidates]
        else:
            row_group_fields = []
        row_group_start_open = bool(
            getattr(ly, "group_start_open", getattr(ly.layout, "group_start_open", False))
        )
        ctx.update(
            {
                "layout_year": ly,
                "buckets_js": json.dumps(buckets_js),
                "kf_codes": json.dumps(kf_codes),
                "kf_meta_js": json.dumps(kf_meta),
                "header_drivers": drivers_for_header,
                "header_drivers_js": json.dumps(drivers_for_header),
                "row_drivers": drivers_for_rows,
                "row_drivers_js": json.dumps(drivers_for_rows),
                "header_defaults_js": json.dumps(header_defaults),
                "api_url": reverse("bps_api:planning_grid"),
                "update_url": reverse("bps_api:planning_grid_update"),
                "services_js": json.dumps(services),
                "org_units_js": json.dumps(org_units),
                "row_group_fields_js": json.dumps(row_group_fields),
                "row_group_start_open_js": json.dumps(row_group_start_open),
            }
        )
        return ctx
```

### `views/views.py`
```python
from uuid import UUID
import json
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.contrib import messages
from django.views import View
from django.views.generic import (
    TemplateView, ListView, DetailView,
    FormView, RedirectView
)
from django.views.generic.edit import FormMixin
from django.forms import modelform_factory
from ..models.models_workflow import ScenarioStep, ScenarioStage
from ..models.models import (
    PlanningScenario, PlanningSession, PlanningStage, PlanningLayoutYear,
    PlanningLayout, Year, Version, Period,
    PlanningFact, DataRequest, Constant, SubFormula,
    Formula, PlanningFunction, ReferenceData
)
from .forms import (
    PlanningSessionForm, PeriodSelector, ConstantForm,
    SubFormulaForm, FormulaForm, FactForm,
    PlanningFunctionForm, ReferenceDataForm
)
from .formula_executor import FormulaExecutor
class ScenarioDashboardView(TemplateView):
    template_name = "bps/scenario_dashboard.html"
    def get_context_data(self, **kwargs):
        scenario = get_object_or_404(PlanningScenario, code=kwargs["code"])
        sessions = PlanningSession.objects.filter(
            scenario=scenario
        ).select_related("org_unit", "current_step__stage", "current_step__layout")
        steps = (
            ScenarioStep.objects
            .filter(scenario=scenario)
            .select_related("stage", "layout")
            .order_by("order")
        )
        return {
            "scenario":   scenario,
            "sessions":   sessions,
            "steps":      steps,
            "org_units":  scenario.org_units.all(),
        }
class DashboardView(TemplateView):
    template_name = 'bps/dashboard.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().year
        all_years = Year.objects.order_by('code').values_list('code', flat=True)
        selected_year = self.request.GET.get('year', str(current_year + 1))
        if selected_year not in all_years:
            selected_year = all_years[-1] if all_years else str(current_year)
        ctx.update({
            'all_years': all_years,
            'selected_year': selected_year,
            'layouts': PlanningLayoutYear.objects.filter(
                year__code=selected_year
            ).select_related('layout','version'),
            'incomplete_sessions': PlanningSession.objects.filter(
                status=PlanningSession.Status.DRAFT
            )
            .select_related(
               'org_unit',
               'scenario__layout_year__layout',
               'scenario__layout_year__version'
            )
            .order_by('org_unit__name'),
            'planning_funcs': [
                {'name': 'Inbox', 'url': reverse('bps:inbox')},
                {'name': 'Notifications', 'url': reverse('bps:notifications')},
                {'name': 'Start New Session', 'url': reverse('bps:session_list')},
                {'name': 'Run All Formulas', 'url': reverse('bps:formula_list')},
                {'name': 'Create Reference Data', 'url': reverse('bps:reference_data_list')},
            ],
            'admin_links': [
                {'name': 'Layouts', 'url': reverse('admin:bps_planninglayout_changelist')},
                {'name': 'Layout-Years', 'url': reverse('admin:bps_planninglayoutyear_changelist')},
                {'name': 'Periods', 'url': reverse('admin:bps_period_changelist')},
                {'name': 'Sessions', 'url': reverse('admin:bps_planningsession_changelist')},
                {'name': 'Data Requests', 'url': reverse('admin:bps_datarequest_changelist')},
                {'name': 'Constants', 'url': reverse('bps:constant_list')},
                {'name': 'SubFormulas', 'url': reverse('bps:subformula_list')},
                {'name': 'Formulas', 'url': reverse('bps:formula_list')},
                {'name': 'Functions', 'url': reverse('bps:planning_function_list')},
                {'name': 'Rate Cards', 'url': reverse('admin:bps_ratecard_changelist')},
                {'name': 'Positions', 'url': reverse('admin:bps_position_changelist')},
            ],
        })
        return ctx
class ProfileView(View):
    def get(self, request):
        return HttpResponse('')
class InboxView(TemplateView):
    template_name = 'bps/inbox.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['breadcrumbs'] = [
            {'url': reverse('bps:dashboard'), 'title': 'Dashboard'},
            {'url': self.request.path,    'title': 'Inbox'},
        ]
        ctx['items'] = []
        return ctx
class NotificationsView(TemplateView):
    template_name = 'bps/notifications.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['breadcrumbs'] = [
            {'url': reverse('bps:dashboard'), 'title': 'Dashboard'},
            {'url': self.request.path,        'title': 'Notifications'},
        ]
        ctx['notifications'] = []
        return ctx
class ManualPlanningSelectView(TemplateView):
    template_name = "bps/manual_planning_select.html"
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["layouts"] = PlanningLayoutYear.objects.select_related(
            "layout", "year", "version"
        )
        return ctx
class PlanningSessionListView(ListView):
    model = PlanningSession
    template_name = 'bps/session_list.html'
    context_object_name = 'sessions'
    ordering = ['-created_at']
    paginate_by = 50
class PlanningSessionDetailView(FormMixin, DetailView):
    model = PlanningSession
    template_name = "bps/session_detail.html"
    context_object_name = "sess"
    form_class = PlanningSessionForm
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object()
        return kwargs
    def get_context_data(self, **ctx):
        ctx = super().get_context_data(**ctx)
        sess   = self.object
        step   = sess.current_step
        stage  = step.stage
        ly      = sess.layout_year
        layout  = ly.layout
        version = ly.version
        grouping = ly.period_groupings.filter(months_per_bucket=1).first()
        buckets  = grouping.buckets() if grouping else []
        row_dims = (
            layout.dimensions
                  .filter(is_row=True)
                  .select_related("content_type")
                  .order_by("order")
        )
        ov_map = {
            ov.dimension_id: ov
            for ov in ly.dimension_overrides.select_related("dimension__content_type")
        }
        drivers = []
        for dim in row_dims:
            Model = dim.content_type.model_class()
            qs = Model.objects.all()
            ov = ov_map.get(dim.id)
            if ov and ov.allowed_values:
                pks   = [v for v in ov.allowed_values if isinstance(v, int)]
                codes = [v for v in ov.allowed_values if isinstance(v, str)]
                if pks:
                    qs = qs.filter(pk__in=pks)
                if codes and hasattr(Model, "code"):
                    qs = qs.filter(code__in=codes)
            drivers.append({
                "key":     dim.content_type.model,
                "label":   Model._meta.verbose_name.title(),
                "choices": [{"id": o.pk, "name": str(o)} for o in qs],
            })
        kf_codes = [
            lkf.key_figure.code
            for lkf in layout.key_figures.select_related("key_figure").order_by("display_order", "id")
        ]
        api_url = reverse('bps_api:planning_pivot')
        dr = sess.requests.order_by('-created_at').first()
        facts_qs = (
            PlanningFact.objects.filter(request=dr)
            if dr else PlanningFact.objects.none()
        )
        facts_qs = facts_qs.select_related(
            "period", "key_figure", "uom", "service"
        ).order_by("period__order", "key_figure__code", "service__name")
        try:
            page_size = int(self.request.GET.get("page_size", 10))
        except (TypeError, ValueError):
            page_size = 10
        if page_size <= 0:
            page_size = 10
        try:
            page_num = int(self.request.GET.get("page", 1))
        except (TypeError, ValueError):
            page_num = 1
        paginator = Paginator(facts_qs, page_size)
        page_obj = paginator.get_page(page_num)
        ctx.update({
            "sess":         sess,
            "current_step": step,
            "stage":        stage,
            "layout":       layout,
            "dr":           dr,
            "facts":        page_obj.object_list,
            "facts_page":   page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "paginator":    paginator,
            "page_size":    page_size,
            "page_sizes":   [10, 25, 50, 100],
            "buckets":      buckets,
            "drivers":      drivers,
            "kf_codes":     kf_codes,
            "api_url":      api_url,
            "can_edit":     sess.can_edit(self.request.user),
            "form":         self.get_form(),
            "breadcrumbs": [
                {"url": reverse("bps:dashboard"),    "title": "Dashboard"},
                {"url": reverse("bps:session_list"), "title": "Sessions"},
                {"url": self.request.path,           "title": sess.org_unit.name},
            ],
            "can_advance":  self.request.user.is_staff and ScenarioStep.objects.filter(
                scenario=sess.scenario,
                order__gt=step.order
            ).exists(),
        })
        return ctx
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        sess = self.object
        if "start" in request.POST:
            form = PlanningSessionForm(request.POST, instance=sess)
            if form.is_valid():
                sess = form.save(commit=False)
                sess.created_by = request.user
                sess.save()
                messages.success(request, "Session started.")
                return redirect("bps:session_detail", pk=sess.pk)
        if "apply" in request.POST:
            ps = PeriodSelector(request.POST, session=sess)
            if ps.is_valid():
                request.session["grouping_id"] = ps.cleaned_data["grouping"].pk
                return redirect("bps:session_detail", pk=sess.pk)
        return self.get(request, *args, **kwargs)
class AdvanceStepView(View):
    def post(self, request, pk):
        sess = get_object_or_404(PlanningSession, pk=pk)
        current_order = sess.current_step.order
        next_step = (
            ScenarioStep.objects
            .filter(scenario=sess.scenario, order__gt=current_order)
            .order_by("order")
            .first()
        )
        if not next_step:
            messages.warning(request, "Already at final step.")
        else:
            sess.current_step = next_step
            sess.save(update_fields=["current_step"])
            messages.success(request, f"Advanced to step: {next_step.stage.name}")
        return redirect("bps:session_detail", pk=pk)
class AdvanceStageView(View):
    def get(self, request, pk):
        sess = get_object_or_404(PlanningSession, pk=pk)
        current_stage = sess.current_step.stage
        next_stage = (
            PlanningStage.objects
            .filter(order__gt=current_stage.order)
            .order_by('order')
            .first()
        )
        if not next_stage:
            messages.warning(request, "Already at final stage.")
            return redirect('bps:session_detail', pk=pk)
        next_step = (
            ScenarioStep.objects
            .filter(scenario=sess.scenario, stage=next_stage)
            .order_by('order')
            .first()
        )
        if not next_step:
            messages.warning(request, f"No step defined for stage: {next_stage.name}")
        else:
            sess.current_step = next_step
            sess.save(update_fields=['current_step'])
            messages.success(request, f"Moved to stage: {next_stage.name}")
        return redirect('bps:session_detail', pk=pk)
class ConstantListView(FormMixin, ListView):
    model = Constant
    template_name = 'bps/constant_list.html'
    context_object_name = 'consts'
    form_class = ConstantForm
    success_url = reverse_lazy('bps:constant_list')
    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "Constant saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)
class SubFormulaListView(FormMixin, ListView):
    model = SubFormula
    template_name = 'bps/subformula_list.html'
    context_object_name = 'subs'
    form_class = SubFormulaForm
    success_url = reverse_lazy('bps:subformula_list')
    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "SubFormula saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)
class FormulaListView(FormMixin, ListView):
    model = Formula
    template_name = 'bps/formula_list.html'
    context_object_name = 'formulas'
    form_class = FormulaForm
    success_url = reverse_lazy('bps:formula_list')
    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "Formula saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)
class FormulaRunView(View):
    def get(self, request, pk):
        formula = get_object_or_404(Formula, pk=pk)
        session = request.user.planningsession_set.filter(
            status=PlanningSession.Status.DRAFT
        ).first()
        period = request.GET.get('period', '01')
        entries = FormulaExecutor(formula, session, period, preview=False).execute()
        messages.success(
            request,
            f"Executed {formula.name}, {entries.count()} entries updated."
        )
        return redirect('bps:formula_list')
class PlanningFunctionListView(FormMixin, ListView):
    model = PlanningFunction
    template_name = 'bps/planning_function_list.html'
    context_object_name = 'functions'
    form_class = PlanningFunctionForm
    success_url = reverse_lazy('bps:planning_function_list')
    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "Planning Function saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)
class RunPlanningFunctionView(View):
    def get(self, request, pk, session_id):
        func = get_object_or_404(PlanningFunction, pk=pk)
        session = get_object_or_404(PlanningSession, pk=session_id)
        result = func.execute(session)
        messages.success(
            request,
            f"{func.get_function_type_display()} executed, result: {result}"
        )
        return redirect('bps:session_detail', pk=session_id)
class CopyActualView(View):
    def get(self, request):
        messages.info(request, "Copy Actual → Plan is not yet implemented.")
        return redirect('bps:dashboard')
class DistributeKeyView(View):
    def get(self, request):
        messages.info(request, "Distribute by Key is not yet implemented.")
        return redirect('bps:dashboard')
class ReferenceDataListView(FormMixin, ListView):
    model = ReferenceData
    template_name = 'bps/reference_data_list.html'
    context_object_name = 'references'
    form_class = ReferenceDataForm
    success_url = reverse_lazy('bps:reference_data_list')
    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "Reference Data saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)
DataRequestForm = modelform_factory(DataRequest, fields=['description'])
class DataRequestListView(ListView):
    model = DataRequest
    template_name = 'bps/data_request_list.html'
    context_object_name = 'data_requests'
    ordering = ['-created_at']
class DataRequestDetailView(FormMixin, DetailView):
    model = DataRequest
    template_name = 'bps/data_request_detail.html'
    context_object_name = 'dr'
    form_class = DataRequestForm
    def get_success_url(self):
        return reverse_lazy('bps:data_request_detail', kwargs={'pk': self.object.pk})
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "DataRequest updated.")
            return redirect(self.get_success_url())
        return self.form_invalid(form)
class FactListView(FormMixin, ListView):
    template_name = 'bps/fact_list.html'
    context_object_name = 'facts'
    form_class = FactForm
    def get_queryset(self):
        return PlanningFact.objects.filter(
            request__pk=self.kwargs['request_id']
        ).order_by('period')
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['dr'] = get_object_or_404(DataRequest, pk=self.kwargs['request_id'])
        return ctx
    def get_success_url(self):
        return reverse_lazy('bps:fact_list', kwargs={'request_id': self.kwargs['request_id']})
    def post(self, request, *args, **kwargs):
        dr = get_object_or_404(DataRequest, pk=self.kwargs['request_id'])
        form = self.get_form()
        if form.is_valid():
            fact = form.save(commit=False)
            fact.request = dr
            fact.session = dr.session
            fact.save()
            messages.success(request, "PlanningFact added.")
            return redirect(self.get_success_url())
        return self.form_invalid(form)
class VariableListView(ConstantListView):
    template_name = 'bps/variable_list.html'
    success_url = reverse_lazy('bps:variable_list')
```

### `views/views_decorator.py`
```python
from rest_framework.response import Response
from ..models.models import PlanningSession
def require_stage(stage_code):
    def decorator(fn):
        def wrapped(self, request, *args, **kw):
            sess = PlanningSession.objects.get(pk=kw.get('session_id'))
            if sess.current_stage.code != stage_code \
               and not sess.current_stage.can_run_in_parallel:
                return Response(
                    {"detail": f"Must be in {stage_code} step to call this."},
                    status=403
                )
            return fn(self, request, *args, **kw)
        return wrapped
    return decorator
```

### `views/views_planner.py`
```python
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from ..access import allowed_orgunits_qs, is_enterprise_planner, set_acting_as, clear_acting_as, get_effective_delegator, can_act_as
from ..models.models_access import Delegation
from ..models.models_dimension import OrgUnit
User = get_user_model()
@method_decorator(login_required, name="dispatch")
class PlannerDashboard(View):
    template_name = "bps/planner/dashboard.html"
    def get(self, request):
        allowed_qs = allowed_orgunits_qs(request.user, request)
        effective_delegator = get_effective_delegator(request)
        delegations = Delegation.objects.filter(delegatee=request.user, active=True)
        ctx = {
            "is_enterprise": is_enterprise_planner(request.user),
            "effective_delegator": effective_delegator,
            "delegations": delegations.select_related("delegator"),
            "allowed_ous": allowed_qs.order_by("name"),
        }
        return render(request, self.template_name, ctx)
@login_required
def act_as_start(request, user_id):
    delegator = get_object_or_404(User, pk=user_id)
    d = can_act_as(request.user, delegator)
    if not (d and d.is_active()):
        return HttpResponseForbidden("No active delegation from this user.")
    set_acting_as(request, delegator)
    return HttpResponseRedirect("/planner/")
@login_required
def act_as_stop(request):
    clear_acting_as(request)
    return HttpResponseRedirect("/planner/")
@login_required
def api_allowed_ous(request):
    qs = allowed_orgunits_qs(request.user, request).order_by("name")
    data = [{"id": ou.id, "code": ou.code, "name": ou.name, "path": ou.get_path() if hasattr(ou, "get_path") else ou.name} for ou in qs]
    return JsonResponse({"results": data})
```

### `views/viewsets.py`
```python
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
import csv
from bps.models.models import PlanningFact, OrgUnit
from ..serializers import PlanningFactSerializer, PlanningFactCreateUpdateSerializer
from ..serializers import OrgUnitSerializer
class PlanningFactViewSet(viewsets.ModelViewSet):
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
    queryset = OrgUnit.objects.all()
    serializer_class = OrgUnitSerializer
```

