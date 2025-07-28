# bps/management/commands/bps_demo_3plan.py

import random
from decimal import Decimal

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

User = get_user_model()
random.seed(42)


class Command(BaseCommand):
    help = (
        "Step 3: Populate each session with demo DataRequest + PlanningFact rows. "
        "Use --year to restrict to a particular Year.code (e.g. 2026)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--year', '-y',
            dest='year_code',
            help="Only generate for LayoutYears whose Year.code matches this (e.g. '2026')",
        )

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write("❌ No superuser found; aborting.")
            return

        year_code = options.get('year_code')

        # load constants
        try:
            infl_rate  = float(Constant.objects.get(name="INFLATION_RATE").value)
            growth_fac = float(Constant.objects.get(name="GROWTH_FACTOR").value)
        except Constant.DoesNotExist:
            self.stderr.write("❌ Missing INFLATION_RATE or GROWTH_FACTOR; run master load first.")
            return

        # load key figures
        try:
            fte_kf  = KeyFigure.objects.get(code="FTE")
            cost_kf = KeyFigure.objects.get(code="COST")
        except KeyFigure.DoesNotExist:
            self.stderr.write("❌ Missing FTE or COST KeyFigure; run master load first.")
            return

        total_rows = 0

        # 12 standard periods
        periods = Period.objects.order_by("order")

        # base queryset of LayoutYears
        layout_years = (
            PlanningLayoutYear.objects
            .select_related('year', 'version')
            .prefetch_related('org_units')
        )
        if year_code:
            layout_years = layout_years.filter(year__code=year_code)

        for ply in layout_years:
            self.stdout.write(f"→ {ply.layout.code} / {ply.year.code} / {ply.version.code}")

            # find the scenario for this LayoutYear
            try:
                scenario = PlanningScenario.objects.get(layout_year=ply)
            except PlanningScenario.DoesNotExist:
                self.stderr.write(f"⚠️ No scenario for {ply}; skipping.")
                continue

            # pick the very first step as the default
            initial_step = (
                ScenarioStep.objects
                .filter(scenario=scenario)
                .order_by('order')
                .first()
            )
            if not initial_step:
                self.stderr.write(f"⚠️ No steps defined for scenario {scenario.code}; skipping.")
                continue

            for org in ply.org_units.all():
                # ensure session has a current_step
                sess, created = PlanningSession.objects.get_or_create(
                    scenario   = scenario,
                    org_unit   = org,
                    defaults   = {
                        'created_by':  admin,
                        'current_step': initial_step,
                    }
                )

                # 1️⃣ Historical / version update facts
                for ly2 in (
                    PlanningLayoutYear.objects
                    .filter(layout=ply.layout, year=ply.year)
                    .select_related('version')
                ):
                    ver  = ly2.version
                    desc = "Historical 2025" if ver.code=="ACTUAL" else f"{ver.code} Update"
                    dr, _ = DataRequest.objects.get_or_create(
                        session     = sess,
                        description = desc,
                        defaults    = {
                            'created_by': admin,
                            'action_type': 'OVERWRITE' if ver.code=='ACTUAL' else 'DELTA'
                        }
                    )

                    for per in periods:
                        fte_val  = Decimal(random.uniform(0.5,1.5)).quantize(Decimal("0.01"))
                        cost_val = (fte_val * Decimal("10000")).quantize(Decimal("0.01"))

                        _, c1 = PlanningFact.objects.update_or_create(
                            request          = dr,
                            session          = sess,
                            version          = ver,
                            year             = ply.year,
                            period           = per,
                            org_unit         = org,
                            service          = None,
                            dimension_values = {},
                            key_figure       = fte_kf,
                            defaults         = {
                                'value': fte_val,
                                'uom':   fte_kf.default_uom
                            }
                        )
                        _, c2 = PlanningFact.objects.update_or_create(
                            request          = dr,
                            session          = sess,
                            version          = ver,
                            year             = ply.year,
                            period           = per,
                            org_unit         = org,
                            service          = None,
                            dimension_values = {},
                            key_figure       = cost_kf,
                            defaults         = {
                                'value': cost_val,
                                'uom':   cost_kf.default_uom
                            }
                        )
                        total_rows += (1 if c1 else 0) + (1 if c2 else 0)

                # 2️⃣ Growth Adjustment (planning-only)
                with transaction.atomic():
                    dr_growth, _ = DataRequest.objects.get_or_create(
                        session     = sess,
                        description = "Growth Adjustment",
                        defaults    = {'created_by': admin, 'action_type': 'DELTA'}
                    )
                    for per in periods:
                        actual = PlanningFact.objects.filter(
                            session        = sess,
                            version__code  = "ACTUAL",
                            year           = ply.year,
                            period         = per,
                            org_unit       = org,
                            key_figure     = fte_kf
                        ).first()
                        base = actual.value if actual else Decimal("0")
                        new  = (base * Decimal(1 + growth_fac)).quantize(Decimal("0.01"))

                        _, c = PlanningFact.objects.update_or_create(
                            request          = dr_growth,
                            session          = sess,
                            version          = ply.version,
                            year             = ply.year,
                            period           = per,
                            org_unit         = org,
                            service          = None,
                            dimension_values = {},
                            key_figure       = fte_kf,
                            defaults         = {
                                'value': new,
                                'uom':   fte_kf.default_uom
                            }
                        )
                        total_rows += 1 if c else 0

                # 3️⃣ Inflation Adjustment (planning-only)
                with transaction.atomic():
                    dr_infl, _ = DataRequest.objects.get_or_create(
                        session     = sess,
                        description = "Inflation Adjustment",
                        defaults    = {'created_by': admin, 'action_type': 'DISTRIBUTE'}
                    )
                    for per in periods:
                        last_cost = (
                            PlanningFact.objects
                            .filter(
                                session        = sess,
                                version__code  = ply.version.code,
                                year           = ply.year,
                                period         = per,
                                org_unit       = org,
                                key_figure     = cost_kf
                            )
                            .order_by('-request__created_at')
                            .first()
                        )
                        base = last_cost.value if last_cost else Decimal("0")
                        new  = (base * Decimal(1 + infl_rate)).quantize(Decimal("0.01"))

                        _, c = PlanningFact.objects.update_or_create(
                            request          = dr_infl,
                            session          = sess,
                            version          = ply.version,
                            year             = ply.year,
                            period           = per,
                            org_unit         = org,
                            service          = None,
                            dimension_values = {},
                            key_figure       = cost_kf,
                            defaults         = {
                                'value': new,
                                'uom':   cost_kf.default_uom
                            }
                        )
                        total_rows += 1 if c else 0

        self.stdout.write(self.style.SUCCESS(
            f"✅ Demo facts generated: {total_rows} rows"
        ))