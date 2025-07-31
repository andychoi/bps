import random
from decimal import Decimal
from itertools import product

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from bps.models.models import (
    PlanningLayoutYear, PlanningScenario, PlanningSession,
    DataRequest, PlanningFact, KeyFigure, Constant, Period
)
from bps.models.models_workflow import ScenarioStep
from bps.models.models_dimension import OrgUnit, InternalOrder
from bps.models.models_resource import Position, Skill, RateCard
from bps.models.models import Service

User = get_user_model()
random.seed(42)

# ─── Your row‐dimension definition for each layout ────────────────────────────────
ROW_DIMS = {
    'RES_FTE':    ['Position','Skill'],
    'RES_CON':    ['InternalOrder','ResourceType','Skill','Level','Country'],
    'SYS_DEMAND': ['Service','Skill'],
    'RES_ALLOC':  ['Position','Service'],
    'SW_LICENSE': ['Service','InternalOrder'],
    'ADMIN_OVH':  ['OrgUnit','Service'],
    'SRV_COST':   ['Service'],
}

# ─── Which KeyFigures to generate for each layout ─────────────────────────────────
# Note: use 'FTE' instead of 'HC' — this matches your master data load.
KF_DEFS = {
    'RES_FTE':    ['FTE','MAN_MONTH'],
    'RES_CON':    ['MAN_MONTH','COST'],
    'SYS_DEMAND': ['MAN_MONTH'],
    'RES_ALLOC':  ['MAN_MONTH','UTIL'],                # UTIL may be missing; we'll warn & skip if so
    'SW_LICENSE': ['LICENSE_VOLUME','LICENSE_UNIT_PRICE','LICENSE_COST'],
    'ADMIN_OVH':  ['ADMIN_OVERHEAD'],
    'SRV_COST':   ['COST','LICENSE_COST','ADMIN_OVERHEAD','TOTAL_COST'],
}

def get_dim_values(dim_name):
    """Return a list of possible values for a given dimension name."""
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
    help = "Step 3: Populate each session with demo PlanningFact rows (all layouts)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--year','-y',
            dest='year_code',
            help="Only generate for LayoutYears whose Year.code matches this (e.g. '2026')"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write("❌ No superuser found; aborting.")
            return

        # ensure constants exist (we don't actually use their values here)
        for cn in ('INFLATION_RATE','GROWTH_FACTOR'):
            if not Constant.objects.filter(name=cn).exists():
                self.stderr.write(f"❌ Missing constant {cn}; run master load first.")
                return

        # cache all KeyFigures up front
        all_needed_kfs = {kf for codes in KF_DEFS.values() for kf in codes}
        kf_qs = KeyFigure.objects.filter(code__in=all_needed_kfs).select_related('default_uom')
        kf_map = {kf.code: kf for kf in kf_qs}

        # warn about any missing codes (but do NOT abort)
        missing = all_needed_kfs - set(kf_map.keys())
        if missing:
            self.stderr.write(f"⚠️ KeyFigure(s) not found, will skip: {', '.join(sorted(missing))}")

        periods = list(Period.objects.order_by('order'))

        # pick up all LayoutYears (filtered by --year if given)
        lys = PlanningLayoutYear.objects.select_related('layout','year','version')\
                                         .prefetch_related('org_units')
        if options.get('year_code'):
            lys = lys.filter(year__code=options['year_code'])

        total_new = 0
        total_updated = 0

        for ply in lys:
            layout_code = ply.layout.code
            dims        = ROW_DIMS.get(layout_code, [])
            raw_kfs     = KF_DEFS.get(layout_code, [])
            # filter to only those KeyFigures we actually have
            kf_codes    = [c for c in raw_kfs if c in kf_map]
            if not kf_codes:
                self.stdout.write(f"→ No valid KeyFigures for {layout_code}; skipping.")
                continue

            self.stdout.write(f"→ Generating for {layout_code} / {ply.year.code} / {ply.version.code}")

            # find the scenario & its first step
            try:
                scenario = PlanningScenario.objects.get(layout_year=ply)
            except PlanningScenario.DoesNotExist:
                self.stderr.write(f"⚠️ No scenario for {ply}; skipping.")
                continue
            first_step = ScenarioStep.objects.filter(scenario=scenario).order_by('order').first()

            # prepare dimension‐value lists & cartesian product
            dim_values = {d: get_dim_values(d) for d in dims}
            combos = list(product(*(dim_values[d] for d in dims))) if dims else [()]

            for org in ply.org_units.all():
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
                    # randomly advance status
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

                # one DataRequest per version
                desc = "Historical" if ply.version.code=='ACTUAL' else f"{ply.version.code} Update"
                dr, _ = DataRequest.objects.get_or_create(
                    session=sess,
                    description=desc,
                    defaults={
                        'created_by':  admin,
                        'action_type': 'OVERWRITE' if ply.version.code=='ACTUAL' else 'DELTA'
                    }
                )

                # fetch existing row‐keys so we can update rather than duplicate
                existing = {
                    (
                        f.period_id,
                        f.org_unit_id,
                        f.service_id,
                        f.key_figure_id,
                        frozenset(f.extra_dimensions_json.items())
                    )
                    for f in PlanningFact.objects.filter(
                        session=sess, request=dr, version=ply.version
                    ).only('period_id','org_unit_id','service_id','key_figure_id','extra_dimensions_json')
                }

                to_create = []
                to_update = []

                for combo in combos:
                    dim_map = {
                        dim: (val.id if hasattr(val,'id') else val)
                        for dim,val in zip(dims, combo)
                    }
                    svc = None
                    if 'Service' in dims:
                        svc = combo[dims.index('Service')]

                    for per in periods:
                        for kf_code in kf_codes:
                            # demo‐value logic
                            if kf_code in ('FTE','MAN_MONTH','LICENSE_VOLUME'):
                                val = Decimal(random.uniform(0.5,3.0)).quantize(Decimal('0.01'))
                            elif kf_code in ('COST','LICENSE_COST','ADMIN_OVERHEAD','TOTAL_COST'):
                                val = Decimal(random.uniform(1000,10000)).quantize(Decimal('0.01'))
                            elif kf_code=='LICENSE_UNIT_PRICE':
                                val = Decimal(random.uniform(10,200)).quantize(Decimal('0.01'))
                            elif kf_code=='UTIL':
                                val = Decimal(random.uniform(50,100)).quantize(Decimal('0.01'))
                            else:
                                val = Decimal(random.uniform(1,5)).quantize(Decimal('0.01'))

                            kf = kf_map[kf_code]
                            row_key = (
                                per.id,
                                org.id,
                                svc.id if svc else None,
                                kf.id,
                                frozenset(dim_map.items())
                            )

                            fact = PlanningFact(
                                request          = dr,
                                session          = sess,
                                version          = ply.version,
                                year             = ply.year,
                                period           = per,
                                org_unit         = org,
                                service          = svc,
                                account          = None,
                                extra_dimensions_json = dim_map,
                                key_figure       = kf,
                                value            = val,
                                uom              = kf.default_uom,
                            )

                            if row_key in existing:
                                to_update.append(fact)
                            else:
                                to_create.append(fact)

                if to_create:
                    PlanningFact.objects.bulk_create(to_create, ignore_conflicts=True)
                    total_new = len(to_create)
                    self.stdout.write(f"   ● Created {total_new} new facts")
                if to_update:
                    PlanningFact.objects.bulk_update(to_update, ['value'], batch_size=500)
                    total_updated = len(to_update)
                    self.stdout.write(f"   ● Updated {total_updated} existing facts")

        self.stdout.write(self.style.SUCCESS("✅ Demo generation complete."))