# bps/views.py
from uuid import UUID
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

from .models import (
    Year, PlanningLayoutYear, 
    PlanningSession, PlanningFunction, ReferenceData, DataRequest, PlanningFact,
    PeriodGrouping,
    Constant, SubFormula, Formula, FormulaRun
)
from .forms  import (
    PlanningSessionForm, PeriodSelector, ConstantForm, SubFormulaForm,
    FormulaForm, FactForm, PlanningFunctionForm, ReferenceDataForm
)
from .formula_executor import FormulaExecutor
from django.forms import modelform_factory

from django.shortcuts import render
from django.urls import reverse

# Dummy Inbox View
def inbox(request):
    # Breadcrumbs for navigation
    breadcrumbs = [
        {'url': reverse('bps:dashboard'), 'title': 'Dashboard'},
        {'url': request.path, 'title': 'Inbox'},
    ]
    # TODO: Replace with real inbox items
    items = []  
    return render(request, 'bps/inbox.html', {
        'breadcrumbs': breadcrumbs,
        'items': items,
    })

def profile(request):
    return ""

# Dummy Notifications View
def notifications(request):
    # Breadcrumbs for navigation
    breadcrumbs = [
        {'url': reverse('bps:dashboard'), 'title': 'Dashboard'},
        {'url': request.path, 'title': 'Notifications'},
    ]
    # TODO: Replace with real notifications
    notifications_list = []
    return render(request, 'bps/notifications.html', {
        'breadcrumbs': breadcrumbs,
        'notifications': notifications_list,
    })

def dashboard(request):
    # 1) Determine selected year (default = next calendar year)
    current_year = timezone.now().year
    all_years = Year.objects.order_by('code').values_list('code', flat=True)
    selected_year = request.GET.get('year', str(current_year + 1))
    if selected_year not in all_years:
        selected_year = all_years[-1] if all_years else str(current_year)

    # 2) Layouts for that year
    layouts = PlanningLayoutYear.objects.filter(year__code=selected_year).select_related('layout','version')

    # 3) Incomplete sessions (status = DRAFT) for that year
    incomplete_sessions = PlanningSession.objects.filter(
        layout_year__year__code=selected_year,
        status=PlanningSession.Status.DRAFT
    ).select_related('org_unit','layout_year').order_by('org_unit__name')

    # 4) Quick links for planning tasks (for planning users)
    planning_funcs = [
        {'name': 'Inbox',                  'url': reverse('bps:inbox')},
        {'name': 'Notifications',          'url': reverse('bps:notifications')},
        {'name': 'Start New Session',      'url': reverse('bps:session_list')},
        {'name': 'Run All Formulas',       'url': reverse('bps:formula_list')},
        {'name': 'Create Reference Data',  'url': reverse('bps:reference_data_list')},
    ]
    # 5) Admin links (Planning Administrators)
    admin_links = [
        {'name': 'Layouts',        'url': reverse('admin:bps_planninglayout_changelist')},
        {'name': 'Layout-Years',   'url': reverse('admin:bps_planninglayoutyear_changelist')},
        {'name': 'Periods',        'url': reverse('admin:bps_period_changelist')},
        {'name': 'Sessions',       'url': reverse('admin:bps_planningsession_changelist')},
        {'name': 'Data Requests',  'url': reverse('admin:bps_datarequest_changelist')},
        {'name': 'Constants',      'url': reverse('bps:constant_list')},
        {'name': 'SubFormulas',    'url': reverse('bps:subformula_list')},
        {'name': 'Formulas',       'url': reverse('bps:formula_list')},
        {'name': 'Functions',      'url': reverse('bps:planning_function_list')},
        {'name': 'Rate Cards',     'url': reverse('admin:bps_ratecard_changelist')},
        {'name': 'Positions',      'url': reverse('admin:bps_position_changelist')},
    ]

    return render(request, 'bps/dashboard.html', {
        'all_years': all_years,
        'selected_year': selected_year,
        'layouts': layouts,
        'incomplete_sessions': incomplete_sessions,
        'planning_funcs': planning_funcs,
        'admin_links': admin_links,
    })

def session_list(request):
    sessions = PlanningSession.objects.all().order_by('-created_at')
    return render(request,'bps/session_list.html',{'sessions':sessions})

def session_detail(request, pk):
    sess = get_object_or_404(PlanningSession, pk=pk)
    can_edit = sess.can_edit(request.user)
    # start planning: create first DataRequest
    if request.method=='POST' and 'start' in request.POST:
        form = PlanningSessionForm(request.POST)
        if form.is_valid():
            sess = form.save(commit=False)
            sess.created_by = request.user
            sess.save()
            messages.success(request,"Session started")
            return redirect('session_detail',sess.pk)
    else:
        form = PlanningSessionForm(instance=sess)

    # pick period grouping
    if request.method=='POST' and 'apply' in request.POST:
        ps = PeriodSelector(request.POST, session=sess)
        if ps.is_valid():
            grouping = ps.cleaned_data['grouping']
            request.session['grouping_id'] = grouping.pk
            return redirect('session_detail',sess.pk)
    else:
        ps = PeriodSelector(session=sess)

    # get the chosen grouping
    grouping = None
    if request.session.get('grouping_id'):
        grouping = PeriodGrouping.objects.get(pk=request.session['grouping_id'])
    periods = grouping.buckets() if grouping else []

    # facts for the very latest request
    dr = sess.requests.order_by('-created_at').first()
    facts = dr.planningfact_set.all() if dr else []

    # Serialize facts for Handsontable
    import json
    from django.utils.safestring import mark_safe

    # simple rows: [PeriodName, KeyFigureCode, Value]
    hot_rows = [
        [str(f.period), f.key_figure.code, float(f.value)]
        for f in facts
    ]
    hot_data = mark_safe(json.dumps(hot_rows))

    return render(request,'bps/session_detail.html',{
        'sess': sess, 'form': form,
        'can_edit': can_edit,
        'period_form': ps, 'periods': periods,
        'facts': facts, 'dr': dr,
        'hot_data': hot_data,
        'can_edit': can_edit,
    })

# ── Constants ──────────────────────────────────────────────────────────────

def constant_list(request):
    if request.method == 'POST':
        form = ConstantForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Constant saved.")
            return redirect('constant_list')
    else:
        form = ConstantForm()
    consts = Constant.objects.all()
    return render(request, 'bps/constant_list.html', {'form': form, 'consts': consts})


# ── SubFormulas ───────────────────────────────────────────────────────────

def subformula_list(request):
    if request.method == 'POST':
        form = SubFormulaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "SubFormula saved.")
            return redirect('subformula_list')
    else:
        form = SubFormulaForm()
    subs = SubFormula.objects.all()
    return render(request, 'bps/subformula_list.html', {'form': form, 'subs': subs})


# ── Formulas ───────────────────────────────────────────────────────────────

def formula_list(request):
    if request.method == 'POST':
        form = FormulaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Formula saved.")
            return redirect('formula_list')
    else:
        form = FormulaForm()
    formulas = Formula.objects.all()
    return render(request, 'bps/formula_list.html', {'form': form, 'formulas': formulas})


# ── Run Formula ────────────────────────────────────────────────────────────

def formula_run(request, pk):
    formula = get_object_or_404(Formula, pk=pk)
    # NOTE: you'll need to supply session and period, perhaps via GET or a small form
    session = request.user.planningsession_set.filter(status='D').first()
    period  = request.GET.get('period', '01')

    executor = FormulaExecutor(formula, session, period, preview=False)
    entries = executor.execute()
    messages.success(request, f"Executed {formula.name}, {entries.count()} entries updated.")
    return redirect(reverse('formula_list'))

# ── Planning Functions ─────────────────────────────────────────────────────
def planning_function_list(request):
    if request.method == 'POST':
        form = PlanningFunctionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Planning Function saved.")
            return redirect('bps:planning_function_list')
    else:
        form = PlanningFunctionForm()
    functions = PlanningFunction.objects.all()
    return render(request, 'bps/planning_function_list.html', {
        'form': form, 'functions': functions
    })

def run_planning_function(request, pk, session_id):
    func = get_object_or_404(PlanningFunction, pk=pk)
    session = get_object_or_404(PlanningSession, pk=session_id)
    result = func.execute(session)
    messages.success(
        request,
        f"{func.get_function_type_display()} executed, result: {result}"
    )
    return redirect('bps:session_detail', pk=session_id)

# ── Reference Data ─────────────────────────────────────────────────────────
def reference_data_list(request):
    if request.method == 'POST':
        form = ReferenceDataForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Reference Data saved.")
            return redirect('bps:reference_data_list')
    else:
        form = ReferenceDataForm()
    refs = ReferenceData.objects.all()
    return render(request, 'bps/reference_data_list.html', {
        'form': form, 'references': refs
    })

# If you need a simple ModelForm for DataRequest:
DataRequestForm = modelform_factory(DataRequest, fields=['description'])


def data_request_list(request):
    """
    List all DataRequests with links to their detail pages.
    """
    requests = DataRequest.objects.order_by('-created_at')
    return render(request, "bps/data_request_list.html", {
        "data_requests": requests
    })


def data_request_detail(request, pk: UUID):
    """
    View/edit a single DataRequest (just its description),
    plus inline list of its PlanningFact records.
    """
    dr = get_object_or_404(DataRequest, pk=pk)
    if request.method == 'POST':
        form = DataRequestForm(request.POST, instance=dr)
        if form.is_valid():
            form.save()
            messages.success(request, "DataRequest updated.")
            return redirect("bps:data_request_detail", pk=pk)
    else:
        form = DataRequestForm(instance=dr)

    facts = dr.planningfact_set.order_by('period')
    return render(request, "bps/data_request_detail.html", {
        "dr": dr,
        "form": form,
        "facts": facts,
    })


def fact_list(request, request_id: UUID):
    dr = get_object_or_404(DataRequest, pk=request_id)
    if request.method == 'POST':
        form = FactForm(request.POST)
        if form.is_valid():
            fact = form.save(commit=False)
            fact.request = dr
            fact.session = dr.session
            fact.save()
            messages.success(request, "PlanningFact added.")
            return redirect("bps:fact_list", request_id=request_id)
    else:
        form = FactForm()
    facts = dr.planningfact_set.order_by('period')
    return render(request, "bps/fact_list.html", {
        "dr": dr, "form": form, "facts": facts
    })


def variable_list(request):
    """
    List and create “global” variables (Constants).
    """
    if request.method == 'POST':
        form = ConstantForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Global variable saved.")
            return redirect("bps:variable_list")
    else:
        form = ConstantForm()

    consts = Constant.objects.order_by('name')
    return render(request, "bps/variable_list.html", {
        "form": form,
        "consts": consts,
    })

def run_planning_function(request, pk, session_id):
    """
    URL: /functions/run/<pk>/?session=<sid>
    """
    func = get_object_or_404(PlanningFunction, pk=pk)
    session = get_object_or_404(PlanningSession, pk=session_id)
    count_or_result = func.execute(session)
    messages.success(
        request,
        f"{func.get_function_type_display()} executed, result: {count_or_result}"
    )
    return redirect('bps:session_detail', pk=session_id)

def copy_actual(request):
    # TODO: wire this up to your actual “Copy Actual → Plan” logic
    messages.info(request, "Copy Actual → Plan is not yet implemented.")
    return redirect('bps:dashboard')

def distribute_key(request):
    # TODO: wire this up to your actual “Distribute by Key” logic
    messages.info(request, "Distribute by Key is not yet implemented.")
    return redirect('bps:dashboard')