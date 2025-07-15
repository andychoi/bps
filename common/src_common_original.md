# Python Project Summary: common

---

### `apps.py`
```python
from django.apps import AppConfig
```

### `autocomplete.py`
```python
from dal import autocomplete
from dal_select2.views import Select2QuerySetView
from django.contrib.auth import get_user_model
UserModel = get_user_model()
from .models import OrgUnit, OrgLevel
from django.db.models import Count, Q
class UserAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = UserModel.objects.all()
        if self.q:
            qs = qs.filter(
                Q(username__icontains=self.q) | Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q)
            )
        return qs
class AuthUserAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return UserModel.objects.none()
        qs = UserModel.objects.filter(is_active=True)
        if self.request.user.is_superuser:
            pass
        else:
            qs = qs.filter(is_superuser=False)
        if self.q:
            qs = qs.filter(
                Q(username__icontains=self.q) | Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q)
            )
        return qs
class OrgUnitAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        qs = OrgUnit.objects.filter(is_active=True)
        if not self.q:
            org_id = self.forwarded.get('orgunit') or getattr(self.request.user, 'orgunit_id', None)
            if org_id:
                try:
                    root = OrgUnit.objects.get(pk=org_id)
                    descendants = root.get_descendants()
                    qs = qs.filter(pk__in=[root.pk] + [o.pk for o in descendants])
                except OrgUnit.DoesNotExist:
                    pass
        if self.q:
            qs = qs.filter(
                Q(name__icontains=self.q) |
                Q(code__icontains=self.q)
            )
        return qs
    def get_result_label(self, item):
        return f"{item.get_level_display()} - {item.name}"
    def get_selected_result_label(self, item):
        return self.get_result_label(item)
    def get_result_value(self, item):
        return item.pk
```

### `choices.py`
```python
from django.db import models
USERTYPE_CHOICES  = (
    ("ADM",   "Admin"),
    ("EMP",   "Employee"),
    ("TEM",   "Contractor"),
    ("CUS",   "Customer"),
    ("VEN",   "Vendor"),
)
class UserTypeChoices(models.TextChoices):
    ADMIN = 'ADM', "Admin"
    EMPLOYEE = 'EMP', "Employee"
    CONTRACTOR = 'TEM', "Contractor"
    CUSTOMER = 'CUS', "Customer"
    VENDOR = 'VEN', "Vendor"
    UNKNOWN = 'UNK', "Unknown"
class OrgCategoryChoices(models.TextChoices):
    DIRECT = 'DIRECT', 'Direct'
    SUPPORT = 'SUPPORT', 'Support'
    ADMIN = 'ADMIN', 'Admin'
    NOT = 'NOT', 'Not Categorized'
```

### `loginas.py`
```python
from django.conf import settings
from django.shortcuts import redirect, resolve_url
from django.contrib.auth import login, logout, get_user_model
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages
import logging
logger = logging.getLogger(__name__)
User = get_user_model()
def login_as(request):
    orig_id = request.session.get('original_login_id')
    original = User.objects.filter(pk=orig_id).first() if orig_id else request.user
    if not original.is_superuser:
        messages.error(request, "Access denied: only superusers can impersonate.")
        return redirect(settings.LOGIN_REDIRECT_URL)
    target = None
    uname = request.GET.get("username")
    if uname:
        target = User.objects.filter(username=uname).first()
    else:
        try:
            pk = int(request.GET.get("user_pk", ""))
            target = User.objects.filter(pk=pk).first()
        except (ValueError, TypeError):
            target = None
    if not target:
        logout(request)
        request.session.pop('original_login_id', None)
        messages.warning(request, "Logged out successfully.")
        logger.info(f"{original.username} ended impersonation")
        return redirect(settings.LOGIN_REDIRECT_URL)
    if 'original_login_id' not in request.session:
        request.session['original_login_id'] = original.pk
    target.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, target)
    request.session.save()
    messages.success(request, f"You are now impersonating {target.username}.")
    logger.info(f"{original.username} is impersonating {target.username}")
    next_url = request.GET.get('next') or settings.LOGIN_REDIRECT_URL
    if url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        return redirect(next_url)
    return redirect(settings.LOGIN_REDIRECT_URL)
```

### `models.py`
```python
import logging
logger = logging.getLogger(__name__)
from django.db import models
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.contrib.auth.models import UserManager
from django.utils.functional import cached_property
from django.contrib.auth.models import AbstractUser
from .choices import USERTYPE_CHOICES, UserTypeChoices, OrgCategoryChoices
from .models_base import BaseModel, ActiveManager
class OrgLevel(models.IntegerChoices):
    COMPANY = 0, _("Company")
    DIV     = 1, _("Division")
    SUB_DIV = 2, _("Sub-Div")
    DEPT    = 3, _("Department")
    TEAM    = 4, _("Team")
    UNKNOWN = 9, _("Unknown")
class OrgUnit(models.Model):
    code = models.CharField(unique=False, db_index=True, max_length=10)
    name = models.CharField(db_index=True, max_length=250)
    description = models.TextField(blank=True)
    category = models.CharField(_("Category"), max_length=10, choices=OrgCategoryChoices.choices,
                                default=OrgCategoryChoices.NOT)
    level = models.PositiveSmallIntegerField(choices=OrgLevel.choices, default=OrgLevel.UNKNOWN)
    is_active = models.BooleanField(_("active"), default=True)
    objects = ActiveManager()
    all_objects = models.Manager()
    company = models.CharField(_('Company'), max_length=25, blank=True, null=True)
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_org', db_index=True
    )
    head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
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
    def __str__(self):
        return self.name
    def natural_key(self):
        return (self.name,)
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
    def move(self, new_parent, pos='sorted-child'):
        self.parent = new_parent
        self.save()
        if pos == 'sorted-child':
            self._sort_children()
    def _sort_children(self):
        children = self.get_children().order_by('code')
    def get_children(self):
        return self.sub_org.all()
    def get_ancestors(self, visited=None):
        if visited is None:
            visited = set()
        if self in visited:
            logger.error(f"Circular parent reference detected for OrgUnit: {self.name}")
            raise ValueError(f"Circular parent reference detected for OrgUnit: {self.name}")
        ancestors = []
        node = self.parent
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
        if other_org_unit in self.get_descendants():
            return True
        return False
    def get_managers_and_higher(self):
        from .models import User
        all_units = self.get_ancestors() + [self]
        users_in_units = User.objects.filter(orgunit__in=all_units)
        managers_and_higher = users_in_units.filter(
                models.Q(manager__isnull=False) | models.Q(subordinates__isnull=False)
            ).distinct()
        return managers_and_higher
    def clean(self):
        super().clean()
        if self.parent_id and self.parent_id == self.pk:
            raise ValidationError(_("An OrgUnit cannot be its own parent."))
        ancestor = self.parent
        visited = set()
        while ancestor:
            if ancestor.pk in visited:
                raise ValidationError(_("Circular parent relationship detected."))
            visited.add(ancestor.pk)
            ancestor = ancestor.parent
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
class OrgunitRetired(OrgUnit):
    class Meta:
        proxy = True
        verbose_name = "Orgunit (retired)"
class User(AbstractUser):
    alias = models.CharField(max_length=50, blank=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL,  related_name='subordinates',  on_delete=models.SET_NULL, blank=True, null=True,)
    orgunit = models.ForeignKey(OrgUnit, verbose_name=_('Org Unit'), related_name='org_members', on_delete=models.SET_NULL, blank=True, null=True)
    company   = models.CharField(_('Company'), max_length=25, blank=True, null=True)
    dept_name = models.CharField(_('Dept Name'), max_length=50, blank=True, null=True)
    job_title = models.CharField(_('Job title'), max_length=50, blank=True, null=True)
    officelocation = models.CharField(_('Office location'), max_length=50, blank=True, null=True)
    userType = models.CharField(_('user Type'), max_length=10, blank=True, null=True)
    onPremisesSamAccountName = models.CharField(_('samAccount'), max_length=12, blank=True, null=True)
    acccountEnabled = models.BooleanField(_('accountEnabled'), default=True, null=True)
    path    = models.CharField(max_length=255, null=True, blank=True)
    tree    = models.CharField(max_length=255, null=True, blank=True)
    depth   = models.PositiveIntegerField(default=1, null=True, blank=True)
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
        if self.username:
            self.username = self.username.lower()
        super().save(*args, **kwargs)
class UserInactive(User):
    class Meta:
        proxy = True
        verbose_name = "User (inactive)"
```

### `models_base.py`
```python
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
class BaseModel(models.Model):
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, editable=False)
    updated_on = models.DateTimeField(_("updated_on"), auto_now=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='created_by_%(class)s_related',
        verbose_name=_('created by'),
        on_delete=models.DO_NOTHING,
        null=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='updated_by_%(class)s_related',
        verbose_name=_('updated by'),
        on_delete=models.DO_NOTHING,
        null=True,
    )
    class Meta:
        abstract = True
class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
```

### `templatetags/user_tags.py`
```python
from django.conf import settings
from django import template
register = template.Library()
from django.contrib.auth import get_user_model
User = get_user_model()
@register.filter
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists()
@register.filter()
def check_permission(user, permission):
    if user.user_permissions.filter(codename=permission).exists():
        return True
    return False
@register.simple_tag(takes_context=True)
def get_session_value(context, key):
    request = context["request"]
    return request.session.get(key, None)
@register.simple_tag(takes_context=True)
def is_original_user_superuser(context):
    request = context["request"]
    original_login_id = request.session.get("original_login_id")
    if original_login_id:
        try:
            original_user = User.objects.get(id=original_login_id)
            return original_user.is_superuser
        except User.DoesNotExist:
            return False
    return False
@register.simple_tag(takes_context=True)
def get_session_user_id(context):
    return get_session_value(context, "original_login_id")
@register.simple_tag(takes_context=True)
def get_selected_user(context):
    request = context["request"]
    selected_user = request.GET.get("selected_user", "")
    if not selected_user:
        selected_user = request.user.username
    return selected_user
```

### `urls.py`
```python
from django.urls import path, re_path
from .autocomplete import UserAutocomplete, OrgUnitAutocomplete
from .loginas import login_as
from .views import UserSearchJSON, loginas_list_view
app_name = 'common'
urlpatterns = [
    path('api/user-search/', UserSearchJSON.as_view(), name='api-user-search'),
    path('user-autocomplete/', UserAutocomplete.as_view(), name='user-autocomplete'),
    path('orgunit-autocomplete/', OrgUnitAutocomplete.as_view(), name='orgunit-autocomplete'),
    path('api/login_as/', login_as, name="api-login-as"),
    path('loginas/', loginas_list_view, name='loginas_list'),
]
```

### `user.py`
```python
from django.contrib.auth import get_user_model
User = get_user_model()
```

### `views.py`
```python
from django.db.models import Q
from django.views.generic import ListView
from dal import autocomplete
from django.http import JsonResponse
from .autocomplete import AuthUserAutocomplete
from .user import User
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
@user_passes_test(lambda u: u.is_superuser)
def loginas_list_view(request):
    return render(request, "loginas_list.html")
class UserSearchJSON(ListView):
    model = User
    http_method_names = ['get']
    def get(self, request, *args, **kwargs):
        search_term = request.GET.get('q', '')
        users = User.objects.filter(
            Q(username__icontains=search_term) |
            Q(alias__icontains=search_term) |
            Q(first_name__icontains=search_term) |
            Q(last_name__icontains=search_term)
        ).order_by('username').values('id', 'username', 'first_name', 'last_name', 'alias', 'job_title', 'dept_name', 'company')
        users_list = list(users)
        paginator = Paginator(users_list, 10)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        user_data = list(page_obj.object_list)
        has_more = page_obj.has_next()
        return JsonResponse({
            'users': user_data,
            'has_more': has_more
        })
```

