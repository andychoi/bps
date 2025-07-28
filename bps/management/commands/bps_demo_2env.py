# bps/management/commands/bps_setup_environment.py
import sys
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from bps.models.models import (
    Year,
    Version,
    PlanningLayout,
    PlanningLayoutYear,
    PeriodGrouping,
    PlanningStage,
    PlanningScenario,
    ScenarioOrgUnit,
    ScenarioStage,
    ScenarioStep,
)
from bps.models.models_dimension import OrgUnit

User = get_user_model()

# 1) your three stages
STAGES = [
    ("DRAFT",    "Draft",     1, False),
    ("REVIEW",   "Review",    2, False),
    ("FINALIZE", "Finalize",  3, False),
]

# 2) your seven cost‐planning layouts
LAYOUT_DEFS = [
    ("RES_FTE",    "Resource Planning – FTE"),
    ("RES_CON",    "Resource Planning – Contractors/MSP"),
    ("SYS_DEMAND", "System Demand by Skill & Level"),
    ("RES_ALLOC",  "Resource Allocation to Systems"),
    ("SW_LICENSE", "Software License Cost Planning"),
    ("ADMIN_OVH",  "Admin Overhead Allocation"),
    ("SRV_COST",   "Service Cost Summary"),
]

class Command(BaseCommand):
    help = "Step 2: Create LayoutYears, PeriodGroupings, Stages, Scenarios & Steps"

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write("❌ no superuser found; aborting.")
            sys.exit(1)

        # 1) ensure core layouts exist
        layouts = {}
        for code, name in LAYOUT_DEFS:
            obj, created = PlanningLayout.objects.get_or_create(
                code=code,
                defaults={"name": name, "domain": "cost", "default": False},
            )
            layouts[code] = obj
        self.stdout.write(self.style.SUCCESS(f"✔️ {len(layouts)} PlanningLayout entries"))

        # 2) create the missing PlanningLayoutYear for every layout × year × version
        years    = Year.objects.all()
        versions = Version.objects.all()
        created_ly = 0
        root = OrgUnit.get_root_nodes().first()
        all_ous = OrgUnit.objects.exclude(pk=root.pk)

        for layout in layouts.values():
            for year in years:
                for version in versions:
                    ply, created = PlanningLayoutYear.objects.get_or_create(
                        layout=layout, year=year, version=version
                    )
                    if created:
                        created_ly += 1
                    # hook up all non‐root org units for planning
                    ply.org_units.set(all_ous)
                    # one‐month buckets + quarterly buckets
                    for months, prefix in ((1, ""), (3, "Q")):
                        PeriodGrouping.objects.get_or_create(
                            layout_year=ply,
                            months_per_bucket=months,
                            defaults={"label_prefix": prefix},
                        )

        self.stdout.write(self.style.SUCCESS(
            f"✔️ Created/ensured {created_ly} PlanningLayoutYear + PeriodGroupings"
        ))

        # 3) create your stages
        stage_objs = []
        for code, name, order, parallel in STAGES:
            stg, _ = PlanningStage.objects.get_or_create(
                code=code,
                defaults={"name": name, "order": order, "can_run_in_parallel": parallel},
            )
            stage_objs.append(stg)
        self.stdout.write(self.style.SUCCESS(f"✔️ {len(stage_objs)} PlanningStage entries"))

        # 4) create one scenario per combination of layout/year/version
        created_sc = 0
        for ply in PlanningLayoutYear.objects.prefetch_related("org_units").all():
            scode = f"{ply.layout.code}_{ply.year.code}_{ply.version.code}"
            sname = f"{ply.layout.name} {ply.year.code}/{ply.version.code}"
            with transaction.atomic():
                scenario, new = PlanningScenario.objects.get_or_create(
                    code=scode,
                    defaults={"name": sname, "layout_year": ply, "is_active": True},
                )
                if new:
                    created_sc += 1

                # assign each org unit to the scenario
                for idx, ou in enumerate(ply.org_units.all(), start=1):
                    ScenarioOrgUnit.objects.get_or_create(
                        scenario=scenario, org_unit=ou, defaults={"order": idx}
                    )

                # attach each stage in order
                for st in stage_objs:
                    ScenarioStage.objects.get_or_create(
                        scenario=scenario, stage=st, defaults={"order": st.order}
                    )

                # and finally, a step linking that stage + this layout
                for st in stage_objs:
                    ScenarioStep.objects.get_or_create(
                        scenario=scenario,
                        stage=st,
                        layout=ply.layout,
                        defaults={"order": st.order},
                    )

        self.stdout.write(self.style.SUCCESS(
            f"✅ Created/ensured {created_sc} PlanningScenario entries"
        ))