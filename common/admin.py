# common/admin.py
# common/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _
from .models import User, OrgUnit, OrgunitRetired

# If you’re *only* using common.User, unregister the default Group entry
admin.site.unregister(Group)

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = (
        'username', 'display_name', 'email', 'job_title',
        'orgunit', 'manager_name', 'is_active', 'is_staff',
    )
    list_filter = (
        'is_active', 'is_staff',
        'company', 'userType', 'orgunit__level',
    )
    search_fields = (
        'username', 'alias', 'email',
        'first_name', 'last_name', 'job_title', 'dept_name',
    )
    ordering = ['username']
    autocomplete_fields = ['manager', 'orgunit']

    # Extend the default UserAdmin fieldsets
    fieldsets = BaseUserAdmin.fieldsets + (
        (_('Extra info'), {
            'fields': (
                'alias', 'company', 'dept_name',
                'job_title', 'officelocation', 'userType',
            )
        }),
    )

    def manager_name(self, obj):
        return obj.manager.display_name if obj.manager else '-'
    manager_name.short_description = 'Manager'


@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'name', 'level', 'category',
        'parent_name', 'head_name', 'is_active',
    )
    list_filter = ('is_active', 'level', 'category', 'company')
    search_fields = ('code', 'name', 'description', 'cc_code')
    autocomplete_fields = ['parent', 'head']
    ordering = ['level', 'code']

    def parent_name(self, obj):
        return obj.parent.name if obj.parent else '-'
    parent_name.short_description = 'Parent Org'

    def head_name(self, obj):
        return obj.head.display_name if obj.head else '-'
    head_name.short_description = 'Head'
