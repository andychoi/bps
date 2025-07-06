Below is a full approach to letting each PlanningLayout definition declare subtotals and/or a grand‐total row for any of its lead dimensions—so that your bps screen will automatically show the grouped sums you sketched in your graphics.

⸻

1. Data-Model Changes

A. Flag your lead dimensions for subtotal or total

Extend your PlanningLayoutLeadDimension through-table so each dimension can carry flags:

# bps/models.py

from django.db import models
from django.contrib.contenttypes.fields import ContentType

class PlanningLayout(models.Model):
    name             = models.CharField(max_length=100)
    lead_dimensions  = models.ManyToManyField(
        ContentType,
        through='PlanningLayoutLeadDimension',
        related_name='lead_dimensions'
    )
    column_dimension = models.ForeignKey(
        ContentType,
        null=True,
        on_delete=models.SET_NULL,
        related_name='column_dimension'
    )
    key_figures      = models.JSONField(default=list)

    def __str__(self):
        return self.name


class PlanningLayoutLeadDimension(models.Model):
    bpslayout = models.ForeignKey(PlanningLayout, on_delete=models.CASCADE)
    contenttype    = models.ForeignKey(ContentType,    on_delete=models.CASCADE)
    order          = models.PositiveIntegerField(default=0)

    # NEW:
    subtotal_after = models.BooleanField(
        default=False,
        help_text="When true, after each group of this dimension emit a subtotal row."
    )
    show_grand_total = models.BooleanField(
        default=False,
        help_text="When true, show one final total row over ALL values at the end."
    )

    class Meta:
        unique_together = ('bpslayout', 'contenttype')
        ordering = ('bpslayout', 'order')

    def __str__(self):
        return f"{self.bpslayout.name} → {self.contenttype.model}"

	1.	subtotal_after: if checked, you’ll get a subtotal row after each break in that dimension.
	2.	show_grand_total: if checked on any lead dimension, you’ll render exactly one “All …” row at the bottom.

Run your migrations:

python manage.py makemigrations bps
python manage.py migrate


⸻

2. Admin Configuration

Wire up the new flags so you can tick them in Django Admin:

# bps/admin.py

from django.contrib import admin
from .models import PlanningLayout, PlanningLayoutLeadDimension

class PlanningLayoutLeadDimensionInline(admin.TabularInline):
    model = PlanningLayoutLeadDimension
    extra = 1
    fields = (
        'contenttype', 'order',
        'subtotal_after', 'show_grand_total',
    )
    verbose_name = "Lead Dimension"
    verbose_name_plural = "Lead Dimensions"

@admin.register(PlanningLayout)
class PlanningLayoutAdmin(admin.ModelAdmin):
    list_display = ('name', 'column_dimension', 'key_figures')
    inlines     = [PlanningLayoutLeadDimensionInline]

Now when you edit a layout, you can:
	•	Reorder your dimensions
	•	Tick Subtotal after on e.g. “Company”
	•	Tick Show grand total on e.g. “Version” (or whichever dimension you choose)

⸻

3. View Logic: Building Rows + Subtotals

In your bps view, after you’ve fetched all PlanningRecord rows for this layout, you’ll do a multi-level grouping to insert subtotal rows.

# bps/views.py

from itertools import groupby
from django.db.models import Sum
from django.shortcuts import render, get_object_or_404
from .models import PlanningLayout, PlanningRecord

def bps_screen(request, layout_id):
    layout = get_object_or_404(PlanningLayout, pk=layout_id)
    # pull all records for this layout, annotated with each key_figure sum
    records = PlanningRecord.objects.filter(layout=layout)

    # load your lead-dimension CTs in order
    lead_defs = layout.bpslayoutleaddimension_set.all()

    # fetch raw rows into a list of dicts you can sort and group
    rows = []
    for rec in records:
        # build a dict of {dim_model_name: dim_value, ...}
        dims = {
            ct.contenttype.model: getattr(rec, 
                next(f.name for f in rec._meta.fields 
                     if getattr(f, 'related_model', None) == ct.contenttype.model_class())
            )
            for ct in lead_defs
        }
        # pull out each key-figure value
        for k in layout.key_figures:
            rows.append({
                **dims,
                'key_figure': k,
                'value': rec.key_figure_values.get(k, 0),
            })

    # sort rows by the lead-dimensions in order
    sort_keys = [ld.contenttype.model for ld in lead_defs]
    rows.sort(key=lambda r: tuple(r[k] for k in sort_keys))

    # helper to sum a list of rows
    def sum_group(group):
        return sum(r['value'] for r in group)

    # now walk through grouping levels and build output with subtotals
    output = []
    def recurse(level, current_rows):
        if level >= len(sort_keys):
            # bottom level: just append all rows
            output.extend(current_rows)
            return

        dim = sort_keys[level]
        subtotal_flag = lead_defs[level].subtotal_after

        # group by this dimension
        for dim_val, group in groupby(current_rows, key=lambda r: r[dim]):
            grp_list = list(group)
            # inside each subgroup, recurse to the next dimension
            recurse(level+1, grp_list)

            if subtotal_flag:
                # after the subgroup, append a subtotal row
                output.append({
                    **{dim: f"{dim_val} (subtotal)"},
                    'is_subtotal': True,
                    'value': sum_group(grp_list),
                    'key_figure': None,
                })

    recurse(0, rows)

    # grand total?
    if any(ld.show_grand_total for ld in lead_defs):
        output.append({
            **{d: "All" for d in sort_keys},
            'is_grand_total': True,
            'value': sum(r['value'] for r in rows),
            'key_figure': None,
        })

    return render(request, 'bps/screen.html', {
        'layout': layout,
        'rows': output,
        'lead_dims': sort_keys,
    })


⸻

4. Template: Rendering Data, Subtotals & Totals

{# bps/templates/bps/screen.html #}

<table class="table table-sm">
  <thead>
    <tr>
      {% for dim in lead_dims %}
        <th>{{ dim|capfirst }}</th>
      {% endfor %}
      <th>Key Figure</th>
      <th>Value</th>
    </tr>
  </thead>
  <tbody>
    {% for row in rows %}
      {% if row.is_grand_total %}
        <tr class="table-success fw-bold">
          {% for dim in lead_dims %}
            <td>{{ row.dim }}</td>
          {% endfor %}
          <td>Total</td>
          <td>{{ row.value }}</td>
        </tr>
      {% elif row.is_subtotal %}
        <tr class="table-secondary fst-italic">
          {% for dim in lead_dims %}
            <td>{{ row.dim }}</td>
          {% endfor %}
          <td>Subtotal</td>
          <td>{{ row.value }}</td>
        </tr>
      {% else %}
        <tr>
          {% for dim in lead_dims %}
            <td>{{ row[dim] }}</td>
          {% endfor %}
          <td>{{ row.key_figure }}</td>
          <td>{{ row.value }}</td>
        </tr>
      {% endif %}
    {% endfor %}
  </tbody>
</table>

	•	.table-secondary for subtotals,
	•	.table-success for the grand total.
	•	Rows without “subtotal” flags render normally.

⸻

5. Summary
	1.	Model: add subtotal_after & show_grand_total to PlanningLayoutLeadDimension.
	2.	Admin: expose those flags inline under each layout.
	3.	View: multi-level group your data rows, insert subtotal rows after the flagged dimension, then append a single grand-total if requested.
	4.	Template: detect row.is_subtotal/row.is_grand_total and render with special styling.

With this in place, each layout author can decide:
	•	Which dimension(s) get subtotals (“Company,” “Version,” etc.)
	•	Whether to show one All-rows grand total at the end

…all without any further code changes to your core bps screen.