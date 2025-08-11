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
from bps.models.models_dimension import OrgUnit, InternalOrder, Service
from bps.models.models_layout import PlanningLayoutYear
from bps.models.models_resource import Position, Skill, RateCard
from bps.models.models_workflow import PlanningScenario, PlanningSession, ScenarioStep

User = get_user_model()
random.seed(42)

def get_dim_values_for_model(Model):
    if Model is Position:
        return list(Position.objects.all())
    if Model is InternalOrder:
        return list(InternalOrder.objects.all())
    if Model is Service:
        return list(Service.objects.filter(is_active=True))
    if Model is OrgUnit:
        return list(OrgUnit.objects.exclude(code="ROOT"))
    if Model is Skill:
        return list(Skill.objects.all())
    # Unknown/unsupported template dimension – return empty to avoid explosion
    return []

class Command(BaseCommand):
    help = "Step 3: Populate each session with demo PlanningFact rows"

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

        # Sanity: constants
        for name in ("INFLATION_RATE", "GROWTH_FACTOR"):
            if not Constant.objects.filter(name=name).exists():
                self.stderr.write(f"❌ Missing constant {name}; run master load first.")
                return

        periods = list(Period.objects.order_by("order"))

        lys = PlanningLayoutYear.objects.select_related("layout", "year", "version").prefetch_related("org_units")
        if options.get("year_code"):
            lys = lys.filter(year__code=options["year_code"])

        for ply in lys:
            layout = ply.layout
            layout_code = layout.code

            # Template-level dims & KFs
            dims_qs = layout.dimensions.filter(is_row=True).select_related("content_type").order_by("order")
            dim_models = [d.content_type.model_class() for d in dims_qs]

            pkf_qs = layout.key_figures.select_related("key_figure").order_by("display_order")
            kf_objs = [pkf.key_figure for pkf in pkf_qs]
            if not kf_objs:
                self.stdout.write(f"→ No KeyFigures linked to {layout_code}; skipping.")
                continue

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

            for org in ply.org_units.all():
                # Build combinations
                if layout_code == "RES_CON":
                    # Keep richer mix for contractor layout
                    ios = list(InternalOrder.objects.filter(cc_code=org.code))
                    rc_combos = [
                        (rc.resource_type, rc.skill, rc.level, rc.country)
                        for rc in RateCard.objects.all()
                    ]
                    combos = [(io, sk) for io in ios for (_, sk, _, _) in rc_combos]
                    # reduce cardinality
                    if len(combos) > 40:
                        combos = random.sample(combos, 40)
                    extra_template = [
                        ("ResourceType", [rc.resource_type for rc in RateCard.objects.all()]),
                        ("Level",        sorted({rc.level for rc in RateCard.objects.all()})),
                        ("Country",      sorted({rc.country for rc in RateCard.objects.all()})),
                    ]
                else:
                    combos = list(product(*dim_values)) if dim_values else [()]
                    extra_template = []

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
                    steps = list(ScenarioStep.objects.filter(scenario=scenario).order_by("order"))
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

                existing = {}
                qs = PlanningFact.objects.filter(session=sess, request=dr, version=ply.version)
                for f in qs.only(
                    "pk", "period_id", "org_unit_id", "service_id", "key_figure_id", "extra_dimensions_json"
                ):
                    key = (
                        f.period_id,
                        f.org_unit_id,
                        f.service_id,
                        f.key_figure_id,
                        frozenset((f.extra_dimensions_json or {}).items()),
                    )
                    existing[key] = f

                to_create, to_update = [], []

                for combo in combos:
                    combo = combo if isinstance(combo, tuple) else (combo,)

                    # Build extra json (use model class names as keys)
                    extra = {}
                    for Model, val in zip(dim_models, combo):
                        if Model is Service:
                            continue
                        extra[Model.__name__] = getattr(val, "id", val)

                    # Add RES_CON synthetic extras
                    if layout_code == "RES_CON" and extra_template:
                        # Sample one consistent set per row
                        rt = random.choice(extra_template[0][1])
                        lvl = random.choice(extra_template[1][1])
                        ctry = random.choice(extra_template[2][1])
                        extra.update({"ResourceType": rt, "Level": lvl, "Country": ctry})

                    svc = None
                    if Service in dim_models:
                        svc = combo[dim_models.index(Service)]

                    for per in periods:
                        for kf in kf_objs:
                            # Simple random demo values by KF type
                            if kf.code in ("FTE", "MAN_MONTH", "LICENSE_VOLUME"):
                                val = Decimal(random.uniform(0.5, 3.0)).quantize(Decimal("0.01"))
                            elif kf.code in ("COST", "LICENSE_COST", "ADMIN_OVERHEAD", "TOTAL_COST"):
                                val = Decimal(random.uniform(1000, 10000)).quantize(Decimal("0.01"))
                            elif kf.code == "LICENSE_UNIT_PRICE":
                                val = Decimal(random.uniform(10, 200)).quantize(Decimal("0.01"))
                            elif kf.code == "UTIL":
                                val = Decimal(random.uniform(50, 100)).quantize(Decimal("0.01"))
                            else:
                                val = Decimal(random.uniform(1, 5)).quantize(Decimal("0.01"))

                            row_key = (
                                per.id,
                                org.id,
                                getattr(svc, "id", None),
                                kf.id,
                                frozenset(extra.items()),
                            )
                            if row_key in existing:
                                inst = existing[row_key]
                                inst.value = val
                                to_update.append(inst)
                            else:
                                to_create.append(
                                    PlanningFact(
                                        request=dr,
                                        session=sess,
                                        version=ply.version,
                                        year=ply.year,
                                        period=per,
                                        org_unit=org,
                                        service=svc,
                                        account=None,
                                        extra_dimensions_json=extra,
                                        key_figure=kf,
                                        value=val,
                                        uom=kf.default_uom,
                                    )
                                )

                if to_create:
                    PlanningFact.objects.bulk_create(to_create, ignore_conflicts=True)
                    self.stdout.write(f"   ● Created {len(to_create):,} new facts")
                if to_update:
                    PlanningFact.objects.bulk_update(to_update, ["value"], batch_size=500)
                    self.stdout.write(f"   ● Updated {len(to_update):,} existing facts")

        self.stdout.write(self.style.SUCCESS("✅ Demo generation complete."))