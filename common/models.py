# common/models.py
import logging
logger = logging.getLogger(__name__)

from django.db import models
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.models import UserManager
from django.utils.functional import cached_property
# from treebeard.mp_tree import MP_Node
from django.contrib.auth.models import AbstractUser
from .choices import USERTYPE_CHOICES, UserTypeChoices, OrgCategoryChoices
from .models_base import BaseModel, ActiveManager     

class OrgLevel(models.IntegerChoices):
    """ Org
    Level 1: Division.
    Level 2: Department.
    Level 3: Team (or any level 3+)
    """
    COMPANY = 0, _("Company")      #00
    DIV     = 1, _("Division")     #01
    SUB_DIV = 2, _("Sub-Div")      #02
    DEPT    = 3, _("Department")   #03
    TEAM    = 4, _("Team")         #04
    UNKNOWN = 9, _("Unknown")

class OrgUnit(models.Model):
    """ without treebeard dependency""" 
    code = models.CharField(unique=False, db_index=True, max_length=10)
    name = models.CharField(db_index=True, max_length=250)
    description = models.TextField(blank=True)

    category = models.CharField(_("Category"), max_length=10, choices=OrgCategoryChoices.choices,
                                default=OrgCategoryChoices.NOT)
    level = models.PositiveSmallIntegerField(choices=OrgLevel.choices, default=OrgLevel.UNKNOWN)
    
    is_active = models.BooleanField(_("active"), default=True)
    objects = ActiveManager()        # default = active only
    all_objects = models.Manager()  # all, if you ever need it

    company = models.CharField(_('Company'), max_length=25, blank=True, null=True)
    
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_org', db_index=True
    )
    head = models.ForeignKey(
        'User',     #settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='head_of_org',
        related_query_name='bps_orgunit_as_head',
        db_index=True
    )    
    cc_code = models.CharField( _("Cost Center Code"), max_length=10, blank=True, null=True, )
    class Meta:
        ordering = ['code']
        verbose_name = _("Org Unit")
        verbose_name_plural = _("Org Units")
        # unique_together = ('name', 'parent')  # Ensures unique OrgUnit names within the same parent

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.name,)

    # mimicking treebeard's depth/numchild/path
    @property
    def depth(self):
        return len(self.get_ancestors())

    @property
    def numchild(self):
        return self.get_children().count()

    @property
    def path(self):
        ancestors = self.get_ancestors()
        codes = [ancestor.code for ancestor in ancestors] + [self.code]
        return '/'.join(codes)
    
    # mimicking treebeard's move
    def move(self, new_parent, pos='sorted-child'):
        # Update the parent
        self.parent = new_parent
        self.save()

        # Optionally, reorder the children if needed
        if pos == 'sorted-child':
            self._sort_children()

    def _sort_children(self):
        children = self.get_children().order_by('code')

    # 3. Get children functionality (mimicking treebeard's get_children)
    def get_children(self):
        return self.sub_org.all()

    def get_ancestors(self, visited=None):
        """
        Get all ancestors of the current node with circular reference detection.
        """
        if visited is None:
            visited = set()

        # Check for circular reference
        if self in visited:
            logger.error(f"Circular parent reference detected for OrgUnit: {self.name}")
            raise ValueError(f"Circular parent reference detected for OrgUnit: {self.name}")

        ancestors = []
        node = self.parent

        # Traverse up the hierarchy
        while node:
            if node in visited:
                logger.error(f"Circular parent reference detected at OrgUnit: {node.name}")
                raise ValueError(f"Circular parent reference detected at OrgUnit: {node.name}")
            ancestors.append(node)
            visited.add(node)
            node = node.parent

        return ancestors

    def get_descendants(self):
        descendants = []

        def collect_children(org_unit):
            children = org_unit.get_children()
            for child in children:
                descendants.append(child)
                collect_children(child)

        collect_children(self)
        return descendants

    def is_child_node(self):
        return self.parent is not None

    def is_root_node(self):
        return self.parent is None

    def is_upper_level(self, other_org_unit):
        # return self.depth < other_org_unit.depth

        # Case 1: Check if this unit is an ancestor of the other unit
        if other_org_unit in self.get_descendants():
            return True

        # Case 2: If not an ancestor, compare based on depth (lower depth is higher)
        # if self.depth < other_org_unit.depth:
        #     return True

        # # Case 3: If depth is the same, compare the level explicitly
        # if self.depth == other_org_unit.depth:
        #     return self.level < other_org_unit.level

        # If neither an ancestor nor a higher depth/level, return False
        return False

    def get_managers_and_higher(self):

        from .models.models import User  # Adjust import path as per your project structure

        # Get all ancestors including the current org unit
        all_units = self.get_ancestors() + [self]

        # Fetch all users from these units
        users_in_units = User.objects.filter(orgunit__in=all_units)

        # Optionally, filter for managerial roles (add conditions as required)
        # manager_roles = ['Manager', 'Senior Manager', 'Director']  # Example roles, adjust as needed
        # managers_and_higher = users_in_units.filter(
        #     models.Q(manager__isnull=False) | models.Q(alias__in=manager_roles)
        managers_and_higher = users_in_units.filter(
                models.Q(manager__isnull=False) | models.Q(subordinates__isnull=False)
            ).distinct()        

        return managers_and_higher

    # to ensure no circulation
    def clean(self):
        super().clean()

        # 1) cannot be its own parent
        if self.parent_id and self.parent_id == self.pk:
            raise ValidationError(_("An OrgUnit cannot be its own parent."))

        # 2) no circular ancestry
        ancestor = self.parent
        visited = set()
        while ancestor:
            if ancestor.pk in visited:
                raise ValidationError(_("Circular parent relationship detected."))
            visited.add(ancestor.pk)
            ancestor = ancestor.parent

    def save(self, *args, **kwargs):
        # always run full_clean first
        self.full_clean()
        super().save(*args, **kwargs)

class OrgunitRetired(OrgUnit):
    class Meta:
        proxy = True
        verbose_name = "Orgunit (retired)"

""" custom user model
"""
class User(AbstractUser):
    # username = models.CharField(max_length=150)
    # first_name = models.CharField(max_length=150, blank=True)
    # last_name = models.CharField(max_length=150, blank=True)
    # email = models.EmailField(blank=True)
    # is_staff = models.BooleanField()
    # is_active = models.BooleanField()

    """ AD attributes """
    alias = models.CharField(max_length=50, blank=True)                                 # displayName
    manager = models.ForeignKey(settings.AUTH_USER_MODEL,  related_name='subordinates',  on_delete=models.SET_NULL, blank=True, null=True,)
    orgunit = models.ForeignKey(OrgUnit, verbose_name=_('Org Unit'), related_name='org_members', on_delete=models.SET_NULL, blank=True, null=True)

    company   = models.CharField(_('Company'), max_length=25, blank=True, null=True)    
    dept_name = models.CharField(_('Dept Name'), max_length=50, blank=True, null=True)  
    job_title = models.CharField(_('Job title'), max_length=50, blank=True, null=True)  
    officelocation = models.CharField(_('Office location'), max_length=50, blank=True, null=True)

    # usertype    = models.CharField(_("User Type"), choices=USERTYPE_CHOICES, max_length=10, null=True, blank=True)
    userType = models.CharField(_('user Type'), max_length=10, blank=True, null=True)  # Member, Guest, None
    onPremisesSamAccountName = models.CharField(_('samAccount'), max_length=12, blank=True, null=True)
    acccountEnabled = models.BooleanField(_('accountEnabled'), default=True, null=True)

    # generated using manager hierarchy relations 
    path    = models.CharField(max_length=255, null=True, blank=True) # 101/10/1 format
    tree    = models.CharField(max_length=255, null=True, blank=True) # 1/10/101 format reversed
    depth   = models.PositiveIntegerField(default=1, null=True, blank=True) # 4 digit in path (max 63)

    # keep the default, so all the BaseUserManager methods stay available:
    objects = UserManager()    
    active = ActiveManager()

    class Meta:
        permissions = [
            ("can_edit_superuser", "Can edit superuser status"),
        ]
 
    @cached_property
    def display_name(self):
        uname = '@' + self.username.split("@")[0] if "@" in self.username else self.username
        full_name = f"{self.last_name}, {self.first_name}".strip(", ") if self.last_name else self.first_name or uname
        return full_name

    def __str__(self):
        status = " (inactive)" if not self.is_active else ""
        company = f"[{self.company}]" if self.company else ""
        return f"{self.display_name}{status} {company}" 

    def save(self, *args, **kwargs):
        # Ensure username is always lowercase
        if self.username:
            self.username = self.username.lower()
        super().save(*args, **kwargs)


    """ update path hierarchy using Panda
    @classmethod
    def update_path(cls):
        qs = cls.objects.values_list("id", "manager_id")    # username    
        df = pd.DataFrame(list(qs), columns=["id", "manager_id"]) ## this will save 50% memory
        dct = dict(zip(df.id.values, df.manager_id.values))

        # convert list of lists to dataframe / "path" is additional column
        def hierarchy(id):  # static method is not callable by dataframe.apply  
            boss = str(id) + '/'
            tree = str(id)
            depth = 1
            while dct.get(id, '') != "" and not pd.isna(dct[id]) and dct[id] != id:        # empty, isna, no more manager or self, what if endless looping??
                boss += str(int(dct[id])) + '/'
                tree = str(int(dct[id])) + '/' + tree
                id = int(dct.get(id, ''))    #next boss
                depth += 1
            return boss[:-1], tree, depth      #remove / 
        
        df['path'], df['tree'], df['depth'] = zip(*df['id'].apply(hierarchy))   # no need lambda
        # Result
        #    EMPLOYEE_ID NAME  MANAGER_ID      Path
        # 0          101    A          10  101/10/1
        # 1          102    B          11  102/11/1
        # 2           10    C           1      10/1
        # 3           11    D           1      11/1
        # 4            1    E         NaN         1

        objs = []
        for index, row in df.iterrows():
            obj = cls.objects.get(pk=row['id'])     # row['id']
            obj.path = row['path']
            obj.tree = row['tree']
            obj.depth = row['depth']
            objs.append(obj)
        cls.objects.bulk_update(objs, ['path', 'tree', 'depth'], batch_size=100)
        """

class UserInactive(User):
    class Meta:
        proxy = True
        verbose_name = "User (inactive)"

