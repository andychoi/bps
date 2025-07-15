# models_resource.py
from django.db import models, transaction
from .models_dimension import *

class Skill(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    def __str__(self): return self.name

class RateCard(models.Model):
    """
    Contractor/MSP rate and efficiency planning, scoped by Year.
    """
    RESOURCE_CHOICES = [('EMP', 'Employee'), ('CON','Contractor'), ('MSP','MSP')]

    skill = models.ForeignKey(Skill, on_delete=models.PROTECT) # Use PROTECT to prevent deleting skills in use
    level             = models.CharField(max_length=20)      # e.g. Junior/Mid/Senior
    resource_type       = models.CharField(max_length=20, choices=RESOURCE_CHOICES)
    country           = models.CharField(max_length=50)
    efficiency_factor = models.DecimalField(default=1.00, max_digits=5, decimal_places=2,
                                            help_text="0.00-1.00")
    class Meta:
        unique_together = ('skill', 'level', 'resource_type', 'country')
        ordering = ['skill','level','resource_type','country']
        verbose_name = "Rate Card Template"
        verbose_name_plural = "Rate Card Templates"

    def __str__(self):
        return (f"{self.resource_type} | {self.skill} ({self.level}) @ "
                f"{self.country}")
    
    # You'll need logic (perhaps in a signal or a custom save method)
    # to calculate `hourly_rate` from its components for 'EMP' types.
    """
    def save(self, *args, **kwargs):
        if self.resource_type == 'EMP':
            self.hourly_rate = (self.base_salary_hourly_equiv or 0) + \
                               (self.benefits_hourly_equiv or 0) + \
                               (self.payroll_tax_hourly_equiv or 0) + \
                               (self.overhead_allocation_hourly or 0)
        super().save(*args, **kwargs)
    """


class Resource(models.Model):
    RESOURCE_TYPES = [
        ('EMP', 'Employee'),
        ('CON', 'Contractor'),
        ('MSP','MSP Staff'),
    ]
    unique_id         = models.CharField(max_length=100, unique=True)
    display_name      = models.CharField(max_length=255)
    resource_type     = models.CharField(max_length=3, choices=RESOURCE_TYPES)
    current_skill     = models.ForeignKey(Skill,  on_delete=models.SET_NULL, null=True)
    current_level     = models.CharField(max_length=20, blank=True, null=True)
    country           = models.CharField(max_length=50, blank=True)
    # … any fields common to all resources …
    def __str__(self):
        return self.display_name

class Employee(Resource):
    # user              = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    employee_id       = models.CharField(max_length=20, unique=True)
    hire_date         = models.DateField()
    annual_salary     = models.DecimalField(max_digits=12, decimal_places=2)
    # … benefits/tax/etc …

    
class Vendor(models.Model):
    name = models.CharField(max_length=255, unique=True)
    vendor_type = models.CharField(max_length=20, choices=RateCard.RESOURCE_CHOICES[1:]) # CON, MSP
    # ... vendor specific details (contact info, billing terms, etc.)
    def __str__(self):
        return self.name

class Contractor(Resource):
    vendor            = models.ForeignKey(Vendor, on_delete=models.PROTECT)
    contract_id       = models.CharField(max_length=50, unique=True)
    contract_start    = models.DateField()
    contract_end      = models.DateField()
    # … contractor-specific fields …

class MSPStaff(Resource):
    # if you need to track individuals from your MSP(s)
    pass


class Position(InfoObject):
    # Override parent code to remove unique constraint
    code        = models.CharField(max_length=20)
    year        = models.ForeignKey(Year, on_delete=models.CASCADE)
    skill       = models.ForeignKey(Skill, on_delete=models.PROTECT)
    level       = models.CharField(max_length=20)      # e.g. Junior/Mid/Senior
    orgunit     = models.ForeignKey(OrgUnit, on_delete=models.PROTECT, null=True, blank=True) 
    fte         = models.FloatField(default=1.0)        # FTE equivalent
    is_open     = models.BooleanField(default=False)    # open vs. filled
    intended_resource_type = models.CharField(
        max_length=20,
        choices=RateCard.RESOURCE_CHOICES,
        default='EMP', # Assume internal unless specified
        help_text="Intended category for this position (Employee, Contractor, MSP). Used for budgeting if 'is_open' is True."
    )
    filled_by_resource = models.ForeignKey(Resource, on_delete=models.SET_NULL, null=True, blank=True,
                                            help_text="The specific person filling this position.")    
    class Meta(InfoObject.Meta):
        unique_together = ('year', 'code')
        ordering = ['year__code', 'order', 'code']

    def __str__(self):
        status = 'Open' if self.is_open else 'Filled'
        return f"[{self.year.code}] {self.code} ({self.skill}/{self.level}) - {status}"
# New KeyFigures for Position budgeting:
# budgeted_fte = KeyFigure.objects.create(code='BUDGETED_FTE', name='Budgeted Full-Time Equivalent')
# position_status = KeyFigure.objects.create(code='POSITION_STATUS', name='Position Status (Open/Filled)')
# intended_category = KeyFigure.objects.create(code='INTENDED_CATEGORY', name='Intended Resource Category')
