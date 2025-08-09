import sys

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from bps.models.models import PeriodGrouping
from bps.models.models_dimension import OrgUnit, InternalOrder, Service, Year, Version
from bps.models.models_layout import (
    PlanningLayout,
    PlanningLayoutYear,
    PlanningDimension,
    PlanningLayoutDimension,
    PlanningKeyFigure,
)
from bps.models.models_resource import Position, Skill
from bps.models.models_workflow import (
    PlanningStage,
    PlanningScenario,
    ScenarioOrgUnit,
    ScenarioStage,
    ScenarioStep,
)


User = get_user_model()

STAGES = [
    ("DRAFT", "Draft", 1, False),
    ("REVIEW", "Review", 2, False),
    ("FINALIZE", "Finalize", 3, False),
]

LAYOUT_DEFS = [
    ("RES_FTE", "Resource Planning – FTE"),
    ("RES_CON", "Resource Planning – Contractors/MSP"),
    ("SYS_DEMAND", "System Demand by Skill & Level"),
    ("RES_ALLOC", "Resource Allocation to Systems"),
    ("SW_LICENSE", "Software License Cost Planning"),
    ("ADMIN_OVH", "Admin Overhead Allocation"),
    ("SRV_COST", "Service Cost Summary"),
]

# Only include real Django models in row dims.
ROW_DIMS = {
    "RES_FTE": ["Position", "Skill"],
    "RES_CON": ["InternalOrder", "Skill"],  # extra attributes (rtype/level/country) live in extra_dimensions_json
    "SYS_DEMAND": ["Service", "Skill"],
    "RES_ALLOC": ["Position", "Service"],
    "SW_LICENSE": ["Service", "InternalOrder"],
    "ADMIN_OVH": ["OrgUnit", "Service"],
    "SRV_COST": ["Service"],
}

KF_DEFS = {
    "RES_FTE": [("FTE", "Headcount"), ("MAN_MONTH", "Man-Months")],
    "RES_CON": [("MAN_MONTH", "Man-Months"), ("COST", "Labor Cost")],
    "SYS_DEMAND": [("MAN_MONTH", "Man-Months")],
    "RES_ALLOC": [("MAN_MONTH", "Man-Months"), ("UTIL", "% Utilization")],
    "SW_LICENSE": [
        ("LICENSE_VOLUME", "Driver Volume"),
        ("LICENSE_UNIT_PRICE", "Unit Price"),
        ("LICENSE_COST", "License Cost"),
    ],
    "ADMIN_OVH": [("ADMIN_OVERHEAD", "Admin Overhead")],
    "SRV_COST": [
        ("COST", "Labor Cost"),
        ("LICENSE_COST", "License Cost"),
        ("ADMIN_OVERHEAD", "Overhead"),
        ("TOTAL_COST", "Total Service Cost"),
    ],
}


class Command(BaseCommand):
    help = "Step 2: Create Layouts, Dimensions, LayoutYears, Scenarios, etc."

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write("❌ no superuser found; aborting.")
            sys.exit(1)

        # Layouts
        layouts = {}
        for code, name in LAYOUT_DEFS:
            obj, _ = PlanningLayout.objects.get_or_create(
                code=code, defaults={"name": name, "domain": "cost", "default": False}
            )
            layouts[code] = obj
        self.stdout.write(self.style.SUCCESS(f"✔️ {len(layouts)} PlanningLayout entries"))

        # PlanningDimensions (row/axis definitions)
        for code, layout in layouts.items():
            PlanningDimension.objects.filter(layout=layout).delete()
            for idx, model_name in enumerate(ROW_DIMS[code], start=1):
                PlanningDimension.objects.create(
                    layout=layout,
                    name=model_name,
                    label=model_name,
                    data_source=model_name.lower(),
                    is_row=True,
                    is_column=False,
                    is_filter=False,
                    is_navigable=False,
                    is_editable=False,
                    required=True,
                    display_order=idx,
                )
        self.stdout.write(self.style.SUCCESS("✔️ Created PlanningDimension for all layouts"))

        # LayoutYears for all (Year × Version)
        root = OrgUnit.get_root_nodes().first()
        all_ous = OrgUnit.objects.exclude(pk=root.pk) if root else OrgUnit.objects.all()
        years = Year.objects.all()
        versions = Version.objects.all()
        created_ly = 0

        for layout in layouts.values():
            for year in years:
                for version in versions:
                    ply, created = PlanningLayoutYear.objects.get_or_create(
                        layout=layout, year=year, version=version
                    )
                    if created:
                        created_ly += 1
                    ply.org_units.set(all_ous)

                    # period groupings
                    monthly, _ = PeriodGrouping.objects.get_or_create(
                        layout_year=ply, months_per_bucket=1, defaults={"label_prefix": ""}
                    )
                    PeriodGrouping.objects.get_or_create(
                        layout_year=ply, months_per_bucket=3, defaults={"label_prefix": "Q"}
                    )
                    ply.header_dims = {"period_grouping_id": monthly.pk}
                    ply.save(update_fields=["header_dims"])

        self.stdout.write(
            self.style.SUCCESS(f"✔️ Created/ensured {created_ly} PlanningLayoutYear + PeriodGroupings")
        )

        # Key Figures per layout
        for code, layout in layouts.items():
            for idx, (kf_code, kf_label) in enumerate(KF_DEFS[code], start=1):
                PlanningKeyFigure.objects.get_or_create(
                    layout=layout,
                    code=kf_code,
                    defaults={
                        "label": kf_label,
                        "is_editable": True,
                        "is_computed": False,
                        "display_order": idx,
                    },
                )

        # LayoutDimensions (ContentTypes for row dims)
        ct_map = {
            "Position": ContentType.objects.get_for_model(Position),
            "Skill": ContentType.objects.get_for_model(Skill),
            "InternalOrder": ContentType.objects.get_for_model(InternalOrder),
            "Service": ContentType.objects.get_for_model(Service),
            "OrgUnit": ContentType.objects.get_for_model(OrgUnit),
        }

        for ply in PlanningLayoutYear.objects.filter(layout__in=layouts.values()):
            PlanningLayoutDimension.objects.filter(layout_year=ply).delete()
            ct_list = []
            for idx, model_name in enumerate(ROW_DIMS[ply.layout.code], start=1):
                ct = ct_map.get(model_name)
                if not ct:
                    continue
                PlanningLayoutDimension.objects.create(
                    layout_year=ply, content_type=ct, is_row=True, is_column=False, order=idx
                )
                ct_list.append(ct)
            ply.row_dims.set(ct_list)

        self.stdout.write(self.style.SUCCESS("✔️ LayoutDimensions & PlanningKeyFigures defined"))

        # Workflow (Stages, Scenarios, Steps, OrgUnit membership)
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
            scenario, new = PlanningScenario.objects.get_or_create(
                code=scode, layout_year=ply, defaults={"name": sname, "is_active": True}
            )
            if new:
                created_sc += 1

            for idx, ou in enumerate(ply.org_units.all(), start=1):
                ScenarioOrgUnit.objects.get_or_create(
                    scenario=scenario, org_unit=ou, defaults={"order": idx}
                )

            for stg in stage_objs:
                ScenarioStage.objects.get_or_create(
                    scenario=scenario, stage=stg, defaults={"order": stg.order}
                )
                ScenarioStep.objects.get_or_create(
                    scenario=scenario, stage=stg, layout=ply.layout, defaults={"order": stg.order}
                )

        self.stdout.write(self.style.SUCCESS(f"✅ Created/ensured {created_sc} PlanningScenario entries"))