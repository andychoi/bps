import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from bps.models.models import (
    UnitOfMeasure, ConversionRate,
    KeyFigure, Constant,
    Year, Version, Period, PeriodGrouping,
    OrgUnit, CBU, CostCenter, InternalOrder,
    Service, Position, RateCard,
    PlanningLayout, PlanningLayoutYear,
    PlanningSession, DataRequest, PlanningFact,
    Skill
)

User = get_user_model()
random.seed(42)

TEMPLATE_SERVICES = ['CRM','Warranty','DealerService','Inventory','Billing']
SOFT_IO_SUFFIX   = '_LIC'

class Command(BaseCommand):
    help = 'Generate demo IT cost planning data for all layouts'

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()

        # ─── 1. Master & Reference Data ──────────────────────────────────────────
        SKILLS = ['Developer','DevOps Engineer','Test Analyst','Security Analyst']
        SENIORITIES = ['Junior','Mid','Senior']

        skill_map = {}
        for s in SKILLS:
            obj, _ = Skill.objects.get_or_create(name=s)
            skill_map[s] = obj

        hrs, _ = UnitOfMeasure.objects.get_or_create(
            code='HRS', defaults={'name':'Hours','is_base':True}
        )
        usd, _ = UnitOfMeasure.objects.get_or_create(
            code='USD', defaults={'name':'US Dollar','is_base':False}
        )
        ea,  _ = UnitOfMeasure.objects.get_or_create(
            code='EA',  defaults={'name':'Each','is_base':False}
        )
        mm,  _ = UnitOfMeasure.objects.get_or_create(
            code='MAN_MONTH', defaults={'name':'Man-Month','is_base':False}
        )
        hc,  _ = UnitOfMeasure.objects.get_or_create(
            code='HC', defaults={'name':'Headcount','is_base':False}
        )

        ConversionRate.objects.get_or_create(
            from_uom=hrs, to_uom=mm,
            defaults={'factor': Decimal('1')/Decimal('168')}
        )
        ConversionRate.objects.get_or_create(
            from_uom=mm, to_uom=hc,
            defaults={'factor': Decimal('1')/Decimal('12')}
        )

        # Key Figures
        kf_defs = [
            ('FTE','Full Time Equivalent',False,hc),
            ('MAN_MONTH','Man-Months',False,mm),
            ('COST','Labor Cost',False,usd),
            ('LICENSE_VOLUME','License Volume',False,ea),
            ('LICENSE_UNIT_PRICE','License Unit Price',False,usd),
            ('LICENSE_COST','License Cost',False,usd),
            ('ADMIN_OVERHEAD','Admin Overhead',False,usd),
            ('TOTAL_COST','Total Service Cost',False,usd),
        ]
        for code,name,pct,uom in kf_defs:
            KeyFigure.objects.get_or_create(
                code=code,
                defaults={'name':name,'is_percent':pct,'default_uom':uom}
            )

        # Constants
        Constant.objects.get_or_create(
            name='INFLATION_RATE', defaults={'value': Decimal('0.03')}
        )
        Constant.objects.get_or_create(
            name='GROWTH_FACTOR', defaults={'value': Decimal('0.05')}
        )

        # ─── 2. Time & Version Dimensions ───────────────────────────────────────
        years = []
        for idx, y in enumerate([2025, 2026], start=1):
            obj, _ = Year.objects.get_or_create(
                code=str(y),
                defaults={'name': f'FY {y}', 'order': idx}
            )
            years.append(obj)

        actual_ver, _ = Version.objects.get_or_create(
            code='ACTUAL',
            defaults={'name':'Actuals','order':0}
        )
        for idx, (code, name) in enumerate(
            [('DRAFT','Draft'), ('PLAN V1','Realistic'), ('PLAN V2','Optimistic')],
            start=1
        ):
            Version.objects.get_or_create(
                code=code,
                defaults={'name':name,'order':idx,'created_by':admin}
            )

        periods = []
        for idx, m in enumerate(
            ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
            start=1
        ):
            obj, _ = Period.objects.get_or_create(
                code=f"{idx:02}",
                defaults={'name':m,'order':idx}
            )
            periods.append(obj)

        # ─── 3. OrgUnit Tree ──────────────────────────────────────────────────
        # Create Root if missing
        roots = OrgUnit.get_root_nodes()
        if roots:
            root = roots[0]
        else:
            root = OrgUnit.add_root(
                code='ROOT', name='Head Office', head_user=admin
            )

        # Divisions & Departments
        for d in range(1, 4):
            div_code = f'DIV{d}'
            if not OrgUnit.objects.filter(code=div_code).exists():
                div_node = root.add_child(
                    code=div_code, name=f'Division {d}', head_user=admin
                )
            else:
                div_node = OrgUnit.objects.get(code=div_code)

            for s in range(1, 4):
                dept_code = f'{div_code}_{s}'
                if not OrgUnit.objects.filter(code=dept_code).exists():
                    div_node.add_child(
                        code=dept_code, name=f'Dept {d}.{s}', head_user=admin
                    )

        # ─── 4. CBUs, Cost Centers & InternalOrders ──────────────────────────
        for tier in range(1, 4):
            CBU.objects.get_or_create(
                code=f'CBU{tier}',
                defaults={'name':f'CBU Tier {tier}','group':'Demo','tier':str(tier),'is_active':True}
            )

        # Dept-level CostCenters & InternalOrders
        for ou in OrgUnit.objects.exclude(code='ROOT'):
            CostCenter.objects.get_or_create(
                code=ou.code, defaults={'name':ou.name}
            )
            InternalOrder.objects.get_or_create(
                code=ou.code, defaults={'name':ou.name,'cc_code':ou.code}
            )
        # Software license buckets
        for svc in TEMPLATE_SERVICES:
            io_code = f'IO_{svc.upper()}{SOFT_IO_SUFFIX}'
            InternalOrder.objects.get_or_create(
                code=io_code,
                defaults={'name':f'{svc} License','cc_code':'ROOT'}
            )

        # ─── 5. Services ──────────────────────────────────────────────────────
        for cbu in CBU.objects.filter(is_active=True):
            for svc in TEMPLATE_SERVICES:
                Service.objects.get_or_create(
                    code=f'{cbu.code}_{svc.upper()}',
                    defaults={
                        'name':svc,
                        'category':random.choice(['Ops','Enhancements','Innovation']),
                        'subcategory':'Demo',
                        'criticality':'M',
                        'sla_response':timedelta(hours=2),
                        'sla_resolution':timedelta(hours=8),
                        'availability':Decimal('99.9'),
                        'support_hours':'9x5',
                        'orgunit':root,
                        'owner':admin,
                        'is_active':True
                    }
                )

        # ─── 6. Positions & RateCards ────────────────────────────────────────
        types = ['EMP','CON','MSP']
        countries = {'CON':['USA','India','Mexico'], 'MSP':['USA','India','Mexico']}
        for y in years:
            for skill in SKILLS:
                sk = skill_map[skill]
                for lvl in SENIORITIES:
                    open_flag = (y.code == '2025' and random.random() < 0.1)
                    code = f"{skill[:3].upper()}-{lvl}{'-OP' if open_flag else ''}"
                    Position.objects.get_or_create(
                        year=y, code=code,
                        defaults={
                            'name':f"{skill} {lvl}{' (Open)' if open_flag else ''}",
                            'skill':sk, 'level':lvl, 'fte':1.0, 'is_open':open_flag
                        }
                    )
            for skill in SKILLS:
                sk = skill_map[skill]
                for rtype in types:
                    for lvl in SENIORITIES:
                        ctrys = countries.get(rtype, ['USA'])
                        for country in ctrys:
                            RateCard.objects.get_or_create(
                                year=y, skill=sk, level=lvl,
                                resource_type=rtype, country=country,
                                defaults={
                                    'efficiency_factor':Decimal(random.uniform(0.7,1.0)).quantize(Decimal('0.01')),
                                    'hourly_rate':Decimal(random.uniform(20,120)).quantize(Decimal('0.01'))
                                }
                            )

        # ─── 7. Planning Layouts ─────────────────────────────────────────────
        layout_defs = [
            ('RES_FTE','Resource Planning - FTE'),
            ('RES_CON','Resource Planning - Contractors/MSP'),
            ('SYS_DEMAND','System Demand by Skill & Level'),
            ('RES_ALLOC','Resource Allocation to Systems'),
            ('SW_LICENSE','Software License Cost Planning'),
            ('ADMIN_OVH','Admin Overhead Allocation'),
            ('SRV_COST','Service Cost Summary'),
        ]
        layouts = {}
        for code,name in layout_defs:
            layouts[code], _ = PlanningLayout.objects.get_or_create(
                code=code, defaults={'name':name,'domain':'cost'}
            )

        # ─── 8. LayoutYears & Sessions ──────────────────────────────────────
        for layout in layouts.values():
            for y in years:
                for ver in Version.objects.all():
                    ply, _ = PlanningLayoutYear.objects.get_or_create(
                        layout=layout, year=y, version=ver
                    )
                    PeriodGrouping.objects.get_or_create(
                        layout_year=ply, months_per_bucket=1,
                        defaults={'label_prefix':''}
                    )
                    PeriodGrouping.objects.get_or_create(
                        layout_year=ply, months_per_bucket=3,
                        defaults={'label_prefix':'Q'}
                    )
                    ply.org_units.set(OrgUnit.objects.exclude(code='ROOT'))

        # ─── 9. Facts Generation ──────────────────────────────────────────────
        infl   = float(Constant.objects.get(name='INFLATION_RATE').value)
        growth = float(Constant.objects.get(name='GROWTH_FACTOR').value)

        for code, layout in layouts.items():
            for ply in PlanningLayoutYear.objects.filter(layout=layout):
                for org in ply.org_units.all():
                    sess, _ = PlanningSession.objects.get_or_create(
                        layout_year=ply, org_unit=org, defaults={'created_by':admin}
                    )
                    dr_desc = 'Historical 2025' if ply.version.code=='ACTUAL' else f'{ply.version.code} Update'
                    dr, _ = DataRequest.objects.get_or_create(
                        session=sess, description=dr_desc, defaults={'created_by':admin}
                    )

                    for per in periods:
                        # ── 1. RES_FTE ─────────────────────────
                        if code == 'RES_FTE':
                            for pos in Position.objects.filter(year=ply.year):
                                hc_val = Decimal(random.uniform(0.8,1.2)).quantize(Decimal('0.01'))
                                PlanningFact.objects.update_or_create(
                                    request=dr, session=sess,
                                    version=ply.version, year=ply.year, period=per,
                                    org_unit=org, service=None,
                                    dimension_values={'Position': pos.id},
                                    key_figure=KeyFigure.objects.get(code='FTE'),
                                    defaults={'value': hc_val, 'uom': hc}
                                )
                                PlanningFact.objects.update_or_create(
                                    request=dr, session=sess,
                                    version=ply.version, year=ply.year, period=per,
                                    org_unit=org, service=None,
                                    dimension_values={'Position': pos.id},
                                    key_figure=KeyFigure.objects.get(code='MAN_MONTH'),
                                    defaults={'value': hc_val, 'uom': mm}
                                )

                        # ── 2. RES_CON ─────────────────────────
                        elif code == 'RES_CON':
                            for io in InternalOrder.objects.exclude(code__endswith=SOFT_IO_SUFFIX):
                                for rtype in ['CON','MSP']:
                                    for skill in SKILLS:
                                        for lvl in SENIORITIES:
                                            mm_val = Decimal(random.uniform(0.5,3)).quantize(Decimal('0.01'))
                                            # cost: mm * random blended rate
                                            rate = Decimal(random.uniform(30,120)).quantize(Decimal('0.01'))
                                            cost_val = (mm_val * rate).quantize(Decimal('0.01'))
                                            dim = {
                                                'InternalOrder': io.id,
                                                'ResourceType': rtype,
                                                'Skill': skill,
                                                'Level': lvl
                                            }
                                            PlanningFact.objects.update_or_create(
                                                request=dr, session=sess,
                                                version=ply.version, year=ply.year, period=per,
                                                org_unit=org, service=None,
                                                dimension_values=dim,
                                                key_figure=KeyFigure.objects.get(code='MAN_MONTH'),
                                                defaults={'value': mm_val, 'uom': mm}
                                            )
                                            PlanningFact.objects.update_or_create(
                                                request=dr, session=sess,
                                                version=ply.version, year=ply.year, period=per,
                                                org_unit=org, service=None,
                                                dimension_values=dim,
                                                key_figure=KeyFigure.objects.get(code='COST'),
                                                defaults={'value': cost_val, 'uom': usd}
                                            )

                        # ── 3. SYS_DEMAND ───────────────────────
                        elif code == 'SYS_DEMAND':
                            for svc in Service.objects.filter(is_active=True):
                                for skill in SKILLS:
                                    for lvl in SENIORITIES:
                                        mm_val = Decimal(random.uniform(0,3)).quantize(Decimal('0.01'))
                                        PlanningFact.objects.update_or_create(
                                            request=dr, session=sess,
                                            version=ply.version, year=ply.year, period=per,
                                            org_unit=org, service=svc,
                                            dimension_values={'Skill': skill,'Level': lvl},
                                            key_figure=KeyFigure.objects.get(code='MAN_MONTH'),
                                            defaults={'value': mm_val, 'uom': mm}
                                        )

                        # ── 4. RES_ALLOC ───────────────────────
                        elif code == 'RES_ALLOC':
                            for pos in Position.objects.filter(year=ply.year):
                                # random split across 2 services
                                svcs = list(Service.objects.filter(is_active=True))
                                picks = random.sample(svcs, 2)
                                splits = [random.random() for _ in picks]
                                total = sum(splits)
                                for svc, frac in zip(picks, splits):
                                    alloc = Decimal(frac/total).quantize(Decimal('0.01'))
                                    mm_val = alloc  # assume 1 mm capacity per FTE
                                    PlanningFact.objects.update_or_create(
                                        request=dr, session=sess,
                                        version=ply.version, year=ply.year, period=per,
                                        org_unit=org, service=svc,
                                        dimension_values={'Position': pos.id},
                                        key_figure=KeyFigure.objects.get(code='MAN_MONTH'),
                                        defaults={'value': mm_val, 'uom': mm}
                                    )

                        # ── 5. SW_LICENSE ──────────────────────
                        elif code == 'SW_LICENSE':
                            for svc in Service.objects.filter(is_active=True):
                                for io in InternalOrder.objects.filter(code__endswith=SOFT_IO_SUFFIX):
                                    base_users = random.randint(50,200)
                                    unit_price = random.uniform(30,150)
                                    if ply.version.code=='ACTUAL' and ply.year.code==2025:
                                        users = base_users
                                        price = unit_price
                                    else:
                                        users = base_users*(1+growth)
                                        price = unit_price*(1+infl)
                                    PlanningFact.objects.update_or_create(
                                        request=dr, session=sess,
                                        version=ply.version, year=ply.year, period=per,
                                        org_unit=org, service=svc,
                                        dimension_values={'InternalOrder': io.id},
                                        key_figure=KeyFigure.objects.get(code='LICENSE_VOLUME'),
                                        defaults={'value': round(users,2), 'uom': ea}
                                    )
                                    PlanningFact.objects.update_or_create(
                                        request=dr, session=sess,
                                        version=ply.version, year=ply.year, period=per,
                                        org_unit=org, service=svc,
                                        dimension_values={'InternalOrder': io.id},
                                        key_figure=KeyFigure.objects.get(code='LICENSE_UNIT_PRICE'),
                                        defaults={'value': round(price,2), 'uom': usd}
                                    )
                                    PlanningFact.objects.update_or_create(
                                        request=dr, session=sess,
                                        version=ply.version, year=ply.year, period=per,
                                        org_unit=org, service=svc,
                                        dimension_values={'InternalOrder': io.id},
                                        key_figure=KeyFigure.objects.get(code='LICENSE_COST'),
                                        defaults={'value': round(users*price,2), 'uom': usd}
                                    )

                        # ── 6. ADMIN_OVH ───────────────────────
                        elif code == 'ADMIN_OVH':
                            # dept-level overhead
                            for dept in OrgUnit.objects.filter(parent__isnull=False):
                                cost_val = Decimal(random.uniform(1000,5000)).quantize(Decimal('0.01'))
                                PlanningFact.objects.update_or_create(
                                    request=dr, session=sess,
                                    version=ply.version, year=ply.year, period=per,
                                    org_unit=dept, service=None,
                                    dimension_values={},
                                    key_figure=KeyFigure.objects.get(code='ADMIN_OVERHEAD'),
                                    defaults={'value': cost_val, 'uom': usd}
                                )

                        # ── 7. SRV_COST ────────────────────────
                        elif code == 'SRV_COST':
                            for svc in Service.objects.filter(is_active=True):
                                labor   = Decimal(random.uniform(20000,50000)).quantize(Decimal('0.01'))
                                lic_c   = Decimal(random.uniform(2000,10000)).quantize(Decimal('0.01'))
                                ovhd    = Decimal(random.uniform(1000,5000)).quantize(Decimal('0.01'))
                                total   = labor + lic_c + ovhd
                                # labor
                                PlanningFact.objects.update_or_create(
                                    request=dr, session=sess,
                                    version=ply.version, year=ply.year, period=per,
                                    org_unit=org, service=svc,
                                    dimension_values={},
                                    key_figure=KeyFigure.objects.get(code='COST'),
                                    defaults={'value': labor, 'uom': usd}
                                )
                                # license cost
                                PlanningFact.objects.update_or_create(
                                    request=dr, session=sess,
                                    version=ply.version, year=ply.year, period=per,
                                    org_unit=org, service=svc,
                                    dimension_values={},
                                    key_figure=KeyFigure.objects.get(code='LICENSE_COST'),
                                    defaults={'value': lic_c, 'uom': usd}
                                )
                                # overhead
                                PlanningFact.objects.update_or_create(
                                    request=dr, session=sess,
                                    version=ply.version, year=ply.year, period=per,
                                    org_unit=org, service=svc,
                                    dimension_values={},
                                    key_figure=KeyFigure.objects.get(code='ADMIN_OVERHEAD'),
                                    defaults={'value': ovhd, 'uom': usd}
                                )
                                # total
                                PlanningFact.objects.update_or_create(
                                    request=dr, session=sess,
                                    version=ply.version, year=ply.year, period=per,
                                    org_unit=org, service=svc,
                                    dimension_values={},
                                    key_figure=KeyFigure.objects.get(code='TOTAL_COST'),
                                    defaults={'value': total, 'uom': usd}
                                )

        self.stdout.write(self.style.SUCCESS('✅ Comprehensive IT cost planning demo data generated.'))