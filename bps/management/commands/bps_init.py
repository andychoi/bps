from datetime import timedelta
from django.core.management.base import BaseCommand
from bps.models import UnitOfMeasure, ConversionRate, Year, Version, Period, KeyFigure, SLAProfile
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

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
            defaults={'description': 'Default SLA for Tier-2 services'},
            response_time=timedelta(hours=2),
            resolution_time=timedelta(hours=8),
            availability=99.9,
        )

        self.stdout.write(self.style.SUCCESS('Initial BPS data loaded.'))

        # g, _ = Group.objects.get_or_create(name="Enterprise Planner")
        # U = get_user_model()
        # u = U.objects.get(username=username)
        # u.groups.add(g)
        # self.stdout.write(self.style.SUCCESS(f"✔ {username} added to Enterprise Planner"))        