# bps/views_planner.py
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from ..access import allowed_orgunits_qs, is_enterprise_planner, set_acting_as, clear_acting_as, get_effective_delegator, can_act_as
from ..models.models_access import Delegation
from ..models.models_dimension import OrgUnit

User = get_user_model()

@method_decorator(login_required, name="dispatch")
class PlannerDashboard(View):
    template_name = "bps/planner/dashboard.html"

    def get(self, request):
        allowed_qs = allowed_orgunits_qs(request.user, request)
        effective_delegator = get_effective_delegator(request)
        delegations = Delegation.objects.filter(delegatee=request.user, active=True)

        ctx = {
            "is_enterprise": is_enterprise_planner(request.user),
            "effective_delegator": effective_delegator,
            "delegations": delegations.select_related("delegator"),
            "allowed_ous": allowed_qs.order_by("name"),
        }
        return render(request, self.template_name, ctx)

@login_required
def act_as_start(request, user_id):
    delegator = get_object_or_404(User, pk=user_id)
    d = can_act_as(request.user, delegator)
    if not (d and d.is_active()):
        return HttpResponseForbidden("No active delegation from this user.")
    set_acting_as(request, delegator)
    return HttpResponseRedirect("/planner/")

@login_required
def act_as_stop(request):
    clear_acting_as(request)
    return HttpResponseRedirect("/planner/")

@login_required
def api_allowed_ous(request):
    qs = allowed_orgunits_qs(request.user, request).order_by("name")
    data = [{"id": ou.id, "code": ou.code, "name": ou.name, "path": ou.get_path() if hasattr(ou, "get_path") else ou.name} for ou in qs]
    return JsonResponse({"results": data})