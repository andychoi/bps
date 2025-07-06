# in bps/forms.py

from django import forms
from .models import PlanningRecord, PriceType

class PlanningRecordForm(forms.ModelForm):
    # this will *not* create an FK — it's just UI
    price_type = forms.ModelChoiceField(
        queryset=PriceType.objects.all(),
        required=False
    )

    class Meta:
        model = PlanningRecord
        fields = [
            "layout", "year", "version", "orgunit", "account", "period",
            # no "price_type" here, we'll handle it manually
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # if editing an existing record, pre-fill the JSON value
        if self.instance.pk:
            pt_id = self.instance.dimension_values.get("PriceType")
            if pt_id:
                self.fields["price_type"].initial = PriceType.objects.filter(pk=pt_id).first()

    def clean(self):
        cleaned = super().clean()
        # nothing else to do here
        return cleaned

    def save(self, commit=True):
        record = super().save(commit=False)
        pt = self.cleaned_data.get("price_type")
        if pt:
            record.dimension_values["PriceType"] = pt.pk
        else:
            record.dimension_values.pop("PriceType", None)
        if commit:
            record.save()
        return record