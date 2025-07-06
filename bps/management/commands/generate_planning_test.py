from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from bps.models import (
    Year, PlanVersion, OrgUnit, Account, Period,
    PlanningLayout, PlanningLayoutLeadDimension, PlanningRecord,
    Constant, SubFormula, Formula, FormulaRun, FormulaRunEntry
)
import random

class Command(BaseCommand):
    help = 'Generate test data for the bps app'

    def handle(self, *args, **options):
        self.stdout.write('Creating Years...')
        years = []
        for y in range(2021, 2024):
            year, _ = Year.objects.get_or_create(value=y)
            years.append(year)

        self.stdout.write('Creating PlanVersions...')
        versions = []
        for name in ['Draft', 'Final']:
            pv, _ = PlanVersion.objects.get_or_create(name=name)
            versions.append(pv)

        self.stdout.write('Creating OrgUnits...')
        org_units = []
        for name in ['North', 'South', 'East', 'West']:
            ou, _ = OrgUnit.objects.get_or_create(name=name)
            org_units.append(ou)

        self.stdout.write('Creating Accounts...')
        accounts = []
        for code in ['1000', '2000', '3000']:
            acc, _ = Account.objects.get_or_create(code=code, defaults={'name': f'Account {code}'})
            accounts.append(acc)

        self.stdout.write('Creating Periods...')
        periods = []
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
        for idx, code in enumerate(months, start=1):
            p, _ = Period.objects.get_or_create(code=code, defaults={'order': idx})
            periods.append(p)

        self.stdout.write('Creating a PlanningLayout...')
        layout, _ = PlanningLayout.objects.get_or_create(
            name='Test Layout',
            defaults={'key_figures': ['amount', 'quantity']}
        )

        # Register lead dimensions: Year, PlanVersion, OrgUnit, Account
        self.stdout.write('Registering lead dimensions...')
        dims = [(Year, 1), (PlanVersion, 2), (OrgUnit, 3), (Account, 4)]
        for model, order in dims:
            ct = ContentType.objects.get_for_model(model)
            PlanningLayoutLeadDimension.objects.get_or_create(
                bpslayout=layout,
                contenttype=ct
            )

        # Set column dimension to Period
        self.stdout.write('Setting column dimension...')
        ct_period = ContentType.objects.get_for_model(Period)
        layout.column_dimension = ct_period
        layout.save()

        self.stdout.write('Generating PlanningRecords...')
        PlanningRecord.objects.filter(layout=layout).delete()
        records_created = 0
        for year in years:
            for pv in versions:
                for ou in org_units:
                    for acc in accounts:
                        for per in periods:
                            rec = PlanningRecord.objects.create(
                                layout=layout,
                                year=year,
                                version=pv,
                                orgunit=ou,
                                account=acc,
                                period=per,
                                dimension_values={},
                                key_figure_values={
                                    'amount': random.uniform(100, 1000),
                                    'quantity': random.randint(1, 100)
                                }
                            )
                            records_created += 1
        self.stdout.write(f'Created {records_created} PlanningRecords.')

        self.stdout.write(self.style.SUCCESS('Test data generation complete.'))
