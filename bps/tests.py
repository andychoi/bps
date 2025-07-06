# bps/tests.py
from django.test import TestCase
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from bps.models import (
    Year, OrgUnit, Period, PlanningLayout, PlanningRecord,
    Constant, SubFormula, Formula, FormulaRun, FormulaRunEntry
)
from bps.formula_executor import FormulaExecutor

class FormulaExecutorTest(TestCase):
    def setUp(self):
        # Create dimensions
        self.year = Year.objects.create(value=2025)
        self.org = OrgUnit.objects.create(name='OrgA')
        self.period = Period.objects.create(code='Jan', order=1)

        # Layout
        self.layout = PlanningLayout.objects.create(name='Layout1')
        # Create base records
        PlanningRecord.objects.create(
            layout=self.layout, year=self.year, orgunit=self.org,
            key_figure_values={'k1':5}
        )
        PlanningRecord.objects.create(
            layout=self.layout, year=self.year, period=self.period,
            key_figure_values={'k1':3}
        )

        # Constants & Sub
        Constant.objects.create(name='CONST1', value=2)
        SubFormula.objects.create(
            name='SUB1', layout=self.layout,
            expression='[year, period].[k1] + CONST1'
        )

        # Formula using ContentType for loop_dimension
        period_ct = ContentType.objects.get_for_model(Period)
        self.formula = Formula.objects.create(
            layout=self.layout,
            name='FullTest',
            loop_dimension=period_ct,
            expression='[orgunit, period].[k1] = $SUB1 * CONST1'
        )

    def test_execute_and_audit(self):
        entries = FormulaExecutor(self.formula).execute()
        self.assertTrue(entries.exists())
        run = FormulaRun.objects.get(formula=self.formula)
        self.assertFalse(run.preview)
        self.assertEqual(entries.count(), FormulaRunEntry.objects.filter(run=run).count())

    def test_preview_does_not_persist(self):
        FormulaExecutor(self.formula, preview=True).execute()
        run = FormulaRun.objects.get(formula=self.formula, preview=True)
        self.assertTrue(run.preview)
        # Ensure no record created for orgunit + period combination on preview
        exists = PlanningRecord.objects.filter(layout=self.layout, orgunit=self.org, period=self.period).exists()
        self.assertFalse(exists)rec.key_figure_values.get('k1'), 3)

