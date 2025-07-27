import random
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from bps.models import (
    UnitOfMeasure, ConversionRate,
    Year, Version, Period,
    OrgUnit, Service, CostCenter,
    Skill, PeriodGrouping, 
    InternalOrder, CBU, SLAProfile,
    KeyFigure, PlanningLayout, PlanningLayoutYear,
    PlanningSession, DataRequest, PlanningFact,
    Position, RateCard,
    ReferenceData, Constant, SubFormula,
    Formula, PlanningFunction, FormulaRun
)

User = get_user_model()
random.seed(42)

SKILLS = [
    'Manager', 'Project Manager', 'Business Analyst', 'BSA',
    'Enterprise Architect', 'Solution Architect',
    'Developer', 'Data Engineer', 'QA Engineer', 'Test Analyst',
    'System Administrator', 'DevOps Engineer', 'Security Analyst'
]
SENIORITY_LEVELS = ['Junior', 'Mid', 'Senior']
SCENARIOS = {'Optimistic': 'PLAN V2', 'Realistic': 'PLAN V1', 'Pessimistic': 'DRAFT'}
SERVICE_TYPES = {
    'Run':    {'category': 'Ops', 'subcategory': 'BAU'},
    'Change': {'category': 'Enhancements', 'subcategory': 'Upgrades'},
    'Grow':   {'category': 'Innovation', 'subcategory': 'New Dev'},
}
OUTSOURCING_COUNTRIES = ['USA', 'India', 'Poland']

class Command(BaseCommand):
    help = 'Generate demo data: historical & planning facts, resources, costs, and formulas'

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()

        # 0. Seed Skill lookup map
        skill_map = {}
        for name in SKILLS:
            obj, _ = Skill.objects.get_or_create(name=name)
            skill_map[name] = obj

        # 1. UOM & conversions
        hrs, _ = UnitOfMeasure.objects.get_or_create(code='HRS', defaults={'name':'Hours','is_base':True})
        usd, _ = UnitOfMeasure.objects.get_or_create(code='USD', defaults={'name':'US Dollar','is_base':False})
        ea,  _ = UnitOfMeasure.objects.get_or_create(code='EA',  defaults={'name':'Each','is_base':False})
        ConversionRate.objects.get_or_create(from_uom=hrs,to_uom=usd,defaults={'factor':Decimal('100.00')})

        # 2. Years, Versions, Periods
        years = []
        for idx,y in enumerate([2024,2025,2026],1):
            obj,_ = Year.objects.get_or_create(code=str(y),defaults={'name':f'FY {y}','order':idx})
            years.append(obj)
        # actual version for historicals
        actual_ver, _ = Version.objects.get_or_create(code='ACTUAL', defaults={'name':'Actuals','order':0})
        # planning versions
        for idx,(code,name) in enumerate([('DRAFT','Draft'),('PLAN V1','Realistic'),('PLAN V2','Optimistic')],1):
            Version.objects.get_or_create(code=code,defaults={'name':name,'order':idx})
        for i,m in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],1):
            Period.objects.get_or_create(code=f"{i:02}",defaults={'name':m,'order':i})

        # ReferenceData entry for 2024 Actuals
        ref_actuals, _ = ReferenceData.objects.get_or_create(
            name='2024 Actuals', source_version=actual_ver,
            source_year=Year.objects.get(code='2024'),
            defaults={'description':'Historical actuals for 2024'}
        )

        # 3. OrgUnits & CBUs
        roots = OrgUnit.get_root_nodes()
        root  = roots[0] if roots else OrgUnit.add_root(code='ROOT',name='Head Office',head_user=admin)
        for i in range(1,4):
            code=f'DIV{i}'
            if not OrgUnit.objects.filter(code=code).exists():
                root.add_child(code=code,name=f'Division {i}',head_user=admin)
        for tier in ['1','2','3']:
            CBU.objects.get_or_create(code=f'CBU{tier}',defaults={'name':f'CBU Tier {tier}','tier':tier,'group':'Demo','is_active':True})

        # 4. Services
        services=[]
        for name,cfg in SERVICE_TYPES.items():
            svc,_=Service.objects.get_or_create(
                code=name[:3].upper(),
                defaults={
                    'name':name,'category':cfg['category'],'subcategory':cfg['subcategory'],
                    'criticality':'M','sla_response':timedelta(hours=2),
                    'sla_resolution':timedelta(hours=8),'availability':Decimal('99.9'),
                    'support_hours':'9x5','orgunit':root,'owner':admin,'is_active':True
                }
            )
            services.append(svc)
        shared_service=services[0]; setattr(shared_service,'is_shared',True); shared_service.save()

        # 5. Positions per year
        for y in years:
            for sg in SKILLS:
                skill_obj = skill_map[sg]
                for lvl in SENIORITY_LEVELS:
                    for open_flag in (False,True):
                        suffix=lvl[:1] + ('-OP' if open_flag else '')
                        code=f"POS-{sg[:3].upper()}-{suffix}"
                        Position.objects.get_or_create(
                            year=y, code=code,
                            defaults={
                                'name': f"{sg} {lvl}{' (Open)' if open_flag else ''}",
                                'skill': skill_obj,
                                'level': lvl,
                                'fte': 1.0,
                                'is_open': open_flag
                            }
                        )
        # assign users to 2025 filled
        filled=Position.objects.filter(year__code='2025',is_open=False)
        for user in User.objects.exclude(is_superuser=True)[:50]:
            pos=filled.order_by('?').first(); user.profile.position=pos; user.profile.availability=random.uniform(6,12); user.profile.save()

        # 6. RateCards per year
        for y in years:
            for sg in SKILLS:
                skill_obj = skill_map[sg]
                for country in OUTSOURCING_COUNTRIES:
                    RateCard.objects.get_or_create(
                        year=y,skill=skill_obj,
                        resource_type=random.choice(['Contractor','MSP']),
                        country=country,
                        defaults={'efficiency_factor':round(random.uniform(0.7,1.0),2),'hourly_rate':round(random.uniform(20,120),2)}
                    )

        # 7. CostCenters & InternalOrders
        for i in range(1,4):
            CostCenter.objects.get_or_create(code=f'CC{i}',defaults={'name':f'Cost Center {i}','order':i})
            InternalOrder.objects.get_or_create(code=f'IO{i}',defaults={'name':f'Internal Order {i}','cc_code':f'CC{i}'})

        # 8. SLAProfiles
        SLAProfile.objects.get_or_create(name='Standard SLA',defaults={
            'response_time':timedelta(hours=2),'resolution_time':timedelta(hours=8),'availability':Decimal('99.9'),'description':'Default SLA'
        })

        # 9. KeyFigures
        for code,name,pct,uom in [('FTE','Man-Months',False,hrs),('COST','Labor Cost',False,usd),('LICENSE','License Cost',False,usd),('ADMIN','Admin Overhead',False,usd)]:
            KeyFigure.objects.get_or_create(code=code,defaults={'name':name,'is_percent':pct,'default_uom':uom})

        # 10. Planning Layout & Facts
        layout,_=PlanningLayout.objects.get_or_create(code='DEMOC',defaults={'name':'Demo Planning','domain':'cost','default':True})
        for year in years:
            for version in Version.objects.all():
                ply,_=PlanningLayoutYear.objects.get_or_create(layout=layout,year=year,version=version)

                for ply in PlanningLayoutYear.objects.all():
                    # 1-month buckets
                    PeriodGrouping.objects.get_or_create(
                        layout_year=ply,
                        months_per_bucket=1,
                        defaults={'label_prefix':''}
                    )
                    # optional: also create quarterly, half-year, etc.
                    PeriodGrouping.objects.get_or_create(
                        layout_year=ply,
                        months_per_bucket=3,
                        defaults={'label_prefix':'Q'}
                    )

                ply.org_units.set(OrgUnit.objects.all())
                for org in OrgUnit.objects.all():
                    ps,_=PlanningSession.objects.get_or_create(layout_year=ply,org_unit=org,defaults={'created_by':admin})
                    dr,_=DataRequest.objects.get_or_create(session=ps,description='Auto-demo',defaults={'created_by':admin})
                    if version.code=='ACTUAL':
                        # historical actuals for 2024
                        for svc in services:
                            for period in Period.objects.all():
                                # FTE actual
                                PlanningFact.objects.update_or_create(
                                    request=dr,session=ps,version=version,year=year,period=period,org_unit=org,service=svc,account=None,
                                    dimension_values={'Type':'Actual'},key_figure=KeyFigure.objects.get(code='FTE'),
                                    defaults={'value':round(random.uniform(1,8),2),'uom':hrs,'ref_value':0,'ref_uom':None}
                                )
                                # COST actual
                                PlanningFact.objects.update_or_create(
                                    request=dr,session=ps,version=version,year=year,period=period,org_unit=org,service=svc,account=None,
                                    dimension_values={'Type':'Actual'},key_figure=KeyFigure.objects.get(code='COST'),
                                    defaults={'value':round(random.uniform(1000,5000),2),'uom':usd,'ref_value':0,'ref_uom':None}
                                )
                        continue
                    # planning facts
                    for svc in services:
                        for period in Period.objects.all():
                            for scen,vcode in SCENARIOS.items():
                                ver=Version.objects.get(code=vcode)
                                PlanningFact.objects.update_or_create(
                                    request=dr,session=ps,version=ver,year=year,period=period,org_unit=org,service=svc,account=None,
                                    dimension_values={'Scenario':scen},key_figure=KeyFigure.objects.get(code='FTE'),
                                    defaults={'value':round(random.uniform(1,8),2),'uom':hrs,'ref_value':0,'ref_uom':None}
                                )
                                for country in OUTSOURCING_COUNTRIES:
                                    PlanningFact.objects.update_or_create(
                                        request=dr,session=ps,version=ver,year=year,period=period,org_unit=org,service=svc,account=None,
                                        dimension_values={'Scenario':scen,'Type':'Outsourced','Country':country},key_figure=KeyFigure.objects.get(code='FTE'),
                                        defaults={'value':round(random.uniform(0,2),2),'uom':hrs,'ref_value':0,'ref_uom':None}
                                    )
                            # labor cost
                            PlanningFact.objects.update_or_create(
                                request=dr,session=ps,version=ver,year=year,period=period,org_unit=org,service=svc,account=None,dimension_values={},
                                key_figure=KeyFigure.objects.get(code='COST'),defaults={'value':round(random.uniform(50,150)*random.uniform(1,8),2),'uom':usd,'ref_value':0,'ref_uom':None}
                            )
                            # license cost
                            PlanningFact.objects.update_or_create(
                                request=dr,session=ps,version=ver,year=year,period=period,org_unit=org,service=svc,account=None,
                                dimension_values={'Driver':random.choice(['UserCount','ServerCount'])},key_figure=KeyFigure.objects.get(code='LICENSE'),
                                defaults={'value':round(random.randint(10,100)*random.uniform(1,12),2),'uom':ea,'ref_value':0,'ref_uom':None}
                            )
                    # admin & orgmgmt & shared
                    first_period=Period.objects.get(code='01')
                    PlanningFact.objects.update_or_create(request=dr,session=ps,version=Version.objects.get(code='DRAFT'),year=year,period=first_period,org_unit=org,service=None,account=None,dimension_values={'Type':'Admin'},key_figure=KeyFigure.objects.get(code='ADMIN'),defaults={'value':round(random.uniform(1000,5000),2),'uom':usd,'ref_value':0,'ref_uom':None})
                    PlanningFact.objects.update_or_create(request=dr,session=ps,version=Version.objects.get(code='DRAFT'),year=year,period=first_period,org_unit=org,service=None,account=None,dimension_values={'Type':'OrgMgmtCost'},key_figure=KeyFigure.objects.get(code='COST'),defaults={'value':round(random.uniform(5000,15000),2),'uom':usd,'ref_value':0,'ref_uom':None})
                    if shared_service:
                        for cbu in CBU.objects.filter(is_active=True):
                            PlanningFact.objects.update_or_create(request=dr,session=ps,version=Version.objects.get(code='DRAFT'),year=year,period=first_period,org_unit=org,service=shared_service,account=None,dimension_values={'Type':'SharedService','CBU':cbu.code},key_figure=KeyFigure.objects.get(code='COST'),defaults={'value':round(random.uniform(2000,8000),2),'uom':usd,'ref_value':0,'ref_uom':None})

        # 11. Formula machinery
        tax_rate,_=Constant.objects.get_or_create(name='TAX_RATE',defaults={'value':Decimal('0.15')})
        growth_sf,_=SubFormula.objects.get_or_create(name='GROWTH_FACTOR',layout=layout,defaults={'expression':'0.10'})
        formula,_=Formula.objects.get_or_create(layout=layout,name='Cost Growth',defaults={'expression':(
            'FOREACH OrgUnit:\n'
            '  [Year=2026,OrgUnit=$OrgUnit]?.[COST] = [Year=2025,OrgUnit=$OrgUnit]?.[COST] * (1 + $GROWTH_FACTOR)'
        )})
        formula.dimensions.set([ContentType.objects.get_for_model(OrgUnit)])
        formula.reference_year=Year.objects.get(code='2025')
        formula.reference_version=Version.objects.get(code='PLAN V1')
        formula.save()
        pf,_=PlanningFunction.objects.get_or_create(layout=layout,name='Copy Cost Baseline',function_type='COPY',defaults={'parameters':{
            'from_version':Version.objects.get(code='PLAN V1').id,'to_version':Version.objects.get(code='PLAN V2').id,'year': Year.objects.get(code='2025').id,'period': Period.objects.get(code='01').id,
        }})
        for ps in PlanningSession.objects.filter(layout_year__layout=layout,layout_year__year__code='2026'):
            run=FormulaRun.objects.create(formula=formula,run_by=admin)
            created=pf.execute(ps)
            self.stdout.write(f"Executed {pf.name} for {ps.org_unit.code}: {created} facts copied")

        self.stdout.write(self.style.SUCCESS('✅ Demo & historical data plus formula seed complete.'))