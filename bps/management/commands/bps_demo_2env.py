# management/commands/bps_demo_2env.py
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
    "RES_CON": ["InternalOrder", "Skill"],  # extra attributes live in extra_dimensions_json
    "SYS_DEMAND": ["Service", "Skill"],
    "RES_ALLOC": ["Position", "Service"],
    "SW_LICENSE": ["Service", "InternalOrder"],
    "ADMIN_OVH": ["OrgUnit", "Service"],
    "SRV_COST": ["Service"],
}

# NEW: which dimensions should behave like BW-BPS "header selections" (per layout)
# You can tweak per layout if you want Service, Position, etc. as headers too.
HEADER_DIMS = {
    "RES_FTE":    ["OrgUnit"],
    "RES_CON":    ["OrgUnit"],
    "SYS_DEMAND": ["OrgUnit"],
    "RES_ALLOC":  ["OrgUnit"],
    "SW_LICENSE": ["OrgUnit"],
    "ADMIN_OVH":  ["OrgUnit"],  # also present in ROW_DIMS; UI will hide the row column if header is set
    "SRV_COST":   ["OrgUnit"],
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
    help = "Step 2: Create Layouts, Dimensions (row + headers), LayoutYears, Scenarios, etc."

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

                    # seed header_dims JSON with period_grouping and empty header selections
                    header_json = dict(ply.header_dims or {})
                    header_json["period_grouping_id"] = monthly.pk
                    for hdr_name in HEADER_DIMS.get(layout.code, []):
                        header_json.setdefault(hdr_name, None)  # let Admin choose later
                    ply.header_dims = header_json
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

        # ContentTypes
        ct_map = {
            "Position": ContentType.objects.get_for_model(Position),
            "Skill": ContentType.objects.get_for_model(Skill),
            "InternalOrder": ContentType.objects.get_for_model(InternalOrder),
            "Service": ContentType.objects.get_for_model(Service),
            "OrgUnit": ContentType.objects.get_for_model(OrgUnit),
        }

        # LayoutDimensions (row dims + header dims with is_header flag)
        for ply in PlanningLayoutYear.objects.filter(layout__in=layouts.values()):
            PlanningLayoutDimension.objects.filter(layout_year=ply).delete()

            # Row dims
            row_cts = []
            for idx, model_name in enumerate(ROW_DIMS[ply.layout.code], start=1):
                ct = ct_map.get(model_name)
                if not ct:
                    continue
                # Keep is_row=True; is_header may also be True if this same model is a header
                pld, _ = PlanningLayoutDimension.objects.get_or_create(
                    layout_year=ply,
                    content_type=ct,
                    defaults={
                        "is_row": True,
                        "is_column": False,
                        "is_header": False,
                        "order": idx,
                    },
                )
                # Make sure flags/order are set (idempotent)
                pld.is_row = True
                pld.is_column = False
                pld.order = idx
                pld.save(update_fields=["is_row", "is_column", "order"])
                row_cts.append(ct)

            # Header dims
            # If a header dim is ALSO a row dim, we simply flip its is_header=True (UI hides it from grid)
            hdr_names = HEADER_DIMS.get(ply.layout.code, [])
            hdr_start_order = len(row_cts) + 1  # put headers after rows for deterministic ordering
            for hidx, model_name in enumerate(hdr_names, start=hdr_start_order):
                ct = ct_map.get(model_name)
                if not ct:
                    continue
                pld, _ = PlanningLayoutDimension.objects.get_or_create(
                    layout_year=ply,
                    content_type=ct,
                    defaults={
                        "is_row": model_name in ROW_DIMS.get(ply.layout.code, []),
                        "is_column": False,
                        "is_header": True,
                        "order": hidx,
                    },
                )
                # ensure header flag is set even if the record existed as a pure row-dim previously
                changed = False
                if not pld.is_header:
                    pld.is_header = True
                    changed = True
                # keep is_row as True if it is a declared row dimension; otherwise False
                should_row = model_name in ROW_DIMS.get(ply.layout.code, [])
                if pld.is_row != should_row:
                    pld.is_row = should_row
                    changed = True
                if pld.order != hidx:
                    pld.order = hidx
                    changed = True
                if changed:
                    pld.save(update_fields=["is_header", "is_row", "order"])

            # maintain the ManyToMany "row_dims" on the LayoutYear (row dims only)
            ply.row_dims.set(row_cts)

        self.stdout.write(self.style.SUCCESS("✔️ LayoutDimensions (rows + headers) & PlanningKeyFigures defined"))

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