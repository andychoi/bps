# Python Project Summary: common

---

### `apps.py`
```python
from django.apps import AppConfig
class UsersConfig(AppConfig):
    name = 'users'
    def ready(self):
        import common.signals
```

### `autocomplete.py`
```python
from dal import autocomplete
from django.contrib.auth import get_user_model
UserModel = get_user_model()
from .models import OrgUnit, OrgLevel
from django.db.models import Count, Q
class UserAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = UserModel.objects.all()
        if self.q:
            qs = qs.filter(
                Q(username__icontains=self.q) | Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q)
            )
        return qs
class AuthUserAutocomplete(autocomplete.Select2QuerySetView):
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
class OrgUnitAutocomplete(autocomplete.Select2QuerySetView):
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
from django.urls import path, re_path
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth import login, logout, get_user_model
User = get_user_model()
from django.contrib import messages
from django.db.models import Q
import logging
logger = logging.getLogger(__name__)
def login_as(request):
    original_user_id = request.session.get('original_login_id', None)
    original_user = User.objects.get(id=original_user_id) if original_user_id else request.user
    if not original_user.is_superuser:
        messages.error(request, "Access denied. Only superusers can use this feature.")
        return redirect(settings.LOGIN_REDIRECT_URL)
    user = None
    try:
        user = User.objects.get(username=request.GET.get("username"))
    except:
        user_pk = request.GET.get('user_pk', None)
        if user_pk:
            try:
                user = User.objects.get(pk=int(user_pk))
            except User.DoesNotExist:
                logger.warning(f"User {user_pk} does not exist")
                return
    if user:
        original_login_id = request.session.get('original_login_id', request.user.id)
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        request.session.save()
        if request.user.is_authenticated and request.user == user:
            request.session['original_login_id'] = original_login_id
            messages.success(request, f"Successfully logged in as {user.username}.")
            logger.info(f"User {original_user.username} logged in as {user.username}")
        else:
            messages.error(request, "Login failed.")
            logger.warning("User login failed for some reason.")
    else:
        logout(request)
        messages.warning(request, f"Logged out successfully.")
        logger.info(f"User {request.user.username} was logged out.")
    redirect_to = request.GET.get('next')
    if redirect_to and url_has_allowed_host_and_scheme(redirect_to, None):
        return HttpResponseRedirect(redirect_to)
    else:
        return redirect(settings.LOGIN_REDIRECT_URL)
```

### `models.py`
```python
import logging
logger = logging.getLogger(__name__)
from django.db import models
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
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
    level = models.PositiveSmallIntegerField(choices=OrgLevel.choices, default=OrgLevel.NA)
    is_active = models.BooleanField(_("active"), default=True)
    objects = ActiveManager()
    all_objects = models.Manager()
    company = models.CharField(_('Company'), max_length=25, blank=True, null=True)
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_org', db_index=True
    )
    head = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True, related_name='head_of_org', db_index=True
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
    manager = models.ForeignKey('users.user',  related_name='subordinates',  on_delete=models.SET_NULL, blank=True, null=True,)
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
class BaseModel(models.Model):
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, editable=False)
    updated_on = models.DateTimeField(_("updated_on"), auto_now=True, editable=False)
    created_by = models.ForeignKey('users.User', related_name='created_by_%(class)s_related', verbose_name=_('created by'),
                                   on_delete=models.DO_NOTHING, null=True)
    updated_by = models.ForeignKey('users.User', related_name='updated_by_%(class)s_related', verbose_name=_('updated by'),
                                   on_delete=models.DO_NOTHING, null=True)
    class Meta:
        abstract = True
class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
```

### `templates/nav-loginas.html`
```html
{% load tags %}
{% load user_tags %}
{% is_original_user_superuser as is_superuser %}
{% if user.is_superuser or is_superuser %}
<li id="login_as_menu" class="nav-item dropdown">
    <a class="nav-link dropdown-toggle" href="#" id="navbarDropdownMenuLinkL" role="button" data-bs-toggle="dropdown" aria-expanded="false">
        <i class="bi bi-people-fill"></i>
        <span>Login as...</span>
    </a>
    <ul class="dropdown-menu dropdown-menu-end p-3" aria-labelledby="navbarDropdownMenuLinkL">
        <input type="text" id="loginAsUserSearch" class="form-control mb-2" placeholder="Search users..." onkeyup="filterLoginAsUsers()">
        {% get_session_user_id as session_user_id %}
        {% if user.id != session_user_id %}
        <li class="dropdown-item">
            <a href="{% url 'login_as' %}?user_pk={{ session_user_id }}&next={{ request.path }}">Return to Original User</a>
        </li>
        <li class="dropdown-divider"></li>
        {% endif %}
        <div id="loginAsUserList">
        </div>
    </ul>
</li>
<script>
// Common function to add a user to the list
function addUserToList(user, userList) {
    const listItem = document.createElement('li');
    listItem.className = 'dropdown-item';
    listItem.innerHTML = `
        <div class="d-flex justify-content-between">
            <a href="/login_as/?user_pk=${user.id}&next=${encodeURIComponent(window.location.pathname)}">
            ${user.first_name} ${user.last_name} <span class='text-muted'>${user.alias || ''}   - ${user.job_title || ''}</span>
            </a>
            <span class="ms-4"></span> 
            <a href="/user_detail/${user.id}"><i class="bi bi-person text-muted"></i></a>
        </div>
    `;
    userList.appendChild(listItem);
}
function filterLoginAsUsers() {
    // Get the search input value
    const searchInput = document.getElementById('loginAsUserSearch').value;
    // Fetch the filtered results from the server
    const url = `{% url 'user_search' %}?q=${encodeURIComponent(searchInput)}&page=1`;
    fetch(url)
        .then(response => response.json())
        .then(data => {
            const userList = document.getElementById('loginAsUserList');
            userList.innerHTML = ''; // Clear existing list
            // Add each user to the list using the common function
            data.users.forEach(user => addUserToList(user, userList));
            // Handle "Load more" button if there are more results
            if (data.has_more) {
                const loadMoreButton = document.createElement('button');
                loadMoreButton.className = 'btn btn-secondary btn-sm mt-2';
                loadMoreButton.innerText = 'Load more';
                loadMoreButton.id = 'loadMoreButton'; // Assign an id for later reference
                loadMoreButton.onclick = (e) => {
                    e.stopPropagation(); // Prevent dropdown from closing
                    loadMoreResults(searchInput, 2); // Start with page 2
                };
                userList.appendChild(loadMoreButton);
            }
        })
        .catch(error => console.error('Error fetching users:', error));
}
// Function to load more results
function loadMoreResults(searchInput, page) {
    const url = `{% url 'user_search' %}?q=${encodeURIComponent(searchInput)}&page=${page}`;
    fetch(url)
        .then(response => response.json())
        .then(data => {
            const userList = document.getElementById('loginAsUserList');
            // Add each additional user to the list using the common function
            data.users.forEach(user => addUserToList(user, userList));
            // Update or remove the load more button based on `has_more`
            const loadMoreButton = document.getElementById('loadMoreButton');
            if (data.has_more) {
                const nextPage = page + 1;
                loadMoreButton.onclick = (e) => {
                    e.stopPropagation(); // Prevent dropdown from closing
                    loadMoreResults(searchInput, nextPage);
                };
            } else if (loadMoreButton) {
                loadMoreButton.remove(); // Remove if no more results
            }
        })
        .catch(error => console.error('Error fetching more users:', error));
}
</script>
{% endif %}
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
urlpatterns = [
    path('user-autocomplete/', UserAutocomplete.as_view(), name='user-autocomplete'),
    path('orgunit-autocomplete/', OrgUnitAutocomplete.as_view(), name='orgunit-autocomplete'),
    re_path(r'^login_as/$', login_as, name="login-as")
]
```

### `user.py`
```python
from django.contrib.auth import get_user_model
User = get_user_model()
```

