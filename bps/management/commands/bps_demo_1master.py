# bps/management/commands/bps_load_master_data.py

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from bps.models.models import (
    UnitOfMeasure,
    ConversionRate,
    KeyFigure,
    Constant,
    Year,
    Version,
    Period,
    CBU,
    CostCenter,
    InternalOrder,
    Service,
    Position,
    RateCard,
    Skill,
)
from bps.models.models_dimension import OrgUnit

User = get_user_model()
random.seed(42)

TEMPLATE_SERVICES = ['CRM','Warranty','DealerService','Inventory','Billing']
SKILLS           = ['Developer','DevOps Engineer','Test Analyst','Security Analyst']
SENIORITIES      = ['Junior','Mid','Senior']
COUNTRIES        = {
    'EMP': ['USA'],
    'CON': ['USA','India','Mexico'],
    'MSP': ['USA','India','Mexico'],
}

class Command(BaseCommand):
    help = 'Step 1: Load all master/reference data for cost-planning'

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write("❌ No superuser found; aborting.")
            return

        with transaction.atomic():
            # ── Units of Measure & ConversionRates ─────────────────────────
            hrs, _ = UnitOfMeasure.objects.get_or_create(
                code='HRS', defaults={'name':'Hours','is_base':True}
            )
            manm, _ = UnitOfMeasure.objects.get_or_create(
                code='MAN_MONTH', defaults={'name':'Man-Month','is_base':False}
            )
            hc, _  = UnitOfMeasure.objects.get_or_create(
                code='HC', defaults={'name':'Headcount','is_base':False}
            )
            usd, _ = UnitOfMeasure.objects.get_or_create(
                code='USD', defaults={'name':'US Dollar','is_base':False}
            )
            ea, _  = UnitOfMeasure.objects.get_or_create(
                code='EA', defaults={'name':'Each','is_base':False}
            )

            ConversionRate.objects.get_or_create(
                from_uom=hrs, to_uom=manm,
                defaults={'factor': Decimal('1')/Decimal('168')}
            )
            ConversionRate.objects.get_or_create(
                from_uom=manm, to_uom=hc,
                defaults={'factor': Decimal('1')/Decimal('12')}
            )
            self.stdout.write(self.style.SUCCESS("✔️ UOMs & ConversionRates"))

            # ── Key Figures ────────────────────────────────────────────────
            kf_defs = [
                ('FTE','Full Time Equivalent', False, hc),
                ('MAN_MONTH','Man-Months',        False, manm),
                ('COST','Labor Cost',             False, usd),
                ('LICENSE_VOLUME','License Volume',      False, ea),
                ('LICENSE_UNIT_PRICE','License Unit Price', False, usd),
                ('LICENSE_COST','License Cost',   False, usd),
                ('ADMIN_OVERHEAD','Admin Overhead', False, usd),
                ('TOTAL_COST','Total Service Cost', False, usd),
            ]
            for code,name,pct,uom in kf_defs:
                KeyFigure.objects.get_or_create(
                    code=code,
                    defaults={
                        'name':name,
                        'is_percent':pct,
                        'default_uom':uom
                    }
                )
            self.stdout.write(self.style.SUCCESS("✔️ KeyFigures"))

            # ── Constants ──────────────────────────────────────────────────
            Constant.objects.get_or_create(
                name='INFLATION_RATE', defaults={'value': Decimal('0.03')}
            )
            Constant.objects.get_or_create(
                name='GROWTH_FACTOR', defaults={'value': Decimal('0.05')}
            )
            self.stdout.write(self.style.SUCCESS("✔️ Constants"))

            # ── Time & Version Dimensions ──────────────────────────────────
            years = []
            for idx,y in enumerate([2025,2026], start=1):
                obj,_ = Year.objects.get_or_create(
                    code=str(y),
                    defaults={'name':f'FY {y}','order':idx}
                )
                years.append(obj)

            actual_ver,_ = Version.objects.get_or_create(
                code='ACTUAL',
                defaults={'name':'Actuals','order':0,'created_by':admin}
            )
            for idx,(code,name) in enumerate(
                [('DRAFT','Draft'),('PLAN V1','Realistic'),('PLAN V2','Optimistic')],
                start=1
            ):
                Version.objects.get_or_create(
                    code=code,
                    defaults={'name':name,'order':idx,'created_by':admin}
                )

            for idx,mon in enumerate(
                ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
                start=1
            ):
                Period.objects.get_or_create(
                    code=f"{idx:02}",
                    defaults={'name':mon,'order':idx}
                )
            self.stdout.write(self.style.SUCCESS("✔️ Years, Versions & Periods"))

            # ── OrgUnit Tree ───────────────────────────────────────────────
            roots = OrgUnit.get_root_nodes()
            if roots:
                root = roots[0]
            else:
                root = OrgUnit.add_root(
                    code='ROOT', name='Head Office', head_user=admin
                )

            # Corporate Admin under ROOT
            if not OrgUnit.objects.filter(code='CORP_ADMIN').exists():
                root.add_child(
                    code='CORP_ADMIN', name='Corporate Admin', head_user=admin
                )

            for div in range(1,4):
                div_code = f'DIV{div}'
                div_node = root.get_children().filter(code=div_code).first()
                if not div_node:
                    div_node = root.add_child(
                        code=div_code, name=f'Division {div}', head_user=admin
                    )
                for dept in range(1,4):
                    dept_code = f'{div_code}_{dept}'
                    if not OrgUnit.objects.filter(code=dept_code).exists():
                        div_node.add_child(
                            code=dept_code,
                            name=f'Dept {div}.{dept}',
                            head_user=admin
                        )
            self.stdout.write(self.style.SUCCESS("✔️ OrgUnit tree"))

            # ── CBUs, CostCenters & InternalOrders ─────────────────────────
            for tier in range(1,4):
                CBU.objects.get_or_create(
                    code=f'CBU{tier}',
                    defaults={
                        'name':f'CBU Tier {tier}',
                        'group':'Demo',
                        'tier':str(tier),
                        'is_active':True
                    }
                )
            for ou in OrgUnit.objects.exclude(code='ROOT'):
                CostCenter.objects.get_or_create(
                    code=ou.code,
                    defaults={'name':ou.name}
                )
                InternalOrder.objects.get_or_create(
                    code=ou.code,
                    defaults={'name':ou.name,'cc_code':ou.code}
                )
            self.stdout.write(self.style.SUCCESS("✔️ CBUs, CostCenters & InternalOrders"))

            # ── Services ───────────────────────────────────────────────────
            roots = OrgUnit.get_root_nodes()
            root = roots[0]
            for cbu in CBU.objects.filter(is_active=True):
                for svc in TEMPLATE_SERVICES:
                    Service.objects.get_or_create(
                        code=f'{cbu.code}_{svc.upper()}',
                        defaults={
                            'name':svc,
                            'category':random.choice(['Ops','Enhancements','Innovation']),
                            'subcategory':'Demo',
                            'orgunit':root,
                            'is_active':True
                        }
                    )
            self.stdout.write(self.style.SUCCESS("✔️ Services"))

            # ── Positions & RateCards ───────────────────────────────────────
            for year in years:
                for skill in SKILLS:
                    sk_obj,_ = Skill.objects.get_or_create(name=skill)
                    for lvl in SENIORITIES:
                        Position.objects.get_or_create(
                            year=year,
                            code=f"{skill[:3].upper()}-{lvl}",
                            defaults={
                                'name':f"{skill} {lvl}",
                                'skill':sk_obj,
                                'level':lvl,
                                'fte':1.0,
                                'is_open':False
                            }
                        )

                for rtype in ['EMP','CON','MSP']:
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
                                        'efficiency_factor':Decimal(random.uniform(0.7,1.0)).quantize(Decimal('0.01')),
                                        'hourly_rate':Decimal(random.uniform(20,120)).quantize(Decimal('0.01'))
                                    }
                                )
            self.stdout.write(self.style.SUCCESS("✔️ Positions & RateCards"))

        self.stdout.write(self.style.SUCCESS("✅ Master data loaded."))