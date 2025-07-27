from django.core.management.base import BaseCommand
from django.apps import apps

class Command(BaseCommand):
    help = 'Clean up all BPS demo data in correct dependency order'

    def handle(self, *args, **options):
        # List of (app_label, model_name) tuples in dependency-safe deletion order
        template_models = [
            ('bps', 'PlanningFactDimension'),
            ('bps', 'DataRequestLog'),
            ('bps', 'FormulaRunEntry'),
            ('bps', 'PlanningFact'),
            ('bps', 'DataRequest'),
            ('bps', 'PlanningSession'),
            ('bps', 'PeriodGrouping'),
            ('bps', 'PlanningLayoutDimension'),
            ('bps', 'PlanningLayoutYear'),
            ('bps', 'PlanningLayout'),
            ('bps', 'PlanningFunction'),
            ('bps', 'Formula'),
            ('bps', 'SubFormula'),
            ('bps', 'RateCard'),
            ('bps', 'Position'),
            ('bps', 'Service'),
            ('bps', 'InternalOrder'),
            ('bps', 'CostCenter'),
            ('bps', 'CBU'),
            ('bps', 'OrgUnit'),
            ('bps', 'ConversionRate'),
            ('bps', 'UnitOfMeasure'),
            ('bps', 'KeyFigure'),
            ('bps', 'Constant'),
            ('bps', 'Skill'),
        ]

        for app_label, model_name in template_models:
            Model = apps.get_model(app_label, model_name)
            deleted_count, _ = Model.objects.all().delete()
            self.stdout.write(f"Deleted {deleted_count} objects from {app_label}.{model_name}")

        self.stdout.write(self.style.SUCCESS('✅ All BPS demo data deleted.'))