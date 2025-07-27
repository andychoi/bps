# api/views_manual.py
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from bps.models.models import PlanningLayoutYear, PlanningFact, PlanningLayoutDimension, Version
from .serializers import PlanningFactSerializer, PlanningFactPivotRowSerializer
from .utils import pivot_facts_grouped

class ManualPlanningGridAPIView(APIView):
    """
    GET: Return pivoted grid of facts for a given layout-year-version
    POST (bulk update): Accepts {layout_id, version, year, updates:[{id, field, value},...]} and saves.
    """
    def get(self, request):
        layout_id = request.query_params.get('layout')
        year_id   = request.query_params.get('year')
        version   = request.query_params.get('version')
        use_ref   = request.query_params.get('ref') == '1'
        ly = get_object_or_404(PlanningLayoutYear, pk=layout_id)
        facts = PlanningFact.objects.filter(session__layout_year=ly)
        if year_id:
            facts = facts.filter(year_id=year_id)
        if version:
            facts = facts.filter(version__code=version)
        pivot = pivot_facts_grouped(facts, use_ref_value=use_ref)
        # pivot is already a list of dicts with dynamic month‐cols
        return Response(pivot)

    @transaction.atomic
    def post(self, request):
        payload = request.data
        layout_id = payload.get('layout')
        ly = get_object_or_404(PlanningLayoutYear, pk=layout_id)
        errors = []
        for upd in payload.get('updates', []):
            try:
                fact = PlanningFact.objects.get(pk=upd['id'], session__layout_year=ly)
                # Only allow the two numeric fields
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
    """
    GET /api/bps_planning_grid?base=<pk>&compare=<pk>
    also supports legacy ?layout=<pk> → treated as base=<pk>
    """
    def get(self, request):
        # 1. parse params
        base_id    = request.query_params.get("base") or request.query_params.get("layout")
        compare_id = request.query_params.get("compare")

        if not base_id:
            return Response(
                {"error": "Missing 'base' (or legacy 'layout') query parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. fetch & permission-check base layout_year
        base_ly = get_object_or_404(PlanningLayoutYear, pk=base_id)
        allowed_versions = Version.objects.filter(
            Q(is_public=True) | Q(created_by=request.user)
        ).values_list("pk", flat=True)

        if base_ly.version_id not in allowed_versions:
            return Response(
                {"error": "You do not have permission to view the base layout."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 3. optionally fetch & permission-check compare layout_year
        compare_ly = None
        if compare_id:
            compare_ly = get_object_or_404(PlanningLayoutYear, pk=compare_id)
            if compare_ly.version_id not in allowed_versions:
                return Response(
                    {"error": "You do not have permission to view the compare layout."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # 4. load facts for each
        base_qs = PlanningFact.objects.filter(
            session__layout_year=base_ly
        ).select_related("period", "key_figure", "org_unit", "service")

        compare_qs = None
        if compare_ly:
            compare_qs = PlanningFact.objects.filter(
                session__layout_year=compare_ly
            ).select_related("period", "key_figure", "org_unit", "service")

        # 5. pivot into rows
        # key = (org_unit.code, service.code)
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
                col = f"M{f.period.code}_{f.key_figure.code}"
                cell = row.setdefault(col, {})
                cell[tag] = float(f.value)

        ingest(base_qs,   "base")
        if compare_qs:
            ingest(compare_qs, "compare")

        # 6. return
        return Response({"data": list(rows.values())})


class PlanningGridBulkUpdateAPIView(APIView):
    """
    PATCH /api/bps_planning_grid_update
    {
      "layout": <layout_year_id>,
      "version": "<VERSION_CODE>",      # optional
      "year": "<YEAR_CODE>",            # optional
      "action_type": "DELTA"|"RESET",   # default DELTA
      "updates": [
        { "id": <fact_id>, "field": "value"|"ref_value", "value": <new> },
        …
      ]
    }
    """
    def patch(self, request):
        layout_id   = request.data.get("layout")
        action      = request.data.get("action_type", "DELTA").upper()
        version     = request.data.get("version")
        year_code   = request.data.get("year")
        updates     = request.data.get("updates", [])

        # 1) Fetch the layout_year context
        ly = get_object_or_404(PlanningLayoutYear, pk=layout_id)
        facts_qs = PlanningFact.objects.filter(session__layout_year=ly)
        if version:
            facts_qs = facts_qs.filter(version__code=version)
        if year_code:
            facts_qs = facts_qs.filter(year__code=year_code)

        # 2) RESET?
        if action == "RESET":
            facts_qs.update(value=0, ref_value=0)

        # 3) Apply each update with validation
        successful, errors = 0, []
        # pre‐load your dimension rules for this layout_year:
        dims = { d.content_type.model: d for d in ly.layout_dimensions.all() }

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
                ).get(pk=fact_id, session__layout_year=ly)
            except PlanningFact.DoesNotExist:
                errors.append({"update": upd, "error": "Fact not found"})
                continue

            # --- dimension validation ---
            # for each row‐dimension on this layout, ensure fact.org_unit etc fits the filter
            for ld in dims.values():
                model_name = ld.content_type.model  # e.g. "orgunit"
                if not ld.is_row:
                    continue
                # pick the corresponding foreign‐key attribute on fact:
                inst = getattr(fact, model_name, None)
                if not inst:
                    continue
                # 1) if allowed_values set, enforce:
                if ld.allowed_values and inst.pk not in ld.allowed_values:
                    raise ValueError(f"{model_name} {inst} not in allowed_values")
                # 2) if filter_criteria set, check the instance matches:
                if ld.filter_criteria:
                    Model = ld.content_type.model_class()
                    if not Model.objects.filter(pk=inst.pk, **ld.filter_criteria).exists():
                        raise ValueError(
                            f"{model_name} {inst} fails filter {ld.filter_criteria}"
                        )
            # ---------------------------------

            # perform the update
            setattr(fact, field, Decimal(str(val)))
            fact.save(update_fields=[field])
            successful += 1

        # 4) Return multi‐status if any errors
        if errors:
            return Response(
                {"updated": successful, "errors": errors},
                status=status.HTTP_207_MULTI_STATUS
            )

        return Response({"updated": successful}, status=status.HTTP_200_OK)