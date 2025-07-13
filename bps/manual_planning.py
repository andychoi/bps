from django.views.generic import TemplateView
from bps.models import PlanningLayoutYear

class ManualPlanningView(TemplateView):
    template_name = "bps/manual_planning.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["layouts"] = PlanningLayoutYear.objects.select_related("layout", "year", "version")
        ctx["selected_layout"] = self.request.GET.get("layout_year")
        return ctx