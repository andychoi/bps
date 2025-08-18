# bps/bps/management/commands/bps_demo_3plan.py

import random
from decimal import Decimal
from itertools import product

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from bps.models.models import (
    DataRequest,
    PlanningFact,
    KeyFigure,
    Constant,
    Period,
)
from bps.models.models_extras import DimensionKey, PlanningFactExtra
from bps.models.models_dimension import OrgUnit, InternalOrder, Service
from bps.models.models_layout import PlanningLayoutYear
from bps.models.models_resource import Position, Skill, RateCard
from bps.models.models_workflow import PlanningScenario, PlanningSession, ScenarioStep

User = get_user_model()
random.seed(42)

BULK_FACT_BATCH = 4000
BULK_EXTRA_BATCH = 8000
RES_CON_MAX_COMBOS = 40  # cap to avoid explosion; adjust as desired


def get_dim_values_for_model(Model):
    """Return small lists to avoid enormous cartesian products."""
    if Model is Position:
        return list(Position.objects.all().only("id", "code").order_by("id"))
    if Model is InternalOrder:
        return list(InternalOrder.objects.all().only("id", "code", "cc_code").order_by("id"))
    if Model is Service:
        return list(Service.objects.filter(is_active=True).only("id", "code").order_by("id"))
    if Model is OrgUnit:
        return list(OrgUnit.objects.exclude(code="ROOT").only("id", "code").order_by("id"))
    if Model is Skill:
        return list(Skill.objects.all().only("id", "name").order_by("id"))
    return []


class Command(BaseCommand):
    help = "Step 3: Populate each session with demo PlanningFact rows (optimized)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            "-y",
            dest="year_code",
            help="Only generate for LayoutYears whose Year.code matches this",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write("❌ No superuser found; aborting.")
            return

        # Sanity: constants exist
        for name in ("INFLATION_RATE", "GROWTH_FACTOR"):
            if not Constant.objects.filter(name=name).exists():
                self.stderr.write(f"❌ Missing constant {name}; run master load first.")
                return

        # Cache small reference tables
        periods = list(Period.objects.order_by("order").values("id"))
        period_ids = [p["id"] for p in periods]  # ids only

        # Cache all DimensionKey in memory (by string key)
        dim_key_map = {dk["key"]: dk for dk in DimensionKey.objects.all().values("id", "key", "content_type_id")}

        # Cache RateCard summaries once (used by RES_CON)
        ratecards = list(
            RateCard.objects.all().values("resource_type", "skill_id", "level", "country")
        )
        rc_resource_types = [rc["resource_type"] for rc in ratecards]
        rc_levels = sorted({rc["level"] for rc in ratecards})
        rc_countries = sorted({rc["country"] for rc in ratecards})

        lys = (
            PlanningLayoutYear.objects
            .select_related("layout", "year", "version")
            .prefetch_related("org_units", "layout__key_figures__key_figure")
        )
        if options.get("year_code"):
            lys = lys.filter(year__code=options["year_code"])

        for ply in lys:
            layout = ply.layout
            layout_code = layout.code

            # Template-level row dimensions & key figures
            dims_qs = (
                layout.dimensions
                .filter(is_row=True)
                .select_related("content_type")
                .order_by("order")
            )
            dim_models = [d.content_type.model_class() for d in dims_qs]

            pkf_qs = layout.key_figures.select_related("key_figure").order_by("display_order")
            kf_objs = [pkf.key_figure for pkf in pkf_qs]
            if not kf_objs:
                self.stdout.write(f"→ No KeyFigures linked to {layout_code}; skipping.")
                continue

            # Map: KeyFigure.id -> is_yearly
            pkf_map = {pkf.key_figure_id: pkf.is_yearly for pkf in pkf_qs}

            self.stdout.write(f"→ Generating for {layout_code} / {ply.year.code} / {ply.version.code}")

            # Scenario/session plumbing
            try:
                scenario = PlanningScenario.objects.get(layout_year=ply)
            except PlanningScenario.DoesNotExist:
                self.stderr.write(f"⚠️ No scenario for {ply}; skipping.")
                continue
            first_step = ScenarioStep.objects.filter(scenario=scenario).order_by("order").first()

            # Precompute value sets for dims
            dim_values = [get_dim_values_for_model(Model) for Model in dim_models]

            # For RES_CON, pre-cache IOs per OU on the fly (fast filter)
            for org in ply.org_units.all().only("id", "code"):
                # Build combinations
                if layout_code == "RES_CON":
                    ios = list(
                        InternalOrder.objects.filter(cc_code=org.code)
                        .only("id", "code", "cc_code")
                        .order_by("id")
                    )
                    # richer mix but capped
                    combos = [(io, sk) for io in ios for sk in Skill.objects.all().only("id").order_by("id")]
                    if len(combos) > RES_CON_MAX_COMBOS:
                        combos = random.sample(combos, RES_CON_MAX_COMBOS)
                    extra_template = [
                        ("ResourceType", rc_resource_types),
                        ("Level",        rc_levels),
                        ("Country",      rc_countries),
                    ]
                else:
                    combos = list(product(*dim_values)) if dim_values else [()]
                    extra_template = []

                # Ensure session
                sess, created = PlanningSession.objects.get_or_create(
                    scenario=scenario,
                    org_unit=org,
                    defaults={
                        "created_by": admin,
                        "current_step": first_step,
                        "status": PlanningSession.Status.DRAFT,
                    },
                )
                if created:
                    steps = list(ScenarioStep.objects.filter(scenario=scenario).only("id").order_by("order"))
                    chosen = random.choice(steps) if steps else first_step
                    if chosen:
                        sess.current_step = chosen
                        sess.status = {
                            "DRAFT": PlanningSession.Status.DRAFT,
                            "REVIEW": PlanningSession.Status.REVIEW,
                            "FINALIZE": PlanningSession.Status.COMPLETED,
                        }.get(chosen.stage.code, PlanningSession.Status.DRAFT)
                        if sess.status == PlanningSession.Status.COMPLETED and random.random() < 0.2:
                            sess.freeze(admin)
                        sess.save(update_fields=["current_step", "status", "frozen_by", "frozen_at"])

                desc = "Historical 2025" if ply.version.code == "ACTUAL" else f"{ply.version.code} Update"
                dr, _ = DataRequest.objects.get_or_create(
                    session=sess,
                    description=desc,
                    defaults={"created_by": admin, "action_type": "OVERWRITE" if ply.version.code == "ACTUAL" else "DELTA"},
                )

                # -------- Existing rows cache (FAST path) --------
                # Pull existing facts as raw dicts to avoid model instantiation overhead
                existing_rows = list(
                    PlanningFact.objects.filter(session_id=sess.id, request_id=dr.id, version_id=ply.version_id)
                    .values("id", "period_id", "org_unit_id", "service_id", "key_figure_id")
                )
                existing_ids = [r["id"] for r in existing_rows]

                # Pull extras for those facts once (id -> set of (key, object_id))
                extras_map = {}  # fact_id -> frozenset((key, object_id), ...)
                if existing_ids:
                    # Join via PlanningFactExtra and DimensionKey to get string key cheaply
                    pfe_rows = (
                        PlanningFactExtra.objects
                        .filter(fact_id__in=existing_ids)
                        .values("fact_id", "object_id", "key__key")
                    )
                    for row in pfe_rows:
                        fid = row["fact_id"]
                        tup = (row["key__key"], row["object_id"])
                        if fid in extras_map:
                            extras_map[fid].append(tup)
                        else:
                            extras_map[fid] = [tup]
                    # Freeze sets
                    for fid, lst in extras_map.items():
                        extras_map[fid] = frozenset(lst)

                # Build a lookup: composite key -> fact_id (or row dict)
                existing = {}
                for r in existing_rows:
                    fid = r["id"]
                    ex = extras_map.get(fid, frozenset())
                    row_key = (r["period_id"], r["org_unit_id"], r["service_id"], r["key_figure_id"], ex)
                    existing[row_key] = fid  # keep just id

                to_create_facts = []
                to_create_extras_payload = []  # (fact_list_index, [(key, value), ...])

                # -------- Generate new rows --------
                for combo in combos:
                    combo = combo if isinstance(combo, tuple) else (combo,)

                    # Build extra dict (skip Service; it's a first-class FK)
                    extra = {}
                    for Model, val in zip(dim_models, combo):
                        if Model is Service:
                            continue
                        # Store only the integer id
                        extra[Model.__name__] = getattr(val, "id", val)

                    # RES_CON synthetic extras
                    if layout_code == "RES_CON" and extra_template:
                        rt = random.choice(extra_template[0][1])
                        lvl = random.choice(extra_template[1][1])
                        ctry = random.choice(extra_template[2][1])
                        extra.update({"ResourceType": rt, "Level": lvl, "Country": ctry})

                    svc_id = None
                    if Service in dim_models:
                        svc = combo[dim_models.index(Service)]
                        svc_id = getattr(svc, "id", svc)

                    for kf in kf_objs:
                        is_yearly = bool(pkf_map.get(kf.id))
                        iter_periods = [None] if is_yearly else period_ids

                        for per_id in iter_periods:
                            # Demo values by KF - adjusted for yearly vs monthly
                            code = kf.code
                            multiplier = 12 if is_yearly else 1  # Scale up yearly values
                            
                            if code in ("FTE", "LICENSE_VOLUME"):
                                val = Decimal(random.uniform(0.5, 3.0)).quantize(Decimal("0.01"))
                            elif code == "MAN_MONTH":
                                val = Decimal(random.uniform(0.5, 3.0)).quantize(Decimal("0.01"))
                            elif code in ("COST", "LICENSE_COST", "ADMIN_OVERHEAD", "TOTAL_COST", "INFRA_COST"):
                                base_val = random.uniform(1000, 10000)
                                val = Decimal(base_val * multiplier).quantize(Decimal("0.01"))
                            elif code == "LICENSE_UNIT_PRICE":
                                val = Decimal(random.uniform(10, 200)).quantize(Decimal("0.01"))
                            elif code == "UTIL":
                                val = Decimal(random.uniform(50, 100)).quantize(Decimal("0.01"))
                            else:
                                val = Decimal(random.uniform(1, 5)).quantize(Decimal("0.01"))

                            ex_key = frozenset(extra.items())
                            row_key = (per_id, org.id, svc_id, kf.id, ex_key)
                            if row_key in existing:
                                # Update existing in one go later (no model instantiation here)
                                # We’ll do a single update statement per session/request/version to avoid per-row saves.
                                pass
                            else:
                                to_create_facts.append(
                                    PlanningFact(
                                        request_id=dr.id,
                                        session_id=sess.id,
                                        version_id=ply.version_id,
                                        year_id=ply.year_id,
                                        period_id=per_id,
                                        org_unit_id=org.id,
                                        service_id=svc_id,
                                        account_id=None,
                                        key_figure_id=kf.id,
                                        value=val,
                                        uom_id=kf.default_uom_id,
                                    )
                                )
                                to_create_extras_payload.append(ex_key)

                # -------- Bulk create facts (chunked) --------
                created_facts = []
                if to_create_facts:
                    for i in range(0, len(to_create_facts), BULK_FACT_BATCH):
                        chunk = to_create_facts[i:i + BULK_FACT_BATCH]
                        created_facts.extend(PlanningFact.objects.bulk_create(chunk, batch_size=BULK_FACT_BATCH))

                # -------- Bulk create extras for created facts (chunked) --------
                if created_facts:
                    # Build extras using cached DimensionKey ids & content_type_ids (no extra queries)
                    extras = []
                    for fact, ex_set in zip(created_facts, to_create_extras_payload):
                        if not ex_set:
                            continue
                        for key, obj_id in ex_set:
                            dk = dim_key_map.get(key)
                            if not dk:
                                continue
                            extras.append(
                                PlanningFactExtra(
                                    fact_id=fact.id,
                                    key_id=dk["id"],
                                    content_type_id=dk["content_type_id"],
                                    object_id=obj_id,
                                )
                            )
                    if extras:
                        for i in range(0, len(extras), BULK_EXTRA_BATCH):
                            PlanningFactExtra.objects.bulk_create(extras[i:i + BULK_EXTRA_BATCH], batch_size=BULK_EXTRA_BATCH)

                    self.stdout.write(f"   ● Created {len(created_facts):,} new facts with extras")

                # -------- Bulk update existing values (single query per KF to keep it simple) --------
                # For performance without instantiating models, do a coarse update per-kf/org/service/period set:
                # (You can skip this if you don’t need to randomize existing rows.)
                # Keeping it simple: no-op for existing in this optimized path to avoid heavy UPDATEs.
                # Uncomment below to update existing values if needed (will be slower):
                #
                # if existing:
                #     # Example: set a deterministic small tweak; or leave as-is
                #     pass

        self.stdout.write(self.style.SUCCESS("✅ Demo generation complete (optimized)."))