# Generated migration for year-dependent planning

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bps', '0003_planninglayoutdimension_group_priority'),
    ]

    operations = [
        migrations.AddField(
            model_name='keyfigure',
            name='is_year_dependent',
            field=models.BooleanField(default=False, help_text='If true, this key figure is planned at year level without periods.'),
        ),
        migrations.AlterField(
            model_name='planningfact',
            name='period',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, to='bps.period'),
        ),
    ]