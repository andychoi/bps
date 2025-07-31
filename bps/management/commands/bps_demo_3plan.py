import random
from decimal import Decimal
from itertools import product

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from bps.models.models import (
    PlanningLayoutYear,
    PlanningScenario,
    PlanningSession,
    DataRequest,
    PlanningFact,
    KeyFigure,
    Constant,
    Period,
)
from bps.models.models_workflow import ScenarioStep
from bps.models.models_dimension import OrgUnit, InternalOrder
from bps.models.models_resource import Position, Skill, RateCard
from bps.models.models import Service

User = get_user_model()
random.seed(42)

# ─── Row‐dimension definitions ─────────────────────────────────────────────────
ROW_DIMS = {
    'RES_FTE':    ['Position', 'Skill'],
    'RES_CON':    ['InternalOrder', 'ResourceType', 'Skill', 'Level', 'Country'],
    'SYS_DEMAND': ['Service', 'Skill'],
    'RES_ALLOC':  ['Position', 'Service'],
    'SW_LICENSE': ['Service', 'InternalOrder'],
    'ADMIN_OVH':  ['OrgUnit', 'Service'],
    'SRV_COST':   ['Service'],
}

# ─── KeyFigures to generate for each layout ─────────────────────────────────────
KF_DEFS = {
    'RES_FTE':    ['FTE','MAN_MONTH'],
    'RES_CON':    ['MAN_MONTH','COST'],
    'SYS_DEMAND': ['MAN_MONTH'],
    'RES_ALLOC':  ['MAN_MONTH','UTIL'],
    'SW_LICENSE': ['LICENSE_VOLUME','LICENSE_UNIT_PRICE','LICENSE_COST'],
    'ADMIN_OVH':  ['ADMIN_OVERHEAD'],
    'SRV_COST':   ['COST','LICENSE_COST','ADMIN_OVERHEAD','TOTAL_COST'],
}

def get_dim_values(dim_name):
    """Return list of objects or simple values for each dimension."""
    if dim_name == 'Position':
        return list(Position.objects.all())
    if dim_name == 'InternalOrder':
        return list(InternalOrder.objects.all())
    if dim_name == 'Service':
        return list(Service.objects.filter(is_active=True))
    if dim_name == 'OrgUnit':
        return list(OrgUnit.objects.exclude(code='ROOT'))
    if dim_name == 'Skill':
        return list(Skill.objects.all())
    if dim_name == 'ResourceType':
        return [choice[0] for choice in RateCard.RESOURCE_CHOICES]
    if dim_name == 'Level':
        return sorted({rc.level for rc in RateCard.objects.all()})
    if dim_name == 'Country':
        return sorted({rc.country for rc in RateCard.objects.all()})
    raise ValueError(f"Unknown dimension: {dim_name}")

class Command(BaseCommand):
    help = "Step 3: Populate each session with demo PlanningFact rows"

    def add_arguments(self, parser):
        parser.add_argument(
            '--year','-y', dest='year_code',
            help="Only generate for LayoutYears whose Year.code matches this"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write("❌ No superuser found; aborting.")
            return

        # Ensure constants exist
        for name in ('INFLATION_RATE','GROWTH_FACTOR'):
            if not Constant.objects.filter(name=name).exists():
                self.stderr.write(f"❌ Missing constant {name}; run master load first.")
                return

        # Preload KeyFigures
        needed_kfs = {kf for codes in KF_DEFS.values() for kf in codes}
        kf_qs = KeyFigure.objects.filter(code__in=needed_kfs).select_related('default_uom')
        kf_map = {kf.code: kf for kf in kf_qs}
        missing = needed_kfs - set(kf_map)
        if missing:
            self.stderr.write(f"⚠️ Missing KeyFigures (will skip): {', '.join(sorted(missing))}")

        periods = list(Period.objects.order_by('order'))

        # Load LayoutYears
        lys = PlanningLayoutYear.objects.select_related('layout','year','version')\
                                         .prefetch_related('org_units')
        if options.get('year_code'):
            lys = lys.filter(year__code=options['year_code'])

        for ply in lys:
            layout_code = ply.layout.code
            dims        = ROW_DIMS.get(layout_code, [])
            raw_kfs     = KF_DEFS.get(layout_code, [])
            kf_codes    = [c for c in raw_kfs if c in kf_map]
            if not kf_codes:
                self.stdout.write(f"→ No valid KeyFigures for {layout_code}; skipping.")
                continue

            self.stdout.write(f"→ Generating for {layout_code} / {ply.year.code} / {ply.version.code}")

            # Scenario & first step
            try:
                scenario = PlanningScenario.objects.get(layout_year=ply)
            except PlanningScenario.DoesNotExist:
                self.stderr.write(f"⚠️ No scenario for {ply}; skipping.")
                continue
            first_step = ScenarioStep.objects.filter(scenario=scenario).order_by('order').first()

            for org in ply.org_units.all():
                # Build dimension‐combos
                if layout_code == 'RES_CON':
                    ios = list(InternalOrder.objects.filter(cc_code=org.code))
                    rc_combos = [(rc.resource_type, rc.skill, rc.level, rc.country)
                                 for rc in RateCard.objects.all()]
                    combos = [(io, rt, sk, lv, co) for io in ios for (rt,sk,lv,co) in rc_combos]
                    # sample down to at most 20 combos per org
                    if len(combos) > 20:
                        combos = random.sample(combos, 20)
                else:
                    vals = {d: get_dim_values(d) for d in dims}
                    combos = list(product(*(vals[d] for d in dims))) if dims else [()]

                sess, created = PlanningSession.objects.get_or_create(
                    scenario=scenario,
                    org_unit=org,
                    defaults={
                        'created_by':   admin,
                        'current_step': first_step,
                        'status':       PlanningSession.Status.DRAFT,
                    }
                )
                if created:
                    steps = list(ScenarioStep.objects.filter(scenario=scenario).order_by('order'))
                    chosen = random.choice(steps)
                    sess.current_step = chosen
                    sess.status = {
                        'DRAFT':    PlanningSession.Status.DRAFT,
                        'REVIEW':   PlanningSession.Status.REVIEW,
                        'FINALIZE': PlanningSession.Status.COMPLETED,
                    }.get(chosen.stage.code, PlanningSession.Status.DRAFT)
                    if sess.status == PlanningSession.Status.COMPLETED and random.random() < 0.2:
                        sess.freeze(admin)
                    sess.save(update_fields=['current_step','status','frozen_by','frozen_at'])

                desc = "Historical" if ply.version.code=='ACTUAL' else f"{ply.version.code} Update"
                dr, _ = DataRequest.objects.get_or_create(
                    session=sess,
                    description=desc,
                    defaults={
                        'created_by':  admin,
                        'action_type': 'OVERWRITE' if ply.version.code=='ACTUAL' else 'DELTA'
                    }
                )

                # Load existing facts into a map
                existing = {}
                qs = PlanningFact.objects.filter(session=sess, request=dr, version=ply.version)
                for f in qs.only('pk','period_id','org_unit_id','service_id','key_figure_id','extra_dimensions_json'):
                    key = (
                        f.period_id,
                        f.org_unit_id,
                        f.service_id,
                        f.key_figure_id,
                        frozenset(f.extra_dimensions_json.items())
                    )
                    existing[key] = f

                to_create, to_update = [], []

                for combo in combos:
                    # Build extra_dimensions_json (skip Service)
                    extra = {}
                    for dim, val in zip(dims, combo):
                        if dim == 'Service':
                            continue
                        extra[dim] = val.id if hasattr(val, 'id') else val

                    svc = None
                    if 'Service' in dims:
                        svc = combo[dims.index('Service')]

                    for per in periods:
                        for kf_code in kf_codes:
                            # Demo‐value
                            if kf_code in ('FTE','MAN_MONTH','LICENSE_VOLUME'):
                                val = Decimal(random.uniform(0.5,3.0)).quantize(Decimal('0.01'))
                            elif kf_code in ('COST','LICENSE_COST','ADMIN_OVERHEAD','TOTAL_COST'):
                                val = Decimal(random.uniform(1000,10000)).quantize(Decimal('0.01'))
                            elif kf_code == 'LICENSE_UNIT_PRICE':
                                val = Decimal(random.uniform(10,200)).quantize(Decimal('0.01'))
                            elif kf_code == 'UTIL':
                                val = Decimal(random.uniform(50,100)).quantize(Decimal('0.01'))
                            else:
                                val = Decimal(random.uniform(1,5)).quantize(Decimal('0.01'))

                            kf = kf_map[kf_code]
                            row_key = (
                                per.id,
                                org.id,
                                svc.id if svc else None,
                                kf.id,
                                frozenset(extra.items())
                            )

                            if row_key in existing:
                                inst = existing[row_key]
                                inst.value = val
                                to_update.append(inst)
                            else:
                                to_create.append(PlanningFact(
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
                                ))

                if to_create:
                    PlanningFact.objects.bulk_create(to_create, ignore_conflicts=True)
                    self.stdout.write(f"   ● Created {len(to_create):,} new facts")
                if to_update:
                    PlanningFact.objects.bulk_update(to_update, ['value'], batch_size=500)
                    self.stdout.write(f"   ● Updated {len(to_update):,} existing facts")

        self.stdout.write(self.style.SUCCESS("✅ Demo generation complete."))