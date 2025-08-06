# bps/management/commands/bps_demo_2env.py

import sys
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType

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
    PlanningKeyFigure,
    PlanningLayoutDimension,
    PlanningDimension,
)
from bps.models.models_dimension import OrgUnit, InternalOrder, Service
from bps.models.models_resource import Position, Skill

User = get_user_model()

# 1) The workflow stages, in order
STAGES = [
    ("DRAFT",    "Draft",     1, False),
    ("REVIEW",   "Review",    2, False),
    ("FINALIZE", "Finalize",  3, False),
]

# 2) Which layouts to create
LAYOUT_DEFS = [
    ("RES_FTE",    "Resource Planning – FTE"),
    ("RES_CON",    "Resource Planning – Contractors/MSP"),
    ("SYS_DEMAND", "System Demand by Skill & Level"),
    ("RES_ALLOC",  "Resource Allocation to Systems"),
    ("SW_LICENSE", "Software License Cost Planning"),
    ("ADMIN_OVH",  "Admin Overhead Allocation"),
    ("SRV_COST",   "Service Cost Summary"),
]

# 3) Which row-dimensions each layout uses
ROW_DIMS = {
    "RES_FTE":    ["Position", "Skill"],
    "RES_CON":    ["InternalOrder"],
    "SYS_DEMAND": ["Service", "Skill"],
    "RES_ALLOC":  ["Position", "Service"],
    "SW_LICENSE": ["Service", "InternalOrder"],
    "ADMIN_OVH":  ["OrgUnit", "Service"],
    "SRV_COST":   ["Service"],
}

# 4) Which key-figures each layout needs (code,label)
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
    help = "Step 2: Create Layouts, Dimensions, LayoutYears, Scenarios, etc."

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write("❌ no superuser found; aborting.")
            sys.exit(1)

        # ─── 1) Ensure all PlanningLayouts exist ──────────────────────────────────
        layouts = {}
        for code, name in LAYOUT_DEFS:
            obj, _ = PlanningLayout.objects.get_or_create(
                code=code,
                defaults={"name": name, "domain": "cost", "default": False},
            )
            layouts[code] = obj
        self.stdout.write(self.style.SUCCESS(f"✔️ {len(layouts)} PlanningLayout entries"))

        # ─── 2) Create the “global” PlanningDimension inline on each layout ──────
        for code, layout in layouts.items():
            PlanningDimension.objects.filter(layout=layout).delete()
            for idx, model_name in enumerate(ROW_DIMS[code], start=1):
                PlanningDimension.objects.create(
                    layout        = layout,
                    name          = model_name,
                    label         = model_name,
                    data_source   = model_name.lower(),
                    is_row        = True,
                    is_column     = False,
                    is_filter     = False,
                    is_navigable  = False,
                    is_editable   = False,
                    required      = True,
                    display_order = idx,
                )
        self.stdout.write(self.style.SUCCESS(
            f"✔️ Created PlanningDimension for {len(layouts)} layouts"
        ))

        # Prepare OrgUnit references for wiring up LayoutYears
        root    = OrgUnit.get_root_nodes().first()
        all_ous = OrgUnit.objects.exclude(pk=root.pk)

        # ─── 3) Create each PlanningLayoutYear + PeriodGroupings ────────────────
        years     = Year.objects.all()
        versions  = Version.objects.all()
        created_ly = 0

        for layout in layouts.values():
            for year in years:
                for version in versions:
                    ply, created = PlanningLayoutYear.objects.get_or_create(
                        layout=layout,
                        year=year,
                        version=version,
                    )
                    if created:
                        created_ly += 1

                    # assign all non‐root org units
                    ply.org_units.set(all_ous)

                    # monthly + quarterly groupings
                    monthly, _ = PeriodGrouping.objects.get_or_create(
                        layout_year=ply,
                        months_per_bucket=1,
                        defaults={"label_prefix": ""}
                    )
                    PeriodGrouping.objects.get_or_create(
                        layout_year=ply,
                        months_per_bucket=3,
                        defaults={"label_prefix":"Q"}
                    )

                    # default header dims JSON
                    ply.header_dims = {"period_grouping_id": monthly.pk}
                    ply.save(update_fields=["header_dims"])

        self.stdout.write(self.style.SUCCESS(
            f"✔️ Created/ensured {created_ly} PlanningLayoutYear + PeriodGroupings"
        ))

        # ─── 4) Define per‐layout KeyFigures & per‐year LayoutDimensions ─────────
        # first build a map of ContentType for each dimension name
        ct_map = {
            "Position":      ContentType.objects.get_for_model(Position),
            "Skill":         ContentType.objects.get_for_model(Skill),
            "InternalOrder": ContentType.objects.get_for_model(InternalOrder),
            "Service":       ContentType.objects.get_for_model(Service),
            "OrgUnit":       ContentType.objects.get_for_model(OrgUnit),
        }

        # 4a) Per-layout key figures
        for code, layout in layouts.items():
            for idx, (kf_code, kf_label) in enumerate(KF_DEFS[code], start=1):
                PlanningKeyFigure.objects.get_or_create(
                    layout=layout,
                    code=kf_code,
                    defaults={
                        "label":       kf_label,
                        "is_editable": True,
                        "is_computed": False,
                        "display_order": idx,
                    }
                )

        # 4b) Per‐year row dimensions and wire up the layout_year.row_dims M2M
        for ply in PlanningLayoutYear.objects.filter(layout__in=layouts.values()):
            # clear old
            PlanningLayoutDimension.objects.filter(layout_year=ply).delete()

            # build list of ContentType objects we’ll assign to row_dims
            ct_list = []
            for idx, model_name in enumerate(ROW_DIMS[ply.layout.code], start=1):
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
                ct_list.append(ct)

            # assign the M2M so your “Filtered lead columns” show up in the UI
            ply.row_dims.set(ct_list)

        self.stdout.write(self.style.SUCCESS(
            "✔️ LayoutDimensions & PlanningKeyFigures defined"
        ))

        # ─── 5) Create PlanningStage entries ─────────────────────────────────────
        stage_objs = []
        for code, name, order, parallel in STAGES:
            stg, _ = PlanningStage.objects.get_or_create(
                code=code,
                defaults={"name": name, "order": order, "can_run_in_parallel": parallel},
            )
            stage_objs.append(stg)
        self.stdout.write(self.style.SUCCESS(
            f"✔️ {len(stage_objs)} PlanningStage entries"
        ))

        # ─── 6) Create one PlanningScenario per LayoutYear ──────────────────────
        created_sc = 0
        for ply in PlanningLayoutYear.objects.prefetch_related("org_units").all():
            scode = f"{ply.layout.code}_{ply.year.code}_{ply.version.code}"
            sname = f"{ply.layout.name} {ply.year.code}/{ply.version.code}"

            # **Include layout_year in the lookup so it actually gets created**
            scenario, new = PlanningScenario.objects.get_or_create(
                code=scode,
                layout_year=ply,
                defaults={"name": sname, "is_active": True},
            )
            if new:
                created_sc += 1

            # wire up the org‐units (through ScenarioOrgUnit)
            for idx, ou in enumerate(ply.org_units.all(), start=1):
                ScenarioOrgUnit.objects.get_or_create(
                    scenario=scenario,
                    org_unit=ou,
                    defaults={"order": idx},
                )

            # wire up stages & steps
            for stg in stage_objs:
                ScenarioStage.objects.get_or_create(
                    scenario=scenario,
                    stage=stg,
                    defaults={"order": stg.order},
                )
                ScenarioStep.objects.get_or_create(
                    scenario=scenario,
                    stage=stg,
                    layout=ply.layout,
                    defaults={"order": stg.order},
                )

        self.stdout.write(self.style.SUCCESS(
            f"✅ Created/ensured {created_sc} PlanningScenario entries"
        ))