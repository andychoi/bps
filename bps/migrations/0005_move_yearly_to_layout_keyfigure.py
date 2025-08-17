# Migration to move yearly flag from KeyFigure to PlanningKeyFigure

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bps', '0004_add_year_dependent_planning'),
    ]

    operations = [
        migrations.AddField(
            model_name='planningkeyfigure',
            name='is_yearly',
            field=models.BooleanField(default=False, help_text='If true, this key figure is planned at year level without periods for this layout.'),
        ),
        migrations.RemoveField(
            model_name='keyfigure',
            name='is_year_dependent',
        ),
    ]