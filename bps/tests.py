# bps/tests.py

from django.test import TestCase
from decimal import Decimal
from bps.models import (
    PlanningFact, Formula, SubFormula, Constant,
    FormulaRun, UnitOfMeasure, ConversionRate, PlanningSession, OrgUnit, Year, Version
)
from bps.formula_executor import FormulaExecutor

class FormulaExecutorTest(TestCase):
    def setUp(self):
        # Basic dimensions
        self.year = Year.objects.create(code='2025', name='2025')
        self.version = Version.objects.create(code='V1', name='Version 1')

        # UoMs
        self.uom_usd = UnitOfMeasure.objects.create(code='USD', name='US Dollar', is_base=True)
        self.uom_ea = UnitOfMeasure.objects.create(code='EA', name='Each')

        # Conversion rates (example)
        ConversionRate.objects.create(from_uom=self.uom_ea, to_uom=self.uom_usd, factor=Decimal('10'))

        # OrgUnits
        self.org_unit_a = OrgUnit.objects.create(code='OUA', name='OrgUnit A')

        # PlanningSession
        self.session = PlanningSession.objects.create(
            layout_year=None,  # simplify
            org_unit=self.org_unit_a,
            status='DRAFT'
        )

        # Constants
        Constant.objects.create(name='TAX_RATE', value=Decimal('0.15'))

        # Subformulas
        SubFormula.objects.create(
            name='PRICE_WITH_TAX',
            expression='[Product=1].?[amount] * (1 + TAX_RATE)',
            layout=None  # simplify
        )

        # Formula
        self.formula = Formula.objects.create(
            layout=None,  # simplify
            loop_dimension=OrgUnit.objects.first()._meta.app_label,
            expression='[OrgUnit=$LOOP].?[amount] = $PRICE_WITH_TAX'
        )

        # Initial PlanningFact
        PlanningFact.objects.create(
            request=self.formula,
            session=self.session,
            period='01',
            row_values={'OrgUnit': self.org_unit_a.pk, 'Product': 1},
            amount=Decimal('100'),
            amount_uom=self.uom_usd,
            quantity=Decimal('10'),
            quantity_uom=self.uom_ea
        )

    def test_formula_execution(self):
        executor = FormulaExecutor(
            formula=self.formula,
            session=self.session,
            period='01'
        )
        entries = executor.execute()

        # Verify formula run created
        run = FormulaRun.objects.first()
        self.assertIsNotNone(run)
        self.assertEqual(run.formula, self.formula)

        # Check entries
        self.assertEqual(entries.count(), 1)
        entry = entries.first()

        self.assertEqual(entry.old_value, Decimal('100'))  # original amount
        self.assertEqual(entry.new_value, Decimal('115.0000'))  # amount * 1.15 tax rate

        # Check PlanningFact updated correctly
        fact = PlanningFact.objects.get(
            session=self.session,
            period='01',
            row_values={'OrgUnit': self.org_unit_a.pk}
        )
        self.assertEqual(fact.amount, Decimal('115.0000'))
        self.assertEqual(fact.amount_uom, self.uom_usd)

    def test_uom_conversion(self):
        # Test conversion helper
        fact = PlanningFact.objects.first()
        converted_amount = fact.amount * ConversionRate.objects.get(
            from_uom=fact.quantity_uom, to_uom=self.uom_usd).factor
        self.assertEqual(converted_amount, Decimal('100'))

    def test_formula_with_missing_fact(self):
        # Formula referencing non-existing fact
        formula = Formula.objects.create(
            layout=None,
            loop_dimension=OrgUnit.objects.first()._meta.app_label,
            expression='[OrgUnit=$LOOP,Product=99].?[amount] = 50'
        )
        executor = FormulaExecutor(formula, session=self.session, period='01')
        entries = executor.execute()

        # Verify new fact created
        fact = PlanningFact.objects.filter(
            session=self.session,
            period='01',
            row_values={'OrgUnit': self.org_unit_a.pk, 'Product': 99}
        ).first()
        self.assertIsNotNone(fact)
        self.assertEqual(fact.amount, Decimal('50'))

        # Entry check
        entry = entries.first()
        self.assertEqual(entry.old_value, 0)
        self.assertEqual(entry.new_value, Decimal('50'))

    def test_formula_preview_mode(self):
        executor = FormulaExecutor(
            formula=self.formula,
            session=self.session,
            period='01',
            preview=True
        )
        entries = executor.execute()

        # Ensure PlanningFact is not updated
        fact = PlanningFact.objects.get(
            session=self.session,
            period='01',
            row_values={'OrgUnit': self.org_unit_a.pk, 'Product': 1}
        )
        self.assertEqual(fact.amount, Decimal('100'))  # unchanged

        # Entry should reflect calculated but unsaved new value
        entry = entries.first()
        self.assertEqual(entry.old_value, Decimal('100'))
        self.assertEqual(entry.new_value, Decimal('115.0000'))

    def test_complex_expression_eval(self):
        expr = '((10 + 5) * 2 - 4) / 2 ** 2'
        executor = FormulaExecutor(self.formula, session=self.session, period='01')
        result = executor._safe_eval(expr)
        self.assertEqual(result, Decimal('3.7500'))

    def test_dimension_resolution(self):
        # Verify JSON dimension resolution
        fact = PlanningFact.objects.first()
        self.assertEqual(fact.row_values['OrgUnit'], self.org_unit_a.pk)
        self.assertEqual(fact.row_values['Product'], 1)

    def test_missing_constant_handling(self):
        # Test proper error raised for missing constant
        formula = Formula.objects.create(
            layout=None,
            loop_dimension=OrgUnit.objects.first()._meta.app_label,
            expression='[OrgUnit=$LOOP].?[amount] = UNKNOWN_CONSTANT'
        )
        executor = FormulaExecutor(formula, session=self.session, period='01')
        with self.assertRaises(Constant.DoesNotExist):
            executor.execute()