# bps/management/commands/cleanup_bps_demo.py
from django.core.management.base import BaseCommand
from django.apps import apps

class Command(BaseCommand):
    help = 'Clean up all BPS demo data in correct dependency order'

    def handle(self, *args, **options):
        # tear down in reverse‐dependency order
        to_delete = [
            # formula runs & entries
            ('bps', 'FormulaRunEntry'),
            ('bps', 'FormulaRun'),
            # fact dimensions & logs
            ('bps', 'PlanningFactDimension'),
            ('bps', 'DataRequestLog'),
            # facts & their request/session
            ('bps', 'PlanningFact'),
            ('bps', 'DataRequest'),
            ('bps', 'PlanningSession'),
            # workflow through‐tables
            ('bps', 'ScenarioFunction'),
            ('bps', 'ScenarioStep'),
            ('bps', 'ScenarioStage'),
            ('bps', 'ScenarioOrgUnit'),
            # scenario & stages
            ('bps', 'PlanningScenario'),
            ('bps', 'PlanningStage'),
            # layout pieces
            ('bps', 'PeriodGrouping'),
            ('bps', 'PlanningLayoutDimension'),
            ('bps', 'PlanningKeyFigure'),
            ('bps', 'PlanningDimension'),
            ('bps', 'PlanningLayoutYear'),
            ('bps', 'PlanningLayout'),
            # functions & formulas
            ('bps', 'ScenarioFunction'),
            ('bps', 'PlanningFunction'),
            ('bps', 'Formula'),
            ('bps', 'SubFormula'),
            # reference data
            ('bps', 'ReferenceData'),
            # resources
            ('bps', 'RateCard'),
            ('bps', 'Position'),
            ('bps', 'Employee'),
            ('bps', 'Contractor'),
            ('bps', 'MSPStaff'),
            ('bps', 'Resource'),
            ('bps', 'Skill'),
            # services & cost masters
            ('bps', 'Service'),
            ('bps', 'InternalOrder'),
            ('bps', 'CostCenter'),
            ('bps', 'CBU'),
            ('bps', 'OrgUnit'),
            # units & conversions
            ('bps', 'ConversionRate'),
            ('bps', 'UnitOfMeasure'),
            # key figures & constants & variables
            ('bps', 'KeyFigure'),
            ('bps', 'GlobalVariable'),
            ('bps', 'Constant'),
            # time dimensions
            ('bps', 'Period'),
            ('bps', 'Version'),
            ('bps', 'Year'),
        ]

        for app_label, model_name in to_delete:
            Model = apps.get_model(app_label, model_name)
            if not Model:
                self.stderr.write(f"Skipping missing model {app_label}.{model_name}")
                continue
            count, _ = Model.objects.all().delete()
            self.stdout.write(f"→ deleted {count} rows from {app_label}.{model_name}")

        self.stdout.write(self.style.SUCCESS("✅ All BPS demo data cleaned up."))