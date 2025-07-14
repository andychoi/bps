import random
from django.core.management.base import BaseCommand
from faker import Faker

from django.contrib.auth import get_user_model
User = get_user_model()
from apps.users.models import OrgUnit, OrgLevel  # Adjust import if needed


ORGS = {
        'Application': {
            'Software': ['Backend', 'Frontend', 'Database'],
            'Product Management': ['Business Analysis', 'Product Design']
        },
        'Infrastructure': {
            'Infrastructure': ['DevOps', 'QA'],
            'Support': ['Technical Support', 'Customer Service']
        },
        'Service Operation': {
            'Support': ['Field Support', 'Remote Support'],
        },
        'Admins': {
            'Business Development': ['Strategy', 'Operations'],
            'Support': ['Admin Support']
        }
}

JOB_TITLES = {
    'Division': [
        'Chief Information Officer',
        'Vice President of IT',
        'Head of IT Operations'
    ],
    'Department': [
        'IT Manager',
        'Department Head',
        'Senior Project Manager'
    ],
    'Team': [
        'Team Lead',
        'Senior Developer',
        'Systems Analyst',
        'Network Engineer',
        'DevOps Engineer',
        'Software Engineer'
    ]
}

class Command(BaseCommand):
    help = 'Generate hierarchical demo users and clean up existing demo users and OrgUnits.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--num_users',
            type=int,
            default=25,
            help='Number of demo users to generate (between 5 and 200).'
        )
        parser.add_argument(
            '--company',
            type=str,
            default='demo',
            help='The company name for the demo users. Defaults to "demo".'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Clean up existing demo data and exit without generating new data.'
        )

    def handle(self, *args, **kwargs):
        num_users = kwargs['num_users']
        company = kwargs['company']
        reset = kwargs['reset']

        if reset:
            self.stdout.write(f'Cleaning up existing demo data for company "{company}"...')
            self.cleanup_users(company)
            self.cleanup_orgunits(company)
            self.stdout.write(self.style.SUCCESS('Successfully cleaned up existing demo data.'))
            return

        if num_users < 5 or num_users > 200:
            self.stdout.write(self.style.ERROR('Please specify a number between 5 and 200.'))
            return

        self.stdout.write(f'Cleaning up existing users and OrgUnits for company "{company}"...')
        self.cleanup_users(company)
        self.cleanup_orgunits(company)

        fake = Faker()

        def get_or_create_orgunit(name, level, parent=None):
            return OrgUnit.objects.get_or_create(
                name=name,
                defaults={
                    'code': fake.bothify(text='###-###'),
                    'description': fake.text(max_nb_chars=200),
                    'level': level,
                    'company': company,
                    'parent': parent
                }
            )[0]

        self.stdout.write(f'Generating divisions and departments...')
        orgunits = {}
        orgunit_company = get_or_create_orgunit(company, level=0)
        for division_name, departments in ORGS.items():
            division = get_or_create_orgunit(division_name, level=2, parent=orgunit_company)
            orgunits[division_name] = division
            for department_name, teams in departments.items():
                department = get_or_create_orgunit(department_name, level=3, parent=division)
                orgunits[department_name] = department
                for team_name in teams:
                    team = get_or_create_orgunit(team_name, level=4, parent=department)
                    orgunits[team_name] = team

        self.stdout.write(f'Generating {num_users} demo users for company "{company}"...')

        managers = []

        def generate_username(first_name, last_name):
            short_last_name = last_name[:3].lower()
            base_username = f'{first_name.lower()}.{short_last_name}'
            username = base_username
            suffix = 1
            while User.objects.filter(username=username).exists():
                username = f'{base_username}{suffix}'
                suffix += 1
            return username, 'demo'  # Set the demo password

        def assign_users_to_orgunit(users_needed, orgunit, level):
            job_titles = JOB_TITLES[level]
            users_created = 0

            for _ in range(users_needed):
                first_name = fake.first_name()
                last_name = fake.last_name()
                username, password = generate_username(first_name, last_name)
                email = f'{username}@{company}.local'
                job_title = random.choice(job_titles)
                is_active = random.random() > 0.1

                user = User(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    company=company,
                    dept_name=orgunit.name,
                    job_title=job_title,
                    is_active=is_active,
                    orgunit=orgunit
                )

                # Assign a manager from the managers list, if available
                if managers and level != 'Division':
                    manager = random.choice(managers)
                    user.manager = manager
                # else:
                #     user.manager = User.objects.get(username='admin')   #for testing purpose

                user.set_password(password)  # Set the demo password
                user.save()
                managers.append(user)
                users_created += 1

            return users_created

        total_users_created = 0
        divisions = [orgunit for orgunit in orgunits.values() if orgunit.level == 2]
        departments = [orgunit for orgunit in orgunits.values() if orgunit.level == 3]
        teams = [orgunit for orgunit in orgunits.values() if orgunit.level == 4]

        # Calculate the number of users to create at each level
        division_users = max(1, num_users // (len(divisions) + len(departments) + len(teams)) * len(divisions))
        department_users = max(1, num_users // (len(divisions) + len(departments) + len(teams)) * len(departments))
        team_users = num_users - division_users - department_users

        # Assign users at the division level
        for division in divisions:
            total_users_created += assign_users_to_orgunit(division_users // len(divisions), division, 'Division')

        # Assign users at the department level
        for department in departments:
            total_users_created += assign_users_to_orgunit(department_users // len(departments), department, 'Department')

        # Assign users at the team level
        for team in teams:
            total_users_created += assign_users_to_orgunit(team_users // len(teams), team, 'Team')

        self.stdout.write(self.style.SUCCESS(f'Successfully generated {total_users_created} hierarchical demo users for company "{company}".'))

    def cleanup_users(self, company):
        from django.db import transaction
        with transaction.atomic():
            User.objects.filter(company=company).delete()

    def cleanup_orgunits(self, company):
        from django.db import transaction
        with transaction.atomic():
            OrgUnit.objects.filter(company=company).delete()
