# bps/management/commands/cleanup_bps_demo.py

from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import connection, transaction

class Command(BaseCommand):
    help = 'Clean up all BPS demo data in correct dependency order (with fast truncate for PlanningFact)'

    def handle(self, *args, **options):
        # 1) truncate the big fact table directly in SQL
        self.stdout.write("→ Truncating PlanningFact via raw SQL…")
        with connection.cursor() as cursor:
            # Adjust quoting if you have a custom schema or quoting requirements
            cursor.execute('TRUNCATE TABLE "bps_planningfact" CASCADE;')
        self.stdout.write(self.style.SUCCESS("   ● PlanningFact truncated"))

        # 2) now delete everything else
        to_delete = [
            ('bps', 'DataRequestLog'),
            ('bps', 'PlanningFactDimension'),
            ('bps', 'DataRequest'),
            ('bps', 'PlanningSession'),
            ('bps', 'FormulaRunEntry'),
            ('bps', 'FormulaRun'),
            ('bps', 'ScenarioFunction'),
            ('bps', 'ScenarioStep'),
            ('bps', 'ScenarioStage'),
            ('bps', 'ScenarioOrgUnit'),
            ('bps', 'PlanningScenario'),
            ('bps', 'PlanningStage'),
            ('bps', 'PeriodGrouping'),
            ('bps', 'PlanningLayoutDimension'),
            ('bps', 'PlanningKeyFigure'),
            ('bps', 'PlanningDimension'),
            ('bps', 'PlanningLayoutYear'),
            ('bps', 'PlanningLayout'),
            ('bps', 'PlanningFunction'),
            ('bps', 'Formula'),
            ('bps', 'SubFormula'),
            ('bps', 'ReferenceData'),
            ('bps', 'RateCard'),
            ('bps', 'Position'),
            ('bps', 'Employee'),
            ('bps', 'Contractor'),
            ('bps', 'MSPStaff'),
            ('bps', 'Resource'),
            ('bps', 'Skill'),
            ('bps', 'Service'),
            ('bps', 'InternalOrder'),
            ('bps', 'CostCenter'),
            ('bps', 'CBU'),
            ('bps', 'OrgUnit'),
            ('bps', 'ConversionRate'),
            ('bps', 'UnitOfMeasure'),
            ('bps', 'KeyFigure'),
            ('bps', 'GlobalVariable'),
            ('bps', 'Constant'),
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