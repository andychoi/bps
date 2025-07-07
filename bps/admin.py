# bps/admin.py
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from .models import (
    UnitOfMeasure, ConversionRate,
    Constant, SubFormula, Formula, FormulaRun, FormulaRunEntry,
    PlanningFunction, ReferenceData,
    Year, Version, OrgUnit, Account, Service, CBU, CostCenter, InternalOrder,
    SLAProfile, KeyFigure,
    PlanningLayout, PlanningDimension, PlanningKeyFigure, PlanningLayoutYear,
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


# ── Constants & Formulas ───────────────────────────────────────────────────
@admin.register(Constant)
class ConstantAdmin(admin.ModelAdmin):
    list_display  = ('name', 'value')
    search_fields = ('name',)

@admin.register(SubFormula)
class SubFormulaAdmin(admin.ModelAdmin):
    list_display  = ('name', 'layout')
    search_fields = ('name', 'layout__code')
    list_filter   = ('layout',)

@admin.register(Formula)
class FormulaAdmin(admin.ModelAdmin):
    list_display  = ('name', 'layout')
    search_fields = ('name', 'layout__code')
    list_filter   = ('layout',)

# ── Formula Runs & Entries ────────────────────────────────────────────────
class FormulaRunEntryInline(admin.TabularInline):
    model = FormulaRunEntry
    extra = 0
    fields = ('record', 'key', 'old_value', 'new_value')
    readonly_fields = fields

@admin.register(FormulaRun)
class FormulaRunAdmin(admin.ModelAdmin):
    list_display    = ('id', 'formula', 'run_at', 'preview')
    list_filter     = ('formula', 'preview')
    readonly_fields = ('formula', 'run_at', 'preview')
    inlines         = [FormulaRunEntryInline]
    ordering        = ('-run_at',)

# ── PlanningFunction & ReferenceData ──────────────────────────────────────
@admin.register(PlanningFunction)
class PlanningFunctionAdmin(admin.ModelAdmin):
    list_display  = ('name', 'layout', 'function_type')
    list_filter   = ('function_type', 'layout')
    search_fields = ('name',)

@admin.register(ReferenceData)
class ReferenceDataAdmin(admin.ModelAdmin):
    list_display  = ('name', 'source_year', 'source_version')
    search_fields = ('name',)

# ── InfoObject‐derived Dimensions ───────────────────────────────────────────
class InfoObjectAdmin(admin.ModelAdmin):
    list_display   = ('code', 'name', 'order')
    search_fields  = ('code', 'name')
    ordering       = ('order', 'code')

admin.site.register([Year, Version, OrgUnit, Account, Service, CBU, CostCenter, InternalOrder], InfoObjectAdmin)

@admin.register(SLAProfile)
class SLAProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'response_time', 'resolution_time', 'availability')
    search_fields = ('name',)

@admin.register(KeyFigure)
class KeyFigureAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_percent')
    search_fields = ('code', 'name')

# ── Planning Layout & Dimensions ───────────────────────────────────────────
class PlanningDimensionInline(admin.TabularInline):
    model = PlanningDimension
    extra = 1

class PlanningKeyFigureInline(admin.TabularInline):
    model = PlanningKeyFigure
    extra = 1

class LayoutYearInline(admin.TabularInline):
    model = PlanningLayoutYear
    extra = 1
    fields = ('year', 'version')

@admin.register(PlanningLayout)
class PlanningLayoutAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'domain', 'default')
    inlines      = [PlanningDimensionInline, PlanningKeyFigureInline, LayoutYearInline]

@admin.register(PlanningLayoutYear)
class PlanningLayoutYearAdmin(admin.ModelAdmin):
    list_display       = ('layout', 'year', 'version')
    filter_horizontal  = ('org_units', 'row_dims')
    search_fields      = ('layout__code',)
    list_filter        = ('layout', 'year', 'version')

# ── Period & Grouping ──────────────────────────────────────────────────────
@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display  = ('code', 'name', 'order')
    ordering      = ('order',)
    search_fields = ('code', 'name')

@admin.register(PeriodGrouping)
class PeriodGroupingAdmin(admin.ModelAdmin):
    list_display = ('layout_year', 'months_per_bucket', 'label_prefix')
    list_filter  = ('months_per_bucket', 'layout_year')
    search_fields = ('layout_year__layout__code',)

# ── Planning Workflow & Sessions ───────────────────────────────────────────
@admin.register(PlanningSession)
class PlanningSessionAdmin(admin.ModelAdmin):
    list_display   = ('org_unit', 'layout_year', 'status', 'created_at')
    list_filter    = ('status', 'layout_year')
    search_fields  = ('org_unit__name',)
    actions        = ['make_completed', 'make_frozen']

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
        'request','session','version','year','period','org_unit',
        'service','account','driver_refs',
        'key_figure','value','uom','ref_value','ref_uom'
    )
    fields = readonly_fields
    can_delete = False
    show_change_link = True
    verbose_name_plural = "Planning Facts"

@admin.register(DataRequest)
class DataRequestAdmin(admin.ModelAdmin):
    list_display   = ('id', 'session', 'description', 'created_at')
    list_filter    = ('session__layout_year__layout',)
    search_fields  = ('description', 'id')
    inlines        = [FactInline]

@admin.register(PlanningFact)
class PlanningFactAdmin(admin.ModelAdmin):
    list_display  = (
        'session','version','year','period','org_unit',
        'service','account','key_figure','value','uom','ref_value','ref_uom'
    )
    list_filter   = ('year','period','uom','service','account','key_figure')
    search_fields = ('driver_refs',)
    readonly_fields = ('request',)
