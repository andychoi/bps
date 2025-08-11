from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = "Clean up all BPS demo data in correct dependency order (with fast truncate for PlanningFact)"

    def handle(self, *args, **options):
        self.stdout.write("→ Truncating PlanningFact via raw SQL…")
        try:
            with connection.cursor() as cursor:
                cursor.execute('TRUNCATE TABLE "bps_planningfact" CASCADE;')
            self.stdout.write(self.style.SUCCESS("   ● PlanningFact truncated"))
        except Exception as e:
            self.stderr.write(f"   ⚠️ Could not TRUNCATE PlanningFact: {e}. Will cascade via deletes.")

        # Delete children → parents
        to_delete = [
            ("bps", "DataRequestLog"),
            # ("bps", "PlanningFactDimension"),  # removed in refactor
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

            # New: per-instance overrides must be deleted before PLD/PLY/PL
            ("bps", "LayoutDimensionOverride"),

            # Instance before template
            ("bps", "PlanningLayoutYear"),

            # Template-level attachments
            ("bps", "PlanningLayoutDimension"),
            ("bps", "PlanningKeyFigure"),

            # Removed legacy model
            # ("bps", "PlanningDimension"),

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