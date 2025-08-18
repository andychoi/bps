# bps/migrations/0002_create_pivoted_planningfact_view.py
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('bps', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            # Create or replace the pivoted view
            sql="""
            CREATE OR REPLACE VIEW pivoted_planningfact AS
            SELECT
                pf.version_id    AS version,
                pf.year_id       AS year,
                pf.org_unit_id   AS org_unit,
                pf.service_id    AS service,
                pf.account_id    AS account,
                pf.extra_dimensions_json AS extra_dimensions_json,
                pf.key_figure_id AS key_figure,

                MAX(CASE WHEN per.code = '01' THEN pf.value END) AS v01,
                MAX(CASE WHEN per.code = '02' THEN pf.value END) AS v02,
                MAX(CASE WHEN per.code = '03' THEN pf.value END) AS v03,
                MAX(CASE WHEN per.code = '04' THEN pf.value END) AS v04,
                MAX(CASE WHEN per.code = '05' THEN pf.value END) AS v05,
                MAX(CASE WHEN per.code = '06' THEN pf.value END) AS v06,
                MAX(CASE WHEN per.code = '07' THEN pf.value END) AS v07,
                MAX(CASE WHEN per.code = '08' THEN pf.value END) AS v08,
                MAX(CASE WHEN per.code = '09' THEN pf.value END) AS v09,
                MAX(CASE WHEN per.code = '10' THEN pf.value END) AS v10,
                MAX(CASE WHEN per.code = '11' THEN pf.value END) AS v11,
                MAX(CASE WHEN per.code = '12' THEN pf.value END) AS v12,

                MAX(CASE WHEN per.code = '01' THEN pf.ref_value END) AS r01,
                MAX(CASE WHEN per.code = '02' THEN pf.ref_value END) AS r02,
                MAX(CASE WHEN per.code = '03' THEN pf.ref_value END) AS r03,
                MAX(CASE WHEN per.code = '04' THEN pf.ref_value END) AS r04,
                MAX(CASE WHEN per.code = '05' THEN pf.ref_value END) AS r05,
                MAX(CASE WHEN per.code = '06' THEN pf.ref_value END) AS r06,
                MAX(CASE WHEN per.code = '07' THEN pf.ref_value END) AS r07,
                MAX(CASE WHEN per.code = '08' THEN pf.ref_value END) AS r08,
                MAX(CASE WHEN per.code = '09' THEN pf.ref_value END) AS r09,
                MAX(CASE WHEN per.code = '10' THEN pf.ref_value END) AS r10,
                MAX(CASE WHEN per.code = '11' THEN pf.ref_value END) AS r11,
                MAX(CASE WHEN per.code = '12' THEN pf.ref_value END) AS r12,

                SUM(pf.value)     AS total_value,
                SUM(pf.ref_value) AS total_reference

            FROM bps_planningfact AS pf
            JOIN bps_period       AS per ON pf.period_id = per.id
            GROUP BY
                pf.version_id,
                pf.year_id,
                pf.org_unit_id,
                pf.service_id,
                pf.account_id,
                pf.extra_dimensions_json,
                pf.key_figure_id;
            """,
            # Rollback: drop the view
            reverse_sql="DROP VIEW IF EXISTS pivoted_planningfact;"
        )
    ]