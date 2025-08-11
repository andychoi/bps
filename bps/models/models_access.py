from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import Q

from .models_dimension import OrgUnit

User = settings.AUTH_USER_MODEL


class OrgUnitAccess(models.Model):
    """
    Grants a user access to an OrgUnit. If scope == SUBTREE, access includes the full subtree.
    This model is NOT a tree; OrgUnit is the tree (Treebeard MP_Node).
    
	•	OrgUnitAccess.scope_for_user(request.user) → queryset of allowed OUs
	•	OrgUnitAccess.can_edit_orgunit(request.user, ou) → boolean edit gate    
    """
    EXACT = "EXACT"
    SUBTREE = "SUBTREE"
    SCOPE_CHOICES = [(EXACT, "Exact"), (SUBTREE, "Subtree")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ou_access")
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.CASCADE, related_name="user_access")
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default=SUBTREE)
    can_edit = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "org_unit", "scope")

    def __str__(self):
        return f"{self.user} → {self.org_unit} [{self.scope}]"

    # ----- helpers ---------------------------------------------------------

    def units_qs(self):
        """
        OrgUnits this single access row grants.
        For SUBTREE, include the anchor OU + all descendants.
        """
        base = OrgUnit.objects.filter(pk=self.org_unit_id)
        if self.scope == self.SUBTREE:
            # treebeard: get_descendants() excludes self, so union with base
            return base.union(self.org_unit.get_descendants())
        return base

    @classmethod
    def scope_for_user(cls, user, *, include_delegations=True):
        """
        Returns a DISTINCT queryset of all OrgUnits the user can see,
        including active delegations (time-bounded) if requested.
        """
        qs = OrgUnit.objects.none()

        # direct access rows
        for access in cls.objects.filter(user=user).select_related("org_unit"):
            qs = qs.union(access.units_qs())

        if include_delegations:
            now = timezone.now()
            dels = Delegation.objects.filter(
                delegatee=user,
                active=True
            ).filter(
                Q(starts_at__isnull=True) | Q(starts_at__lte=now),
                Q(ends_at__isnull=True)   | Q(ends_at__gte=now),
            ).select_related("delegator")

            if dels.exists():
                delegator_ids = list(dels.values_list("delegator_id", flat=True))
                for access in cls.objects.filter(user_id__in=delegator_ids).select_related("org_unit"):
                    qs = qs.union(access.units_qs())

        return qs.distinct()

    @classmethod
    def can_edit_orgunit(cls, user, org_unit, *, include_delegations=True):
        """
        True if user (or any active delegator) has edit rights covering org_unit.
        - EXACT matches the org_unit directly
        - SUBTREE matches if org_unit is under (or equal to) the anchor OU
          (we check using ancestors of the target)
        """
        # ancestors of the target (include target) – used to match SUBTREE anchors
        anc_ids = list(org_unit.get_ancestors().values_list("id", flat=True)) + [org_unit.id]

        base = cls.objects.filter(user=user, can_edit=True).filter(
            Q(scope=cls.EXACT, org_unit_id=org_unit.id) |
            Q(scope=cls.SUBTREE, org_unit_id__in=anc_ids)
        )
        if base.exists():
            return True

        if include_delegations:
            now = timezone.now()
            delegator_ids = list(
                Delegation.objects.filter(
                    delegatee=user, active=True
                ).filter(
                    Q(starts_at__isnull=True) | Q(starts_at__lte=now),
                    Q(ends_at__isnull=True)   | Q(ends_at__gte=now),
                ).values_list("delegator_id", flat=True)
            )
            if delegator_ids:
                via_del = cls.objects.filter(user_id__in=delegator_ids, can_edit=True).filter(
                    Q(scope=cls.EXACT, org_unit_id=org_unit.id) |
                    Q(scope=cls.SUBTREE, org_unit_id__in=anc_ids)
                )
                if via_del.exists():
                    return True

        return False


class Delegation(models.Model):
    """Delegator grants delegatee the right to act with the delegator's scope."""
    delegator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="delegations_out")
    delegatee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="delegations_in")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ("delegator", "delegatee")

    def is_active(self):
        now = timezone.now()
        if not self.active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True

    def __str__(self):
        return f"{self.delegator} → {self.delegatee}"