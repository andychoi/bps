#. views/manual_planning.py
from django.views.generic import TemplateView
from django.shortcuts import redirect, get_object_or_404
from bps.models import PlanningLayoutYear, Year, Version, Period

class ManualPlanningSelectView(TemplateView):
    template_name = 'bps/manual_planning_select.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['layouts'] = PlanningLayoutYear.objects.select_related('layout','year','version')
        return ctx

class ManualPlanningView(TemplateView):
    template_name = 'bps/manual_planning.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        layout_id  = self.kwargs.get('layout_id')
        year_id    = self.kwargs.get('year_id')
        version_id = self.kwargs.get('version_id')

        if not (layout_id and year_id and version_id):
            # no args → redirect to selector
            return redirect('bps:manual-planning-select')

        ly = get_object_or_404(
            PlanningLayoutYear,
            layout_id=layout_id,
            year_id=year_id,
            version_id=version_id
        )

        ctx.update({
            'layout_year': ly,
            'layout':      ly.layout,
            'year':        ly.year,
            'version':     ly.version,
            'periods':     Period.objects.order_by('order'),
        })
        return ctx