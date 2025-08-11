# bps/admin_access.py
from django.contrib import admin
from .models.models_access import OrgUnitAccess, Delegation

@admin.register(OrgUnitAccess)
class OrgUnitAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "org_unit", "scope", "can_edit", "created_at")
    list_filter = ("scope", "can_edit", "org_unit")
    search_fields = ("user__username", "user__email", "org_unit__name", "org_unit__code")

@admin.register(Delegation)
class DelegationAdmin(admin.ModelAdmin):
    list_display = ("delegator", "delegatee", "active", "starts_at", "ends_at", "note")
    list_filter = ("active",)
    search_fields = ("delegator__username", "delegatee__username", "note")