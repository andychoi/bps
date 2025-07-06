# bps/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import (
    PlanningSession, DataRequest, PlanningFact,
    PeriodGrouping
)
from .forms  import PlanningSessionForm, PeriodSelector

def session_list(request):
    sessions = PlanningSession.objects.all().order_by('-created_at')
    return render(request,'bps/session_list.html',{'sessions':sessions})

def session_detail(request, pk):
    sess = get_object_or_404(PlanningSession, pk=pk)

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
    facts = dr.facts.all() if dr else []

    return render(request,'bps/session_detail.html',{
        'sess': sess, 'form': form,
        'period_form': ps, 'periods': periods,
        'facts': facts, 'dr': dr
    })
