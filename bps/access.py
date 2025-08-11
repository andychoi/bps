# bps/access.py
from django.contrib.auth.models import Group
from django.db.models import Q
from .models.models_access import OrgUnitAccess, Delegation
from .models.models_dimension import OrgUnit

ENTERPRISE_GROUP = "Enterprise Planner"
SESSION_ACTING_AS = "bps_acting_as_user_id"

def is_enterprise_planner(user):
    return user.is_superuser or user.groups.filter(name=ENTERPRISE_GROUP).exists()

def get_effective_delegator(request):
    """Return a User instance we are 'acting as' (delegator), or None."""
    uid = request.session.get(SESSION_ACTING_AS)
    if not uid:
        return None
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        return User.objects.get(pk=uid)
    except User.DoesNotExist:
        return None

def can_act_as(user, delegator):
    """Does delegator delegate to user, and is it active?"""
    return Delegation.objects.filter(delegatee=user, delegator=delegator).first()

def set_acting_as(request, delegator):
    request.session[SESSION_ACTING_AS] = delegator.pk

def clear_acting_as(request):
    request.session.pop(SESSION_ACTING_AS, None)

def allowed_orgunits_qs(user, request=None):
    """Compute allowed OU queryset for the current user, considering enterprise and delegation."""
    # Enterprise → full tree
    if is_enterprise_planner(user):
        return OrgUnit.objects.all()

    # Delegation: replace scope with delegator's scope (not union)
    delegator = get_effective_delegator(request) if request else None
    effective_user = delegator if (delegator and can_act_as(user, delegator) and can_act_as(user, delegator).is_active()) else user

    grants = OrgUnitAccess.objects.filter(user=effective_user).select_related("org_unit")
    if not grants.exists():
        return OrgUnit.objects.none()

    ids = set()
    for g in grants:
        if g.scope == OrgUnitAccess.SUBTREE:
            ids.update(g.org_unit.get_descendants(include_self=True).values_list("id", flat=True))
        else:
            ids.add(g.org_unit_id)

    return OrgUnit.objects.filter(id__in=list(ids))

def can_edit_ou(user, ou, request=None):
    if is_enterprise_planner(user):
        return True
    # when acting-as, evaluate delegator's grants
    allowed = allowed_orgunits_qs(user, request).filter(pk=ou.pk).exists()
    if not allowed:
        return False
    # check edit bit
    grants = OrgUnitAccess.objects.filter(user=user, org_unit__in=[ou] + list(ou.get_ancestors())).order_by("-org_unit__level")
    return any(g.can_edit for g in grants)