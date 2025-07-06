# bps/forms.py

from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, Submit
from dal_select2.widgets import ModelSelect2, ModelSelect2Multiple
from django.contrib.contenttypes.models import ContentType
from .models import (
    Constant, SubFormula, Formula,
    PlanningLayoutYear, PeriodGrouping, PlanningSession,
    DataRequest, PlanningFact, Year, Version, OrgUnit
)


class FactForm(forms.ModelForm):
    class Meta:
        model = PlanningFact
        fields = [
            'session',
            'period',
            'quantity', 'quantity_uom',
            'amount', 'amount_uom',
            'other_key_figure', 'other_value',
        ]
        widgets = {
            'session': ModelSelect2(
                url='bps:layoutyear-autocomplete'
            ),
            'period': ModelSelect2(
                url='bps:period-autocomplete'
            ),
            'quantity_uom': ModelSelect2(
                url='bps:uom-autocomplete'
            ),
            'amount_uom': ModelSelect2(
                url='bps:uom-autocomplete'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Row(
                Column('session', css_class='col-md-4'),
                Column('period',  css_class='col-md-2'),
                Column('quantity',     css_class='col-md-2'),
                Column('quantity_uom', css_class='col-md-2'),
                Column('amount',       css_class='col-md-2'),
                Column('amount_uom',   css_class='col-md-2'),
            ),
            Row(
                Column('other_key_figure', css_class='col-md-4'),
                Column('other_value',      css_class='col-md-4'),
            ),
            Submit('save','Save Fact')
        )


class ConstantForm(forms.ModelForm):
    class Meta:
        model = Constant
        fields = ['name', 'value']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'name', 'value',
            Submit('save','Save Constant')
        )


class SubFormulaForm(forms.ModelForm):
    class Meta:
        model = SubFormula
        fields = ['name', 'expression']
        widgets = {'expression': forms.Textarea(attrs={'rows':3})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'name', 'expression',
            Submit('save','Save Sub-Formula')
        )


class FormulaForm(forms.ModelForm):
    loop_dimension = forms.ModelChoiceField(
        queryset=ContentType.objects.all(),
        widget=ModelSelect2(
            url='bps:contenttype-autocomplete'
        )
    )
    class Meta:
        model = Formula
        fields = ['name', 'loop_dimension', 'expression']
        widgets = {
            'expression': forms.Textarea(attrs={'rows':4}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'name', 'loop_dimension', 'expression',
            Submit('save','Save Formula')
        )

# ── A. Session Form ────────────────────────────────────────────────────────

class PlanningSessionForm(forms.ModelForm):
    class Meta:
        model = PlanningSession
        fields = ['layout_year','org_unit']
        widgets = {
           'layout_year': ModelSelect2(url='layoutyear-autocomplete'),
           'org_unit'   : ModelSelect2(url='orgunit-autocomplete'),
        }
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
          Row(Column('layout_year', css_class='col-md-6'),
              Column('org_unit',    css_class='col-md-6')),
          Submit('start','Start Planning')
        )

# ── B. Period Selector (Vue stub) ─────────────────────────────────────────

class PeriodSelector(forms.Form):
    grouping = forms.ModelChoiceField(
        queryset=PeriodGrouping.objects.none(),
        label="Period Grouping"
    )
    def __init__(self, *a, session:PlanningSession, **kw):
        super().__init__(*a,**kw)
        qs = session.layout_year.period_groupings.all()
        self.fields['grouping'].queryset = qs
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'grouping',
            Submit('apply','Apply')
        )

# ── C. FactField config–driven form omitted for brevity ────────────────────
#    (Use the FactField / DynamicFactForm pattern from previous example)

class PlanningFactForm(forms.ModelForm):
    class Meta:
        model = PlanningFact
        fields = [
          'period','quantity','quantity_uom',
          'amount','amount_uom',
          'other_key_figure','other_value',
        ]
        widgets = {
          'period': forms.TextInput(attrs={'placeholder':'01, Q1, H1'}),
          'quantity_uom': ModelSelect2(url='uom-autocomplete'),
          'amount_uom':   ModelSelect2(url='uom-autocomplete'),
        }