# views.py
from uuid import UUID
import json

from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.contrib import messages
from django.views import View
from django.views.generic import (
    TemplateView, ListView, DetailView,
    FormView, RedirectView
)
from django.views.generic.edit import FormMixin
from django.forms import modelform_factory
from bps.models.models_workflow import ScenarioStep  
from ..models.models import (
    PlanningScenario, PlanningSession, PlanningStage, PlanningLayoutYear,
    PlanningLayout, Year, Version, Period,
    PlanningFact, DataRequest, Constant, SubFormula,
    Formula, PlanningFunction, ReferenceData
)
from .forms import (
    PlanningSessionForm, PeriodSelector, ConstantForm,
    SubFormulaForm, FormulaForm, FactForm,
    PlanningFunctionForm, ReferenceDataForm
)
from .formula_executor import FormulaExecutor


# ── Dashboard & Basic Pages ────────────────────────────────────────────────
class ScenarioDashboardView(TemplateView):
    template_name = "bps/scenario_dashboard.html"

    def get_context_data(self, **kwargs):
        scenario = get_object_or_404(PlanningScenario, code=kwargs["code"])
        # Now each session is tied to scenario, not a layout_year
        sessions = PlanningSession.objects.filter(
            scenario=scenario
        ).select_related("org_unit", "current_step__stage", "current_step__layout")
        steps = ScenarioStep.objects.filter(scenario=scenario)\
                    .select_related("stage","layout").order_by("order")
        return {
            "scenario":   scenario,
            "sessions":   sessions,
            "steps":      steps,
            "org_units":  scenario.org_units.all(),
        }
    
class DashboardView(TemplateView):
    template_name = 'bps/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().year
        all_years = Year.objects.order_by('code').values_list('code', flat=True)
        selected_year = self.request.GET.get('year', str(current_year + 1))
        if selected_year not in all_years:
            selected_year = all_years[-1] if all_years else str(current_year)

        ctx.update({
            'all_years': all_years,
            'selected_year': selected_year,
            'layouts': PlanningLayoutYear.objects.filter(
                year__code=selected_year
            ).select_related('layout','version'),
            'incomplete_sessions': PlanningSession.objects.filter(
                status=PlanningSession.Status.DRAFT
            )
            # join the FK to scenario, then its FK to layout_year,
            # plus the org_unit itself
            .select_related(
               'org_unit',
               'scenario__layout_year__layout',
               'scenario__layout_year__version'
            )
            .order_by('org_unit__name'),
            'planning_funcs': [
                {'name': 'Inbox', 'url': reverse('bps:inbox')},
                {'name': 'Notifications', 'url': reverse('bps:notifications')},
                {'name': 'Start New Session', 'url': reverse('bps:session_list')},
                {'name': 'Run All Formulas', 'url': reverse('bps:formula_list')},
                {'name': 'Create Reference Data', 'url': reverse('bps:reference_data_list')},
            ],
            'admin_links': [
                {'name': 'Layouts', 'url': reverse('admin:bps_planninglayout_changelist')},
                {'name': 'Layout-Years', 'url': reverse('admin:bps_planninglayoutyear_changelist')},
                {'name': 'Periods', 'url': reverse('admin:bps_period_changelist')},
                {'name': 'Sessions', 'url': reverse('admin:bps_planningsession_changelist')},
                {'name': 'Data Requests', 'url': reverse('admin:bps_datarequest_changelist')},
                {'name': 'Constants', 'url': reverse('bps:constant_list')},
                {'name': 'SubFormulas', 'url': reverse('bps:subformula_list')},
                {'name': 'Formulas', 'url': reverse('bps:formula_list')},
                {'name': 'Functions', 'url': reverse('bps:planning_function_list')},
                {'name': 'Rate Cards', 'url': reverse('admin:bps_ratecard_changelist')},
                {'name': 'Positions', 'url': reverse('admin:bps_position_changelist')},
            ],
        })
        return ctx


class ProfileView(View):
    def get(self, request):
        # stub for future profile page
        return HttpResponse('')


class InboxView(TemplateView):
    template_name = 'bps/inbox.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['breadcrumbs'] = [
            {'url': reverse('bps:dashboard'), 'title': 'Dashboard'},
            {'url': self.request.path,    'title': 'Inbox'},
        ]
        ctx['items'] = []
        return ctx


class NotificationsView(TemplateView):
    template_name = 'bps/notifications.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['breadcrumbs'] = [
            {'url': reverse('bps:dashboard'), 'title': 'Dashboard'},
            {'url': self.request.path,        'title': 'Notifications'},
        ]
        ctx['notifications'] = []
        return ctx


# ── Manual Planning ─────────────────────────────────────────────────────────

class ManualPlanningSelectView(TemplateView):
    template_name = "bps/manual_planning_select.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["layouts"] = PlanningLayoutYear.objects.select_related(
            "layout", "year", "version"
        )
        return ctx

# ── Planning Sessions ───────────────────────────────────────────────────────

class PlanningSessionListView(ListView):
    model = PlanningSession
    template_name = 'bps/session_list.html'
    context_object_name = 'sessions'
    ordering = ['-created_at']
    paginate_by = 50


class PlanningSessionDetailView(FormMixin, DetailView):
    """
    Displays a single PlanningSession, bound to a ScenarioStep.
    Allows:
      - Starting (assigning created_by)
      - Applying period‐grouping
      - Viewing raw facts for the current step/layout
      - Advancing to the next step
    """
    model = PlanningSession
    template_name = "bps/session_detail.html"
    context_object_name = "sess"
    form_class = PlanningSessionForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # bind the form to the existing session instance
        kwargs["instance"] = self.get_object()
        return kwargs

    def get_context_data(self, **ctx):
        sess   = self.object
        # 1) grab the current step & stage
        step   = sess.current_step
        stage  = step.stage

        # 2) session + layout metadata
        ly      = sess.layout_year
        layout  = ly.layout
        version = ly.version

        # 3) pick the MONTHLY grouping by default
        grouping = ly.period_groupings.filter(months_per_bucket=1).first()
        buckets  = grouping.buckets()

        # 4) build your “driver” dimensions (rows)
        drivers = []
        for ld in ly.layout_dimensions.filter(is_row=True).order_by('order'):
            Model = ld.content_type.model_class()
            qs    = Model.objects.filter(pk__in=ld.allowed_values) \
                    if ld.allowed_values else Model.objects.all()
            drivers.append({
                "key":     ld.content_type.model,
                "label":   ld.content_type.model.title(),
                "choices": [{"id":o.pk,"name":str(o)} for o in qs],
            })

        # 5) pull out the key-figure codes in layout order
        kf_codes = [kf.code for kf in layout.key_figures.all()]

        # 6) compute your pivot API URL
        from django.urls import reverse
        api_url = reverse('bps_api:planning_pivot')

        # 7) leave the old raw‐facts in case you still need them
        dr    = sess.requests.order_by('-created_at').first()
        facts = sess.planningfact_set.filter(request=dr) if dr else []

        ctx = super().get_context_data(**ctx)
        ctx.update({
            "sess":         sess,
            "current_step": step,
            "stage":        stage,
            "layout":       layout,
            "dr":           dr,
            "facts":        facts,
            "buckets":      buckets,
            "drivers":      drivers,
            "kf_codes":     kf_codes,
            "api_url":      api_url,
            "can_edit":     sess.can_edit(self.request.user),
            "form":         self.get_form(),
            "breadcrumbs": [
                {"url": reverse("bps:dashboard"),    "title": "Dashboard"},
                {"url": reverse("bps:session_list"), "title": "Sessions"},
                {"url": self.request.path,           "title": sess.org_unit.name},
            ],
            "can_advance":  self.request.user.is_staff and sess.scenario.steps.filter(order__gt=step.order).exists(),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        sess = self.object

        # Start the session (set created_by)
        if "start" in request.POST:
            form = PlanningSessionForm(request.POST, instance=sess)
            if form.is_valid():
                sess = form.save(commit=False)
                sess.created_by = request.user
                sess.save()
                messages.success(request, "Session started.")
                return redirect("bps:session_detail", pk=sess.pk)

        # Apply a new period‐grouping
        if "apply" in request.POST:
            ps = PeriodSelector(request.POST, session=sess)
            if ps.is_valid():
                request.session["grouping_id"] = ps.cleaned_data["grouping"].pk
                return redirect("bps:session_detail", pk=sess.pk)

        return self.get(request, *args, **kwargs)


class AdvanceStepView(View):
    """
    Move the session to the next ScenarioStep in order.
    """
    def post(self, request, session_id):
        from bps.models.models_workflow import ScenarioStep
        sess = get_object_or_404(PlanningSession, pk=session_id)
        current_order = sess.current_step.order
        next_step = ScenarioStep.objects.filter(scenario=sess.scenario, order__gt=current_order).order_by("order").first()

        if not next_step:
            messages.warning(request, "Already at final step.")
        else:
            sess.current_step = next_step
            sess.save(update_fields=["current_step"])
            messages.success(request, f"Advanced to step: {next_step.stage.name}")

        return redirect("bps:session_detail", pk=session_id)


class AdvanceStageView(View):
    def get(self, request, session_id):
        sess = get_object_or_404(PlanningSession, pk=session_id)
        next_stage = PlanningStage.objects.filter(
            order__gt=sess.current_stage.order
        ).order_by('order').first()

        if not next_stage:
            messages.warning(request, "Already at final stage.")
        else:
            sess.current_stage = next_stage
            sess.save(update_fields=['current_stage'])
            messages.success(request, f"Moved to stage: {next_stage.name}")

        return redirect('bps:session_detail', pk=session_id)


# ── Constants, Sub-Formulas & Formulas ───────────────────────────────────────

class ConstantListView(FormMixin, ListView):
    model = Constant
    template_name = 'bps/constant_list.html'
    context_object_name = 'consts'
    form_class = ConstantForm
    success_url = reverse_lazy('bps:constant_list')

    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "Constant saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)


class SubFormulaListView(FormMixin, ListView):
    model = SubFormula
    template_name = 'bps/subformula_list.html'
    context_object_name = 'subs'
    form_class = SubFormulaForm
    success_url = reverse_lazy('bps:subformula_list')

    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "SubFormula saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)


class FormulaListView(FormMixin, ListView):
    model = Formula
    template_name = 'bps/formula_list.html'
    context_object_name = 'formulas'
    form_class = FormulaForm
    success_url = reverse_lazy('bps:formula_list')

    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "Formula saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)


class FormulaRunView(View):
    def get(self, request, pk):
        formula = get_object_or_404(Formula, pk=pk)
        session = request.user.planningsession_set.filter(
            status=PlanningSession.Status.DRAFT
        ).first()
        period = request.GET.get('period', '01')
        entries = FormulaExecutor(formula, session, period, preview=False).execute()
        messages.success(
            request,
            f"Executed {formula.name}, {entries.count()} entries updated."
        )
        return redirect('bps:formula_list')


# ── Planning Functions ──────────────────────────────────────────────────────

class PlanningFunctionListView(FormMixin, ListView):
    model = PlanningFunction
    template_name = 'bps/planning_function_list.html'
    context_object_name = 'functions'
    form_class = PlanningFunctionForm
    success_url = reverse_lazy('bps:planning_function_list')

    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "Planning Function saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)


class RunPlanningFunctionView(View):
    def get(self, request, pk, session_id):
        func = get_object_or_404(PlanningFunction, pk=pk)
        session = get_object_or_404(PlanningSession, pk=session_id)
        result = func.execute(session)
        messages.success(
            request,
            f"{func.get_function_type_display()} executed, result: {result}"
        )
        return redirect('bps:session_detail', pk=session_id)


class CopyActualView(View):
    def get(self, request):
        messages.info(request, "Copy Actual → Plan is not yet implemented.")
        return redirect('bps:dashboard')


class DistributeKeyView(View):
    def get(self, request):
        messages.info(request, "Distribute by Key is not yet implemented.")
        return redirect('bps:dashboard')


# ── Reference Data ───────────────────────────────────────────────────────────

class ReferenceDataListView(FormMixin, ListView):
    model = ReferenceData
    template_name = 'bps/reference_data_list.html'
    context_object_name = 'references'
    form_class = ReferenceDataForm
    success_url = reverse_lazy('bps:reference_data_list')

    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "Reference Data saved.")
            return redirect(self.success_url)
        return self.form_invalid(form)


# ── Data Requests & Facts ────────────────────────────────────────────────────

DataRequestForm = modelform_factory(DataRequest, fields=['description'])


class DataRequestListView(ListView):
    model = DataRequest
    template_name = 'bps/data_request_list.html'
    context_object_name = 'data_requests'
    ordering = ['-created_at']


class DataRequestDetailView(FormMixin, DetailView):
    model = DataRequest
    template_name = 'bps/data_request_detail.html'
    context_object_name = 'dr'
    form_class = DataRequestForm

    def get_success_url(self):
        return reverse_lazy('bps:data_request_detail', kwargs={'pk': self.object.pk})

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, "DataRequest updated.")
            return redirect(self.get_success_url())
        return self.form_invalid(form)


class FactListView(FormMixin, ListView):
    template_name = 'bps/fact_list.html'
    context_object_name = 'facts'
    form_class = FactForm

    def get_queryset(self):
        return PlanningFact.objects.filter(
            request__pk=self.kwargs['request_id']
        ).order_by('period')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['dr'] = get_object_or_404(DataRequest, pk=self.kwargs['request_id'])
        return ctx

    def get_success_url(self):
        return reverse_lazy('bps:fact_list', kwargs={'request_id': self.kwargs['request_id']})

    def post(self, request, *args, **kwargs):
        dr = get_object_or_404(DataRequest, pk=self.kwargs['request_id'])
        form = self.get_form()
        if form.is_valid():
            fact = form.save(commit=False)
            fact.request = dr
            fact.session = dr.session
            fact.save()
            messages.success(request, "PlanningFact added.")
            return redirect(self.get_success_url())
        return self.form_invalid(form)


# ── Global Variables ───────────────────────────────────────────────────────

class VariableListView(ConstantListView):
    template_name = 'bps/variable_list.html'
    success_url = reverse_lazy('bps:variable_list')