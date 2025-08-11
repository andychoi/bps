# Python Project Summary: management

---

### `commands/bps_demo_0clean.py`
```python
from django.apps import apps
from django.db import connection
class Command(BaseCommand):
    help = "Clean up all BPS demo data in correct dependency order (with fast truncate for PlanningFact)"
    def handle(self, *args, **options):
        self.stdout.write("→ Truncating PlanningFact via raw SQL…")
        with connection.cursor() as cursor:
            cursor.execute('TRUNCATE TABLE "bps_planningfact" CASCADE;')
        self.stdout.write(self.style.SUCCESS("   ● PlanningFact truncated"))
        to_delete = [
            ("bps", "DataRequestLog"),
            ("bps", "PlanningFactDimension"),
            ("bps", "DataRequest"),
            ("bps", "PlanningSession"),
            ("bps", "FormulaRunEntry"),
            ("bps", "FormulaRun"),
            ("bps", "ScenarioFunction"),
            ("bps", "ScenarioStep"),
            ("bps", "ScenarioStage"),
            ("bps", "ScenarioOrgUnit"),
            ("bps", "PlanningScenario"),
            ("bps", "PlanningStage"),
            ("bps", "PeriodGrouping"),
            ("bps", "PlanningLayoutDimension"),
            ("bps", "PlanningKeyFigure"),
            ("bps", "PlanningDimension"),
            ("bps", "PlanningLayoutYear"),
            ("bps", "PlanningLayout"),
            ("bps", "PlanningFunction"),
            ("bps", "Formula"),
            ("bps", "SubFormula"),
            ("bps", "ReferenceData"),
            ("bps", "RateCard"),
            ("bps", "Position"),
            ("bps", "Employee"),
            ("bps", "Contractor"),
            ("bps", "MSPStaff"),
            ("bps", "Resource"),
            ("bps", "Skill"),
            ("bps", "Service"),
            ("bps", "InternalOrder"),
            ("bps", "CostCenter"),
            ("bps", "CBU"),
            ("bps", "OrgUnit"),
            ("bps", "ConversionRate"),
            ("bps", "UnitOfMeasure"),
            ("bps", "KeyFigure"),
            ("bps", "GlobalVariable"),
            ("bps", "Constant"),
            ("bps", "Period"),
            ("bps", "Version"),
            ("bps", "Year"),
        ]
        for app_label, model_name in to_delete:
            try:
                Model = apps.get_model(app_label, model_name)
            except LookupError:
                self.stderr.write(f"Skipping missing model {app_label}.{model_name}")
                continue
            count, _ = Model.objects.all().delete()
            self.stdout.write(f"→ deleted {count} rows from {app_label}.{model_name}")
        self.stdout.write(self.style.SUCCESS("✅ All BPS demo data cleaned up."))
```

### `commands/bps_demo_1master.py`
```python
import random
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from bps.models.models import UnitOfMeasure, ConversionRate, KeyFigure, Constant, Period
from bps.models.models_dimension import (
    Year,
    Version,
    CBU,
    CostCenter,
    InternalOrder,
    Service,
    OrgUnit,
)
from bps.models.models_resource import Position, RateCard, Skill
User = get_user_model()
random.seed(42)
TEMPLATE_SERVICES = ["CRM", "Warranty", "DealerService", "Inventory", "Billing"]
SKILLS = ["Developer", "DevOps Engineer", "Test Analyst", "Security Analyst"]
SENIORITIES = ["Junior", "Mid", "Senior"]
COUNTRIES = {
    "EMP": ["USA"],
    "CON": ["USA", "India", "Mexico"],
    "MSP": ["USA", "India", "Mexico"],
}
class Command(BaseCommand):
    help = "Step 1: Load all master/reference data for cost-planning"
    @transaction.atomic
    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write("❌ No superuser found; aborting.")
            return
        hrs, _ = UnitOfMeasure.objects.get_or_create(
            code="HRS", defaults={"name": "Hours", "is_base": True}
        )
        manm, _ = UnitOfMeasure.objects.get_or_create(
            code="MAN_MONTH", defaults={"name": "Man-Month", "is_base": False}
        )
        hc, _ = UnitOfMeasure.objects.get_or_create(
            code="HC", defaults={"name": "Headcount", "is_base": False}
        )
        usd, _ = UnitOfMeasure.objects.get_or_create(
            code="USD", defaults={"name": "US Dollar", "is_base": False}
        )
        ea, _ = UnitOfMeasure.objects.get_or_create(
            code="EA", defaults={"name": "Each", "is_base": False}
        )
        ConversionRate.objects.get_or_create(
            from_uom=hrs,
            to_uom=manm,
            defaults={"factor": Decimal("1") / Decimal("168")},
        )
        ConversionRate.objects.get_or_create(
            from_uom=manm,
            to_uom=hc,
            defaults={"factor": Decimal("1") / Decimal("12")},
        )
        self.stdout.write(self.style.SUCCESS("✔️ UOMs & ConversionRates"))
        kf_defs = [
            ("FTE", "Full Time Equivalent", False, hc),
            ("MAN_MONTH", "Man-Months", False, manm),
            ("COST", "Labor Cost", False, usd),
            ("LICENSE_VOLUME", "License Volume", False, ea),
            ("LICENSE_UNIT_PRICE", "License Unit Price", False, usd),
            ("LICENSE_COST", "License Cost", False, usd),
            ("ADMIN_OVERHEAD", "Admin Overhead", False, usd),
            ("TOTAL_COST", "Total Service Cost", False, usd),
            ("UTIL", "Utilization %", True, None),
        ]
        for code, name, pct, uom in kf_defs:
            KeyFigure.objects.get_or_create(
                code=code,
                defaults={"name": name, "is_percent": pct, "default_uom": uom},
            )
        self.stdout.write(self.style.SUCCESS("✔️ KeyFigures"))
        Constant.objects.get_or_create(
            name="INFLATION_RATE", defaults={"value": Decimal("0.03")}
        )
        Constant.objects.get_or_create(
            name="GROWTH_FACTOR", defaults={"value": Decimal("0.05")}
        )
        self.stdout.write(self.style.SUCCESS("✔️ Constants"))
        years = []
        for idx, y in enumerate([2025, 2026], start=1):
            obj, _ = Year.objects.get_or_create(
                code=str(y), defaults={"name": f"FY {y}", "order": idx}
            )
            years.append(obj)
        actual_ver, _ = Version.objects.get_or_create(
            code="ACTUAL",
            defaults={"name": "Actuals", "order": 0, "created_by": admin},
        )
        for idx, (code, name) in enumerate(
            [("DRAFT", "Draft"), ("PLAN V1", "Realistic"), ("PLAN V2", "Optimistic")],
            start=1,
        ):
            Version.objects.get_or_create(
                code=code, defaults={"name": name, "order": idx, "created_by": admin}
            )
        for idx, mon in enumerate(
            ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
            start=1,
        ):
            Period.objects.get_or_create(
                code=f"{idx:02}", defaults={"name": mon, "order": idx}
            )
        self.stdout.write(self.style.SUCCESS("✔️ Years, Versions & Periods"))
        root = OrgUnit.get_root_nodes().first()
        if not root:
            root = OrgUnit.add_root(code="ROOT", name="Head Office", head_user=admin)
        if not OrgUnit.objects.filter(code="CORP_ADMIN").exists():
            root.add_child(code="CORP_ADMIN", name="Corporate Admin", head_user=admin)
        for div in range(1, 3 + 1):
            div_code = f"DIV{div}"
            div_node = root.get_children().filter(code=div_code).first()
            if not div_node:
                div_node = root.add_child(code=div_code, name=f"Division {div}", head_user=admin)
            for dept in range(1, 3 + 1):
                dept_code = f"{div_code}_{dept}"
                if not OrgUnit.objects.filter(code=dept_code).exists():
                    div_node.add_child(code=dept_code, name=f"Dept {div}.{dept}", head_user=admin)
        self.stdout.write(self.style.SUCCESS("✔️ OrgUnit tree"))
        for tier in range(1, 3 + 1):
            CBU.objects.get_or_create(
                code=f"CBU{tier}",
                defaults={"name": f"CBU Tier {tier}", "group": "Demo", "tier": str(tier), "is_active": True},
            )
        for ou in OrgUnit.objects.exclude(code="ROOT"):
            cc, _ = CostCenter.objects.get_or_create(code=ou.code, defaults={"name": ou.name})
            target_ios = random.randint(2, 4)
            created = 0
            attempts = 0
            while created < target_ios and attempts < 50:
                attempts += 1
                io_code = f"IO{random.randint(1000, 9999)}"
                io, was_created = InternalOrder.objects.get_or_create(
                    code=io_code,
                    defaults={
                        "name": f"{ou.name} {io_code}",
                        "cc_code": cc.code,
                    },
                )
                if was_created:
                    created += 1
        self.stdout.write(self.style.SUCCESS("✔️ CBUs, CostCenters & InternalOrders"))
        for cbu in CBU.objects.filter(is_active=True):
            for svc in TEMPLATE_SERVICES:
                Service.objects.get_or_create(
                    code=f"{cbu.code}_{svc.upper()}",
                    defaults={
                        "name": svc,
                        "category": random.choice(["Ops", "Enhancements", "Innovation"]),
                        "subcategory": "Demo",
                        "orgunit": root,
                        "is_active": True,
                    },
                )
        self.stdout.write(self.style.SUCCESS("✔️ Services"))
        for year in years:
            for skill in SKILLS:
                sk_obj, _ = Skill.objects.get_or_create(name=skill)
                for lvl in SENIORITIES:
                    Position.objects.get_or_create(
                        year=year,
                        code=f"{skill[:3].upper()}-{lvl}",
                        defaults={
                            "name": f"{skill} {lvl}",
                            "skill": sk_obj,
                            "level": lvl,
                            "fte": 1.0,
                            "is_open": False,
                        },
                    )
            for rtype in ["EMP", "CON", "MSP"]:
                for skill in SKILLS:
                    sk_obj = Skill.objects.get(name=skill)
                    for lvl in SENIORITIES:
                        for country in COUNTRIES[rtype]:
                            RateCard.objects.get_or_create(
                                year=year,
                                skill=sk_obj,
                                level=lvl,
                                resource_type=rtype,
                                country=country,
                                defaults={
                                    "efficiency_factor": Decimal(random.uniform(0.7, 1.0)).quantize(
                                        Decimal("0.01")
                                    ),
                                    "hourly_rate": Decimal(random.uniform(20, 120)).quantize(Decimal("0.01")),
                                },
                            )
        self.stdout.write(self.style.SUCCESS("✔️ Positions & RateCards"))
        self.stdout.write(self.style.SUCCESS("✅ Master data loaded."))
```

### `commands/bps_demo_2env.py`
```python
import sys
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
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
ROW_DIMS = {
    "RES_FTE": ["Position", "Skill"],
    "RES_CON": ["InternalOrder", "Skill"],
    "SYS_DEMAND": ["Service", "Skill"],
    "RES_ALLOC": ["Position", "Service"],
    "SW_LICENSE": ["Service", "InternalOrder"],
    "ADMIN_OVH": ["OrgUnit", "Service"],
    "SRV_COST": ["Service"],
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
        layouts = {}
        for code, name in LAYOUT_DEFS:
            obj, _ = PlanningLayout.objects.get_or_create(
                code=code, defaults={"name": name, "domain": "cost", "default": False}
            )
            layouts[code] = obj
        self.stdout.write(self.style.SUCCESS(f"✔️ {len(layouts)} PlanningLayout entries"))
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
                    monthly, _ = PeriodGrouping.objects.get_or_create(
                        layout_year=ply, months_per_bucket=1, defaults={"label_prefix": ""}
                    )
                    PeriodGrouping.objects.get_or_create(
                        layout_year=ply, months_per_bucket=3, defaults={"label_prefix": "Q"}
                    )
                    header_json = dict(ply.header_dims or {})
                    header_json["period_grouping_id"] = monthly.pk
                    for hdr_name in HEADER_DIMS.get(layout.code, []):
                        header_json.setdefault(hdr_name, None)
                    ply.header_dims = header_json
                    ply.save(update_fields=["header_dims"])
        self.stdout.write(
            self.style.SUCCESS(f"✔️ Created/ensured {created_ly} PlanningLayoutYear + PeriodGroupings")
        )
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
        ct_map = {
            "Position": ContentType.objects.get_for_model(Position),
            "Skill": ContentType.objects.get_for_model(Skill),
            "InternalOrder": ContentType.objects.get_for_model(InternalOrder),
            "Service": ContentType.objects.get_for_model(Service),
            "OrgUnit": ContentType.objects.get_for_model(OrgUnit),
        }
        for ply in PlanningLayoutYear.objects.filter(layout__in=layouts.values()):
            PlanningLayoutDimension.objects.filter(layout_year=ply).delete()
            row_cts = []
            for idx, model_name in enumerate(ROW_DIMS[ply.layout.code], start=1):
                ct = ct_map.get(model_name)
                if not ct:
                    continue
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
                pld.is_row = True
                pld.is_column = False
                pld.order = idx
                pld.save(update_fields=["is_row", "is_column", "order"])
                row_cts.append(ct)
            hdr_names = HEADER_DIMS.get(ply.layout.code, [])
            hdr_start_order = len(row_cts) + 1
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
                changed = False
                if not pld.is_header:
                    pld.is_header = True
                    changed = True
                should_row = model_name in ROW_DIMS.get(ply.layout.code, [])
                if pld.is_row != should_row:
                    pld.is_row = should_row
                    changed = True
                if pld.order != hidx:
                    pld.order = hidx
                    changed = True
                if changed:
                    pld.save(update_fields=["is_header", "is_row", "order"])
            ply.row_dims.set(row_cts)
        self.stdout.write(self.style.SUCCESS("✔️ LayoutDimensions (rows + headers) & PlanningKeyFigures defined"))
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
```

### `commands/bps_demo_3plan.py`
```python
import random
from decimal import Decimal
from itertools import product
from django.contrib.auth import get_user_model
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
ROW_DIMS = {
    "RES_FTE": ["Position", "Skill"],
    "RES_CON": ["InternalOrder", "ResourceType", "Skill", "Level", "Country"],
    "SYS_DEMAND": ["Service", "Skill"],
    "RES_ALLOC": ["Position", "Service"],
    "SW_LICENSE": ["Service", "InternalOrder"],
    "ADMIN_OVH": ["OrgUnit", "Service"],
    "SRV_COST": ["Service"],
}
KF_DEFS = {
    "RES_FTE": ["FTE", "MAN_MONTH"],
    "RES_CON": ["MAN_MONTH", "COST"],
    "SYS_DEMAND": ["MAN_MONTH"],
    "RES_ALLOC": ["MAN_MONTH", "UTIL"],
    "SW_LICENSE": ["LICENSE_VOLUME", "LICENSE_UNIT_PRICE", "LICENSE_COST"],
    "ADMIN_OVH": ["ADMIN_OVERHEAD"],
    "SRV_COST": ["COST", "LICENSE_COST", "ADMIN_OVERHEAD", "TOTAL_COST"],
}
def get_dim_values(dim_name):
    if dim_name == "Position":
        return list(Position.objects.all())
    if dim_name == "InternalOrder":
        return list(InternalOrder.objects.all())
    if dim_name == "Service":
        return list(Service.objects.filter(is_active=True))
    if dim_name == "OrgUnit":
        return list(OrgUnit.objects.exclude(code="ROOT"))
    if dim_name == "Skill":
        return list(Skill.objects.all())
    if dim_name == "ResourceType":
        return [choice[0] for choice in RateCard.RESOURCE_CHOICES]
    if dim_name == "Level":
        return sorted({rc.level for rc in RateCard.objects.all()})
    if dim_name == "Country":
        return sorted({rc.country for rc in RateCard.objects.all()})
    raise ValueError(f"Unknown dimension: {dim_name}")
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
        for name in ("INFLATION_RATE", "GROWTH_FACTOR"):
            if not Constant.objects.filter(name=name).exists():
                self.stderr.write(f"❌ Missing constant {name}; run master load first.")
                return
        needed_kfs = {kf for codes in KF_DEFS.values() for kf in codes}
        kf_qs = KeyFigure.objects.filter(code__in=needed_kfs).select_related("default_uom")
        kf_map = {kf.code: kf for kf in kf_qs}
        missing = needed_kfs - set(kf_map)
        if missing:
            self.stderr.write(f"⚠️ Missing KeyFigures (will skip): {', '.join(sorted(missing))}")
        periods = list(Period.objects.order_by("order"))
        lys = (
            PlanningLayoutYear.objects.select_related("layout", "year", "version").prefetch_related("org_units")
        )
        if options.get("year_code"):
            lys = lys.filter(year__code=options["year_code"])
        for ply in lys:
            layout_code = ply.layout.code
            dims = ROW_DIMS.get(layout_code, [])
            raw_kfs = KF_DEFS.get(layout_code, [])
            kf_codes = [c for c in raw_kfs if c in kf_map]
            if not kf_codes:
                self.stdout.write(f"→ No valid KeyFigures for {layout_code}; skipping.")
                continue
            self.stdout.write(
                f"→ Generating for {layout_code} / {ply.year.code} / {ply.version.code}"
            )
            try:
                scenario = PlanningScenario.objects.get(layout_year=ply)
            except PlanningScenario.DoesNotExist:
                self.stderr.write(f"⚠️ No scenario for {ply}; skipping.")
                continue
            first_step = ScenarioStep.objects.filter(scenario=scenario).order_by("order").first()
            for org in ply.org_units.all():
                if layout_code == "RES_CON":
                    ios = list(InternalOrder.objects.filter(cc_code=org.code))
                    rc_combos = [
                        (rc.resource_type, rc.skill, rc.level, rc.country)
                        for rc in RateCard.objects.all()
                    ]
                    combos = [(io, rt, sk, lv, co) for io in ios for (rt, sk, lv, co) in rc_combos]
                    if len(combos) > 20:
                        combos = random.sample(combos, 20)
                else:
                    vals = {d: get_dim_values(d) for d in dims}
                    combos = list(product(*(vals[d] for d in dims))) if dims else [()]
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
                    extra = {}
                    for dim, val in zip(dims, combo):
                        if dim == "Service":
                            continue
                        extra[dim] = getattr(val, "id", val)
                    svc = None
                    if "Service" in dims:
                        svc = combo[dims.index("Service")]
                    for per in periods:
                        for kf_code in kf_codes:
                            if kf_code in ("FTE", "MAN_MONTH", "LICENSE_VOLUME"):
                                val = Decimal(random.uniform(0.5, 3.0)).quantize(Decimal("0.01"))
                            elif kf_code in ("COST", "LICENSE_COST", "ADMIN_OVERHEAD", "TOTAL_COST"):
                                val = Decimal(random.uniform(1000, 10000)).quantize(Decimal("0.01"))
                            elif kf_code == "LICENSE_UNIT_PRICE":
                                val = Decimal(random.uniform(10, 200)).quantize(Decimal("0.01"))
                            elif kf_code == "UTIL":
                                val = Decimal(random.uniform(50, 100)).quantize(Decimal("0.01"))
                            else:
                                val = Decimal(random.uniform(1, 5)).quantize(Decimal("0.01"))
                            kf = kf_map[kf_code]
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
```

### `commands/bps_init.py`
```python
from bps.models import UnitOfMeasure, ConversionRate, Year, Version, Period, KeyFigure, SLAProfile
from datetime import timedelta
class Command(BaseCommand):
    help = 'Loads initial reference data for BPS app'
    def handle(self, *args, **options):
        hrs, _ = UnitOfMeasure.objects.get_or_create(code='HRS', name='Hours', is_base=True)
        usd, _ = UnitOfMeasure.objects.get_or_create(code='USD', name='US Dollar', is_base=False)
        ConversionRate.objects.get_or_create(from_uom=hrs, to_uom=usd, factor=100)
        for y in range(2024, 2027):
            Year.objects.get_or_create(code=str(y), name=f'Fiscal Year {y}', order=y - 2020)
        for i, v in enumerate(['Draft', 'Final', 'Plan v1', 'Plan v2']):
            Version.objects.get_or_create(code=v.upper(), name=v, order=i)
        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        for i, name in enumerate(months, 1):
            Period.objects.get_or_create(code=f"{i:02}", name=name, order=i)
        kfs = [
            ('FTE', 'Full-Time Equivalent', False, hrs),
            ('COST', 'Total Cost', False, usd),
            ('UTIL', 'Utilization %', True, None),
        ]
        for code, name, is_percent, uom in kfs:
            KeyFigure.objects.get_or_create(code=code, name=name, is_percent=is_percent, default_uom=uom)
        SLAProfile.objects.get_or_create(
            name='Standard SLA',
            response_time=timedelta(hours=2),
            resolution_time=timedelta(hours=8),
            availability=99.9,
            defaults={'description': 'Default SLA for Tier-2 services'}
        )
        self.stdout.write(self.style.SUCCESS('Initial BPS data loaded.'))
```

