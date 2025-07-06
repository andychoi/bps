# bps/admin.py

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from .models import (
    Constant, SubFormula, Formula, FormulaRun, FormulaRunEntry,
    UnitOfMeasure, ConversionRate,
    Year, Version, OrgUnit, CostCenter, InternalOrder,
    UserMaster, PlanningLayout, PlanningLayoutYear,
    Period, PeriodGrouping,
    PlanningSession, DataRequest, PlanningFact
)

# ── Units of Measure & Conversion Rates ────────────────────────────────────

@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_base')
    search_fields = ('code', 'name')

@admin.register(ConversionRate)
class ConversionRateAdmin(admin.ModelAdmin):
    list_display = ('from_uom', 'to_uom', 'factor')
    list_filter  = ('from_uom', 'to_uom')

# ── Formula & Sub-Formula ─────────────────────────────────────────────────

@admin.register(Constant)
class ConstantAdmin(admin.ModelAdmin):
    list_display  = ('name', 'value')
    search_fields = ('name',)

@admin.register(SubFormula)
class SubFormulaAdmin(admin.ModelAdmin):
    list_display  = ('name',)
    search_fields = ('name',)

@admin.register(Formula)
class FormulaAdmin(admin.ModelAdmin):
    list_display  = ('name', 'loop_dimension')
    search_fields = ('name',)
    save_on_top  = True

# ── Formula Runs & Entries ────────────────────────────────────────────────

class FormulaRunEntryInline(admin.TabularInline):
    model = FormulaRunEntry
    extra = 0
    fields = ('record', 'key', 'old_value', 'new_value')
    readonly_fields = fields

@admin.register(FormulaRun)
class FormulaRunAdmin(admin.ModelAdmin):
    list_display   = ('id', 'formula', 'run_at', 'preview')
    list_filter    = ('formula','preview')
    readonly_fields= ('formula','run_at','preview')
    inlines        = [FormulaRunEntryInline]
    ordering       = ('-run_at',)
    
# ── InfoObject‐derived Dimensions ───────────────────────────────────────────

class InfoObjectAdmin(admin.ModelAdmin):
    list_display   = ('code', 'name', 'order')
    search_fields  = ('code', 'name')
    ordering       = ('order', 'code')

admin.site.register([Year, Version, OrgUnit, CostCenter, InternalOrder], InfoObjectAdmin)

@admin.register(UserMaster)
class UserMasterAdmin(admin.ModelAdmin):
    list_display  = ('user', 'org_unit', 'cost_center')
    search_fields = ('user__username', 'org_unit__name')


# ── Planning Layout & Year Scoping ─────────────────────────────────────────

class LayoutYearInline(admin.TabularInline):
    model = PlanningLayoutYear
    extra = 1
    fields = ('year', 'version', 'filter_horizontal')

@admin.register(PlanningLayout)
class PlanningLayoutAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    inlines      = [LayoutYearInline]

@admin.register(PlanningLayoutYear)
class PlanningLayoutYearAdmin(admin.ModelAdmin):
    list_display        = ('layout', 'year', 'version')
    filter_horizontal   = ('org_units', 'row_dims')
    search_fields       = ('layout__name',)


# ── Period & Grouping ──────────────────────────────────────────────────────

@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display   = ('code', 'name', 'order')
    ordering       = ('order',)
    search_fields  = ('code', 'name')

class PeriodGroupingInline(admin.TabularInline):
    model = PeriodGrouping
    extra = 1
    fields = ('months_per_bucket', 'label_prefix')

@admin.register(PeriodGrouping)
class PeriodGroupingAdmin(admin.ModelAdmin):
    list_display = ('layout_year', 'months_per_bucket', 'label_prefix')
    list_filter  = ('months_per_bucket',)


# ── Planning Workflow & Sessions ───────────────────────────────────────────

@admin.register(PlanningSession)
class PlanningSessionAdmin(admin.ModelAdmin):
    list_display  = ('org_unit', 'layout_year', 'status', 'created_at')
    list_filter   = ('status', 'layout_year')
    search_fields = ('org_unit__name',)
    actions       = ['make_completed', 'make_frozen']

    def make_completed(self, request, queryset):
        for session in queryset:
            session.complete(request.user)
    make_completed.short_description = "Mark selected sessions as Completed"

    def make_frozen(self, request, queryset):
        for session in queryset:
            session.freeze(request.user)
    make_frozen.short_description = "Mark selected sessions as Frozen"


# ── DataRequest & Facts Inline ────────────────────────────────────────────

class FactInline(admin.TabularInline):
    model = PlanningFact
    extra = 0
    readonly_fields = (
        'session',
        'period',
        'row_values',
        'quantity',
        'quantity_uom',
        'amount',
        'amount_uom',
        'other_key_figure',
        'other_value',
    )
    fields = readonly_fields
    can_delete = False
    show_change_link = True
    verbose_name_plural = "Planning Facts"

@admin.register(DataRequest)
class DataRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'description', 'created_at')
    list_filter  = ('session__layout_year',)
    search_fields = ('description', 'id')
    inlines = [FactInline]


@admin.register(PlanningFact)
class PlanningFactAdmin(admin.ModelAdmin):
    list_display = (
        'session',
        'period',
        'quantity',
        'quantity_uom',
        'amount',
        'amount_uom',
        'other_key_figure',
        'other_value',
    )
    list_filter  = ('period', 'quantity_uom', 'amount_uom')
    search_fields = ('other_key_figure',)
    readonly_fields = ('session', 'row_values')