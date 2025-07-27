# models_dimension.py
from django.conf import settings
from django.db import models, transaction
from treebeard.mp_tree import MP_Node

class InfoObject(models.Model):
    """
    Abstract base for any dimension (Year, Period, Version, OrgUnit, etc.).
    """
    code        = models.CharField(max_length=20, unique=True)
    name        = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    order       = models.IntegerField(default=0,
                      help_text="Controls ordering in UIs")

    class Meta:
        abstract = True
        ordering = ['order', 'code']

    def __str__(self):
        return self.name

class Year(InfoObject):
    """e.g. code='2025', name='Fiscal Year 2025'"""
    pass

class Version(InfoObject):
    """
    A global dimension (e.g. 'Draft', 'Final', 'Plan v1', 'Plan v2').
    Used to isolate concurrent planning streams.
    """
    is_public = models.BooleanField(default=True, help_text="Public versions are visible to everyone; private only to creator")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="For private versions, track the owner"
    )

    class Meta(InfoObject.Meta):
        ordering = ['order', 'code']

class OrgUnit(MP_Node, InfoObject):
    head_user      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bps_orgunits_headed',
        related_query_name='bps_orgunit_headed',
        help_text="OrgUnit lead who must draft and approve"
    )
    cc_code    = models.CharField(max_length=10, blank=True)    # SAP cost center code
    node_order_by = ['order', 'code']  # controls sibling ordering


class CBU(InfoObject):
    """Client Business Unit (inherits InfoObject)"""
    group       = models.CharField(max_length=50, blank=True)  # e.g. industry vertical
    TIER_CHOICES = [('1','Tier-1'),('2','Tier-2'),('3','Tier-3')]
    tier        = models.CharField(max_length=1, choices=TIER_CHOICES)
    sla_profile = models.ForeignKey('SLAProfile', on_delete=models.SET_NULL, null=True, blank=True)
    region      = models.CharField(max_length=50, blank=True)
    is_active   = models.BooleanField(default=True)

    node_order_by = ['group', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Account(InfoObject):
    pass

class Service(InfoObject):
    """Product/Service"""
    category         = models.CharField(max_length=50)    # e.g. Platform, Security
    subcategory      = models.CharField(max_length=50)    # e.g. Directory Services
    related_services = models.ManyToManyField('self', blank=True)
    CRITICALITY_CHOICES = [('H','High'),('M','Medium'),('L','Low')]
    criticality      = models.CharField(max_length=1, choices=CRITICALITY_CHOICES)
    sla_response     = models.DurationField(help_text="e.g. PT2H for 2 hours")
    sla_resolution   = models.DurationField(help_text="e.g. PT4H for 4 hours")
    availability     = models.DecimalField(max_digits=5, decimal_places=3,
                                           help_text="e.g. 99.900")
    SUPPORT_HOUR_CHOICES = [
        ('24x7','24x7'),
        ('9x5','9x5 Mon-Fri'),
        ('custom','Custom')
    ]
    support_hours    = models.CharField(max_length=10,choices=SUPPORT_HOUR_CHOICES)
    orgunit      = models.ForeignKey('OrgUnit',on_delete=models.SET_NULL,null=True, blank=True)
    owner            = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True, blank=True)
    is_active        = models.BooleanField(default=True)

    class Meta:
        ordering = ['category','subcategory','code']

    def __str__(self):
        return f"{self.code} – {self.name}"
    
class CostCenter(InfoObject):
    pass

class InternalOrder(InfoObject):
    cc_code    = models.CharField(max_length=10, blank=True)    # SAP cost center code

