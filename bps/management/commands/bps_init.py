from django.core.management.base import BaseCommand
from bps.models import UnitOfMeasure, ConversionRate, Year, Version, Period, KeyFigure, SLAProfile
from datetime import timedelta

class Command(BaseCommand):
    help = 'Loads initial reference data for BPS app'

    def handle(self, *args, **options):
        # Units
        hrs, _ = UnitOfMeasure.objects.get_or_create(code='HRS', name='Hours', is_base=True)
        usd, _ = UnitOfMeasure.objects.get_or_create(code='USD', name='US Dollar', is_base=False)

        # Conversion
        ConversionRate.objects.get_or_create(from_uom=hrs, to_uom=usd, factor=100)

        # Years
        for y in range(2024, 2027):
            Year.objects.get_or_create(code=str(y), name=f'Fiscal Year {y}', order=y - 2020)

        # Versions
        for i, v in enumerate(['Draft', 'Final', 'Plan v1', 'Plan v2']):
            Version.objects.get_or_create(code=v.upper(), name=v, order=i)

        # Periods (Jan–Dec)
        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        for i, name in enumerate(months, 1):
            Period.objects.get_or_create(code=f"{i:02}", name=name, order=i)

        # Key Figures
        kfs = [
            ('FTE', 'Full-Time Equivalent', False, hrs),
            ('COST', 'Total Cost', False, usd),
            ('UTIL', 'Utilization %', True, None),
        ]
        for code, name, is_percent, uom in kfs:
            KeyFigure.objects.get_or_create(code=code, name=name, is_percent=is_percent, default_uom=uom)

        # SLA Profiles
        SLAProfile.objects.get_or_create(
            name='Standard SLA',
            response_time=timedelta(hours=2),
            resolution_time=timedelta(hours=8),
            availability=99.9,
            defaults={'description': 'Default SLA for Tier-2 services'}
        )

        self.stdout.write(self.style.SUCCESS('Initial BPS data loaded.'))