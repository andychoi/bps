Below is one way to make your “Fact” entry form 100% driven by configuration in the database, rather than hard-coding fields in FactForm.  We’ll:
	1.	Introduce a FactField config model to declare each field
	2.	Write a DynamicFactForm that reads those configs and builds its self.fields at runtime
	3.	Hook it into your views.py and templates so everything flows from the config
	4.	Sprinkle in crispy-forms, django-autocomplete-light, Bootstrap 5 and a Vue stub for any highly dynamic behaviors

⸻

1. planning/models.py

from django.db import models
from django.contrib.contenttypes.models import ContentType

class PlanningLayout(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # … your existing fields …
    def __str__(self): return self.name

class FactField(models.Model):
    """
    Defines one field on the Fact entry form.
    Order controls left-to-right rendering.
    """
    FIELD_TYPES = [
        ('char',   'Text'),
        ('int',    'Integer'),
        ('dec',    'Decimal'),
        ('fk',     'ForeignKey'),
    ]
    layout        = models.ForeignKey(PlanningLayout,
                                      on_delete=models.CASCADE,
                                      related_name='fact_fields')
    name          = models.CharField(max_length=50,
                                     help_text="Attribute name / form field name")
    label         = models.CharField(max_length=100,
                                     help_text="What users see")
    field_type    = models.CharField(max_length=4, choices=FIELD_TYPES)
    required      = models.BooleanField(default=True)
    order         = models.PositiveIntegerField(default=0)
    # only for FK fields:
    content_type  = models.ForeignKey(ContentType,
                                      on_delete=models.SET_NULL,
                                      blank=True, null=True,
                                      help_text="The model this FK points to")

    class Meta:
        unique_together = ('layout','name')
        ordering = ('layout','order')

    def __str__(self):
        return f"{self.layout.name} ▸ {self.label}"

	•	layout: which planning layout this field belongs to
	•	name: machine name, also the key in PlanningFact (or JSON)
	•	field_type: drives which Django field class to use
	•	content_type: for FK fields, which model to query

Run:

python manage.py makemigrations planning
python manage.py migrate


⸻

2. planning/admin.py

from django.contrib import admin
from .models import PlanningLayout, FactField

class FactFieldInline(admin.TabularInline):
    model = FactField
    extra = 1
    fields = ('order','name','label','field_type','required','content_type')

@admin.register(PlanningLayout)
class PlanningLayoutAdmin(admin.ModelAdmin):
    list_display = ('name',)
    inlines      = [FactFieldInline]

Now you can, per layout, drag-drop your fact form fields, mark them Text/Decimal/Integer/ForeignKey, set the FK’s ContentType, and change the order—and it instantly drives the form.

⸻

3. planning/forms.py

from django import forms
from django.contrib.contenttypes.models import ContentType
from dal import autocomplete
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
from .models import PlanningLayout, FactField, PlanningFact

class DynamicFactForm(forms.Form):
    """
    Builds its fields at __init__ by reading FactField config.
    """
    def __init__(self, *args, layout: PlanningLayout, instance: PlanningFact=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.layout   = layout
        self.instance = instance
        # load config
        for cfg in layout.fact_fields.all():
            field_name = cfg.name
            label      = cfg.label
            required   = cfg.required
            if cfg.field_type == 'char':
                fld = forms.CharField(label=label, required=required)
            elif cfg.field_type == 'int':
                fld = forms.IntegerField(label=label, required=required)
            elif cfg.field_type == 'dec':
                fld = forms.DecimalField(label=label, required=required)
            elif cfg.field_type == 'fk':
                ct   = cfg.content_type
                mdl  = ct.model_class()
                fld  = forms.ModelChoiceField(
                    label=label,
                    queryset=mdl.objects.all(),
                    required=required,
                    widget=autocomplete.ModelSelect2(url=f"{ct.app_label}-{ct.model}-autocomplete")
                )
            else:
                continue

            # pre-fill from instance
            if instance:
                val = getattr(instance, field_name, None)
                fld.initial = val

            self.fields[field_name] = fld

        # crispy layout
        self.helper = FormHelper(self)
        cols = []
        for cfg in layout.fact_fields.all():
            cols.append(Column(cfg.name, css_class="col-md-4"))
        self.helper.layout = Layout(
            Row(*cols),
            Submit('save','Save Fact'),
        )

    def save(self, request_obj):
        """
        Write values into a PlanningFact instance (new or existing).
        """
        inst = self.instance or PlanningFact(request=request_obj, area=None)
        for cfg in self.layout.fact_fields.all():
            name = cfg.name
            setattr(inst, name, self.cleaned_data[name])
        inst.area = self.cleaned_data.get('area') or inst.area
        inst.save()
        return inst

	•	You pass in layout= to tell it “which config to use”
	•	It loops layout.fact_fields, builds matching Django fields
	•	FK fields get an autocomplete widget (you’ll wire up the URL in urls.py)
	•	Crispy-Forms arranges them in rows of three columns

⸻

4. planning/views.py

from django.shortcuts import render, get_object_or_404, redirect
from .models import DataRequest, PlanningFact, PlanningLayout
from .forms  import DynamicFactForm

def fact_list(request, request_id, layout_id):
    dr     = get_object_or_404(DataRequest, pk=request_id)
    layout = get_object_or_404(PlanningLayout, pk=layout_id)

    if request.method == 'POST':
        form = DynamicFactForm(request.POST, layout=layout)
        if form.is_valid():
            form.save(request_obj=dr)
            return redirect(request.path_info)
    else:
        # editing the first fact as an example
        inst = dr.facts.filter(layout=layout).first()
        form = DynamicFactForm(layout=layout, instance=inst)

    facts = dr.facts.filter(layout=layout)
    return render(request, 'planning/fact_dynamic.html',{
        'form': form, 'facts': facts, 'layout': layout, 'dr': dr
    })


⸻

5. planning/templates/planning/fact_dynamic.html

{% extends "base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<h1>Facts ({{ layout.name }}) for {{ dr }}</h1>

<form method="post" class="mb-4">{% csrf_token %}
  {{ form|crispy }}
</form>

<table class="table table-striped">
  <thead>
    <tr>
      {% for cfg in layout.fact_fields.all %}
        <th>{{ cfg.label }}</th>
      {% endfor %}
      <th>Value</th>
    </tr>
  </thead>
  <tbody>
    {% for f in facts %}
      <tr>
        {% for cfg in layout.fact_fields.all %}
          <td>{{ f|attr:cfg.name }}</td>
        {% endfor %}
        <td>{{ f.value }}</td>
      </tr>
    {% endfor %}
  </tbody>
</table>

<script src="https://unpkg.com/vue@3"></script>
<script>
// If you need any fancy Vue bits—e.g. dynamic row addition—bootstrap it here.
</script>
{% endblock %}

	•	The table header comes from the same layout.fact_fields list, so you never hard‐code columns
	•	The form and the grid stay in sync automatically

⸻

Wiring up Autocomplete URLs

In your urls.py, add patterns like:

from dal import autocomplete
from planning.models import Year

urlpatterns = [
    path('year-autocomplete/',
         autocomplete.Select2QuerySetView.as_view(model=Year)),
    # and similarly for other InfoObjects...
]


⸻

Summary
	1.	FactField model drives every form field and grid column
	2.	DynamicFactForm builds itself off FactField rows in the DB
	3.	Templates loop the same config to render headers & values
	4.	Admin lets you add/remove/reorder FactFields without touching code
	5.	Autocomplete-light & Crispy-Forms give a polished UI
	6.	Vue stub in place for any additional client-side enhancements

Now your Fact entry form/layout is 100% configurable at runtime. Any change to FactField records immediately shows up in the UI—no code deploy required!