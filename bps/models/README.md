

python manage.py makemigrations --empty bps

from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('your_app_name', '0001_initial'),  # Replace with your last migration
    ]

    operations = [
        migrations.RunSQL(
            # SQL to create or replace the view
            """
            CREATE OR REPLACE VIEW pivoted_planningfact AS
            SELECT
                version,
                year,
                org_unit,
                service,
                account,
                key_figure,
                -- Value columns
                MAX(CASE WHEN period = 'v01' THEN value ELSE NULL END) AS v01,
                MAX(CASE WHEN period = 'v02' THEN value ELSE NULL END) AS v02,
                MAX(CASE WHEN period = 'v03' THEN value ELSE NULL END) AS v03,
                -- Add other value columns...
                MAX(CASE WHEN period = 'v12' THEN value ELSE NULL END) AS v12,
                -- Reference value columns
                MAX(CASE WHEN period = 'r01' THEN value ELSE NULL END) AS r01,
                MAX(CASE WHEN period = 'r02' THEN value ELSE NULL END) AS r02,
                MAX(CASE WHEN period = 'r03' THEN value ELSE NULL END) AS r03,
                -- Add other reference value columns...
                MAX(CASE WHEN period = 'r12' THEN value ELSE NULL END) AS r12,
                -- Totals
                SUM(CASE WHEN period LIKE 'v%' THEN value ELSE 0 END) AS total_value,
                SUM(CASE WHEN period LIKE 'r%' THEN value ELSE 0 END) AS total_reference
            FROM
                planningfact
            GROUP BY
                version, year, org_unit, service, account, key_figure;
            """,
            # SQL to drop the view (for rollback)
            "DROP VIEW IF EXISTS pivoted_planningfact;",
        )
    ]
