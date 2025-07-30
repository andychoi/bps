import sys
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType

from bps.models.models import (
    Year, Version,
    PlanningLayout, PlanningLayoutYear,
    PeriodGrouping,
    PlanningStage, PlanningScenario,
    ScenarioOrgUnit, ScenarioStage, ScenarioStep,
    PlanningKeyFigure, PlanningLayoutDimension,
)
from bps.models.models_dimension import OrgUnit, InternalOrder, Service
from bps.models.models_resource import Position, Skill
from bps.models.models import PlanningLayout  # ensure PlanningLayout is in scope

User = get_user_model()

STAGES = [
    ("DRAFT",    "Draft",     1, False),
    ("REVIEW",   "Review",    2, False),
    ("FINALIZE", "Finalize",  3, False),
]

LAYOUT_DEFS = [
    ("RES_FTE",    "Resource Planning – FTE"),
    ("RES_CON",    "Resource Planning – Contractors/MSP"),
    ("SYS_DEMAND", "System Demand by Skill & Level"),
    ("RES_ALLOC",  "Resource Allocation to Systems"),
    ("SW_LICENSE", "Software License Cost Planning"),
    ("ADMIN_OVH",  "Admin Overhead Allocation"),
    ("SRV_COST",   "Service Cost Summary"),
]

# which dimensions (by model name) go on each layout’s rows
ROW_DIMS = {
    "RES_FTE":    ["Position", "Skill"],
    "RES_CON":    ["InternalOrder"],
    "SYS_DEMAND": ["Service", "Skill"],
    "RES_ALLOC":  ["Position", "Service"],
    "SW_LICENSE": ["Service", "InternalOrder"],
    "ADMIN_OVH":  ["OrgUnit", "Service"],
    "SRV_COST":   ["Service"],
}

# KeyFigures for each layout
KF_DEFS = {
    "RES_FTE":    [("HC","Headcount"), ("MAN_MONTH","Man-Months")],
    "RES_CON":    [("MAN_MONTH","Man-Months"), ("COST","Labor Cost")],
    "SYS_DEMAND": [("MAN_MONTH","Man-Months")],
    "RES_ALLOC":  [("MAN_MONTH","Man-Months"), ("UTIL","% Utilization")],
    "SW_LICENSE": [
        ("LICENSE_VOLUME","Driver Volume"),
        ("LICENSE_UNIT_PRICE","Unit Price"),
        ("LICENSE_COST","License Cost"),
    ],
    "ADMIN_OVH":  [("ADMIN_OVERHEAD","Admin Overhead")],
    "SRV_COST":   [
        ("COST","Labor Cost"),
        ("LICENSE_COST","License Cost"),
        ("ADMIN_OVERHEAD","Overhead"),
        ("TOTAL_COST","Total Service Cost"),
    ],
}

class Command(BaseCommand):
    help = "Step 2: Create LayoutYears + PeriodGroupings + Scenarios + Dimensions + KeyFigures"

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write("❌ no superuser found; aborting.")
            sys.exit(1)

        # 1) ensure all PlanningLayouts exist
        layouts = {}
        for code, name in LAYOUT_DEFS:
            obj, _ = PlanningLayout.objects.get_or_create(
                code=code,
                defaults={"name": name, "domain": "cost", "default": False},
            )
            layouts[code] = obj
        self.stdout.write(self.style.SUCCESS(f"✔️ {len(layouts)} PlanningLayout entries"))

        # 2) create each LayoutYear + PeriodGroupings
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

                    # assign all non-root org units
                    ply.org_units.set(all_ous)

                    # default to monthly grouping
                    monthly, _ = PeriodGrouping.objects.get_or_create(
                        layout_year=ply,
                        months_per_bucket=1,
                        defaults={"label_prefix": ""}
                    )
                    # also ensure quarterly exists
                    PeriodGrouping.objects.get_or_create(
                        layout_year=ply,
                        months_per_bucket=3,
                        defaults={"label_prefix":"Q"}
                    )

                    # tell UI which grouping to render by default
                    ply.header_dims = {"period_grouping_id": monthly.pk}
                    ply.save(update_fields=["header_dims"])

        self.stdout.write(self.style.SUCCESS(
            f"✔️ Created/ensured {created_ly} PlanningLayoutYear + PeriodGroupings"
        ))

        # 3) define row dimensions & key figures on each layout
        ct_map = {
            "Position":      ContentType.objects.get_for_model(Position),
            "Skill":         ContentType.objects.get_for_model(Skill),
            "InternalOrder": ContentType.objects.get_for_model(InternalOrder),
            "Service":       ContentType.objects.get_for_model(Service),
            "OrgUnit":       ContentType.objects.get_for_model(OrgUnit),
        }

        for code, layout in layouts.items():
            # create PlanningKeyFigure entries
            for idx,(kf_code,kf_label) in enumerate(KF_DEFS[code], start=1):
                PlanningKeyFigure.objects.get_or_create(
                    layout=layout,
                    code=kf_code,
                    defaults={
                        "label": kf_label,
                        "is_editable": True,
                        "is_computed": False,
                    }
                )

            # attach dimensions to each LayoutYear
            for ply in PlanningLayoutYear.objects.filter(layout=layout):
                # clear existing dims
                PlanningLayoutDimension.objects.filter(layout_year=ply).delete()

                # add row dims in defined order
                for idx, model_name in enumerate(ROW_DIMS[code], start=1):
                    ct = ct_map.get(model_name)
                    if not ct:
                        continue
                    PlanningLayoutDimension.objects.create(
                        layout_year=ply,
                        content_type=ct,
                        is_row=True,
                        is_column=False,
                        order=idx,
                    )

        self.stdout.write(self.style.SUCCESS("✔️ LayoutDimensions & PlanningKeyFigures defined"))

        # 4) create planning stages & scenarios
        stage_objs = []
        for code, name, order, parallel in STAGES:
            stg, _ = PlanningStage.objects.get_or_create(
                code=code,
                defaults={"name": name, "order": order, "can_run_in_parallel": parallel},
            )
            stage_objs.append(stg)
        self.stdout.write(self.style.SUCCESS(f"✔️ {len(stage_objs)} PlanningStage entries"))

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

                # tie org units
                for idx, ou in enumerate(ply.org_units.all(), start=1):
                    ScenarioOrgUnit.objects.get_or_create(
                        scenario=scenario, org_unit=ou, defaults={"order": idx}
                    )

                # stages & steps
                for st in stage_objs:
                    ScenarioStage.objects.get_or_create(
                        scenario=scenario, stage=st, defaults={"order": st.order}
                    )
                    ScenarioStep.objects.get_or_create(
                        scenario=scenario,
                        stage=st,
                        layout=ply.layout,
                        defaults={"order": st.order},
                    )

        self.stdout.write(self.style.SUCCESS(
            f"✅ Created/ensured {created_sc} PlanningScenario entries"
        ))