import sys
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from bps.models.models import PeriodGrouping, KeyFigure
from bps.models.models_dimension import OrgUnit, InternalOrder, Service, Year, Version
from bps.models.models_layout import (
    PlanningLayout,
    PlanningLayoutYear,
    PlanningLayoutDimension,   # template-level
    LayoutDimensionOverride,   # per-instance (kept for completeness; not used here)
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
    ("RES_FTE",   "Resource Planning – FTE"),
    ("RES_CON",   "Resource Planning – Contractors/MSP"),
    ("SYS_DEMAND","System Demand by Skill & Level"),
    ("RES_ALLOC", "Resource Allocation to Systems"),
    ("SW_LICENSE","Software License Cost Planning"),
    ("ADMIN_OVH", "Admin Overhead Allocation"),
    ("SRV_COST",  "Service Cost Summary"),
]

# Define desired roles (template-level)
ROW_DIMS = {
    "RES_FTE":    ["Position", "Skill"],
    "RES_CON":    ["InternalOrder", "Skill"],
    "SYS_DEMAND": ["Service", "Skill"],
    "RES_ALLOC":  ["Position", "Service"],
    "SW_LICENSE": ["Service", "InternalOrder"],
    "ADMIN_OVH":  ["OrgUnit", "Service"],
    "SRV_COST":   ["Service"],
}
HEADER_DIMS = {
    "RES_FTE":    ["OrgUnit"],
    "RES_CON":    ["OrgUnit"],
    "SYS_DEMAND": ["OrgUnit"],
    "RES_ALLOC":  ["OrgUnit"],
    "SW_LICENSE": ["OrgUnit"],
    "ADMIN_OVH":  ["OrgUnit"],
    "SRV_COST":   ["OrgUnit"],
}

KF_DEFS = {
    "RES_FTE":   ["FTE", "MAN_MONTH"],
    "RES_CON":   ["MAN_MONTH", "COST"],
    "SYS_DEMAND":["MAN_MONTH"],
    "RES_ALLOC": ["MAN_MONTH", "UTIL"],
    "SW_LICENSE":["LICENSE_VOLUME","LICENSE_UNIT_PRICE","LICENSE_COST"],
    "ADMIN_OVH": ["ADMIN_OVERHEAD"],
    "SRV_COST":  ["COST","LICENSE_COST","ADMIN_OVERHEAD","TOTAL_COST"],
}

class Command(BaseCommand):
    help = "Step 2: Create Layouts (template), Dimensions (row + headers) at template level, LayoutYears, Scenarios, etc."

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write("❌ no superuser found; aborting.")
            sys.exit(1)

        # 1) Layout templates
        layouts = {}
        for code, name in LAYOUT_DEFS:
            obj, _ = PlanningLayout.objects.get_or_create(
                code=code, defaults={"name": name, "domain": "cost", "default": False}
            )
            layouts[code] = obj
        self.stdout.write(self.style.SUCCESS(f"✔️ {len(layouts)} PlanningLayout entries"))

        # 2) Template-level dimensions
        ct_map = {
            "Position":      ContentType.objects.get_for_model(Position),
            "Skill":         ContentType.objects.get_for_model(Skill),
            "InternalOrder": ContentType.objects.get_for_model(InternalOrder),
            "Service":       ContentType.objects.get_for_model(Service),
            "OrgUnit":       ContentType.objects.get_for_model(OrgUnit),
        }

        for code, layout in layouts.items():
            # Rebuild the full set every time (idempotent)
            PlanningLayoutDimension.objects.filter(layout=layout).delete()

            # rows
            order = 1
            for name in ROW_DIMS.get(code, []):
                ct = ct_map[name]
                PlanningLayoutDimension.objects.create(
                    layout=layout,
                    content_type=ct,
                    is_row=True,
                    is_column=False,
                    is_header=False,
                    order=order,
                )
                order += 1

            # headers (org unit for all; appears distinct from row role)
            for name in HEADER_DIMS.get(code, []):
                ct = ct_map[name]
                # header order starts after rows
                PlanningLayoutDimension.objects.create(
                    layout=layout,
                    content_type=ct,
                    is_row=False,
                    is_column=False,
                    is_header=True,
                    order=order,
                )
                order += 1

        self.stdout.write(self.style.SUCCESS("✔️ Template-level PlanningLayoutDimension created"))

        # 3) Link KeyFigures to the layout template
        for code, layout in layouts.items():
            desired = KF_DEFS.get(code, [])
            PlanningKeyFigure.objects.filter(layout=layout).delete()
            for idx, kf_code in enumerate(desired, start=1):
                kf = KeyFigure.objects.filter(code=kf_code).first()
                if not kf:
                    self.stderr.write(f"⚠️ Missing KeyFigure {kf_code}; skipping for {code}")
                    continue
                PlanningKeyFigure.objects.create(
                    layout=layout,
                    key_figure=kf,
                    is_editable=True,
                    is_computed=False,
                    display_order=idx,
                )
        self.stdout.write(self.style.SUCCESS("✔️ PlanningKeyFigure linked to global KeyFigures"))

        # 4) Instances (per year/version) + org units + header defaults
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

                    # Period groupings
                    monthly, _ = PeriodGrouping.objects.get_or_create(
                        layout_year=ply, months_per_bucket=1, defaults={"label_prefix": ""}
                    )
                    PeriodGrouping.objects.get_or_create(
                        layout_year=ply, months_per_bucket=3, defaults={"label_prefix": "Q"}
                    )

                    # Header JSON: use template header dims (lowercase keys via ContentType.model)
                    header_json = dict(ply.header_dims or {})
                    header_json["period_grouping_id"] = monthly.pk
                    for dim in layout.dimensions.filter(is_header=True).select_related("content_type"):
                        header_json.setdefault(dim.content_type.model, None)
                    ply.header_dims = header_json
                    ply.save(update_fields=["header_dims"])

        self.stdout.write(
            self.style.SUCCESS(f"✔️ Created/ensured {created_ly} PlanningLayoutYear + PeriodGroupings")
        )

        # 5) Workflow scaffolding
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