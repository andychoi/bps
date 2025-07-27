from django.db import models, transaction
from django.conf import settings
from .models_layout import PlanningLayoutYear
from .models_dimension import OrgUnit

class PlanningStage(models.Model):
    """
    A single step in the planning process.
        order   code    name    can_run_in_parallel
        1   ENV_SETUP   Environment Setup   True
        2   GLOBAL_VALUES   Global Planning Values  True
        3   MANUAL_ORG  Manual Planning (per OrgUnit)   False
        4   VALIDATE_MANUAL Validate Manual Planning    False
        5   RUN_FUNCTIONS   Run Enterprise‐wide Functions   True
        6   REVIEW_FINAL    Review & Finalize   False
    """
    code       = models.CharField(max_length=20, unique=True)
    name       = models.CharField(max_length=100)
    order      = models.PositiveSmallIntegerField(
                   help_text="Determines execution order. Lower=earlier.")
    can_run_in_parallel = models.BooleanField(
                   default=False,
                   help_text="If True, this step may execute alongside others.")
    # e.g. 'delta', 'overwrite', etc. but DataRequest will get its own type.

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.order}: {self.name}"

class PlanningSession(models.Model):
    """
    One OrgUnit’s planning for one layout‐year.
    """
    layout_year = models.ForeignKey(PlanningLayoutYear, on_delete=models.CASCADE,
                                    related_name='sessions')
    org_unit    = models.ForeignKey(OrgUnit, on_delete=models.CASCADE,
                                    help_text="Owner of this session")
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    # Draft → Completed (owner) → Frozen (admin)
    class Status(models.TextChoices):
        DRAFT     = 'D','Draft'
        FEEDBACK  = 'B','Return Back'
        COMPLETED = 'C','Completed'
        REVIEW    = 'R','Review'
        FROZEN    = 'F','Frozen'
    status      = models.CharField(max_length=1,
                                   choices=Status.choices,
                                   default=Status.DRAFT)
    frozen_by   = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='+')
    frozen_at   = models.DateTimeField(null=True, blank=True)

    """ 
    - When you create a new session, set current_stage = PlanningStage.objects.get(order=1).
    - In every view (manual planning, data-request creation, function runs, etc.) check
    if not session.current_stage.can_run_in_parallel and session.current_stage.order != MY_STEP_ORDER:
        raise PermissionDenied("Cannot do manual planning until stage 3 is reached.")
    """
    current_stage = models.ForeignKey(PlanningStage, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        unique_together = ('layout_year','org_unit')
    def __str__(self):
        return f"{self.org_unit.name} - {self.layout_year}"

    def can_edit(self, user):
        if self.status == self.Status.DRAFT and user == self.org_unit.head_user:
            return True
        return False

    def complete(self, user):
        if user == self.org_unit.head_user:
            self.status = self.Status.COMPLETED
            self.save()

    def freeze(self, user):
        # planning admin only
        self.status    = self.Status.FROZEN
        self.frozen_by = user
        self.frozen_at = models.functions.Now()
        self.save()

