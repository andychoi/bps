# bps/forms.py

from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
from dal import autocomplete
from django.contrib.contenttypes.models import ContentType
from .models import (
    PlanningLayoutYear, PeriodGrouping, PlanningSession,
    DataRequest, PlanningFact, Year, Version, OrgUnit
)

# ── A. Session Form ────────────────────────────────────────────────────────

class PlanningSessionForm(forms.ModelForm):
    class Meta:
        model = PlanningSession
        fields = ['layout_year','org_unit']
        widgets = {
           'layout_year': autocomplete.ModelSelect2(url='layoutyear-autocomplete'),
           'org_unit'   : autocomplete.ModelSelect2(url='orgunit-autocomplete'),
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
          'quantity_uom': autocomplete.ModelSelect2(url='uom-autocomplete'),
          'amount_uom':   autocomplete.ModelSelect2(url='uom-autocomplete'),
        }