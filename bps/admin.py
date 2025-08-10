# bps/admin.py

from django.contrib import admin
from django import forms
from django.contrib.contenttypes.models import ContentType

from .models.models import (
    UnitOfMeasure, ConversionRate,
    Constant, SubFormula, Formula, FormulaRun, FormulaRunEntry,
    PlanningFunction, ReferenceData,
    KeyFigure, DataRequest, DataRequestLog, PlanningFact,
    PlanningSession, PlanningStage,
    PlanningLayout, PlanningLayoutYear, PlanningDimension, PlanningKeyFigure,
    Period, PeriodGrouping, RateCard, Position, PlanningLayoutDimension
)
from .models.models_dimension import (
    Year, Version, OrgUnit, Account, Service, CBU, CostCenter, InternalOrder
)
from .models.models_resource import Skill, Resource
from .models.models_workflow import (
    PlanningScenario, ScenarioStep, ScenarioStage, ScenarioFunction, ScenarioOrgUnit
)


# ── Units of Measure & Conversion Rates ────────────────────────────────────

@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display   = ('code', 'name', 'is_base')
    search_fields  = ('code', 'name')


@admin.register(ConversionRate)
class ConversionRateAdmin(admin.ModelAdmin):
    list_display  = ('from_uom', 'to_uom', 'factor')
    list_filter   = ('from_uom', 'to_uom')


# ── Constants & Formulas ───────────────────────────────────────────────────

@admin.register(Constant)
class ConstantAdmin(admin.ModelAdmin):
    list_display   = ('name', 'value')
    search_fields  = ('name',)


@admin.register(SubFormula)
class SubFormulaAdmin(admin.ModelAdmin):
    list_display   = ('name', 'layout')
    search_fields  = ('name', 'layout__code')
    list_filter    = ('layout',)


@admin.register(Formula)
class FormulaAdmin(admin.ModelAdmin):
    list_display   = ('name', 'layout')
    search_fields  = ('name', 'layout__code')
    list_filter    = ('layout',)


# ── Formula Runs & Entries ────────────────────────────────────────────────

class FormulaRunEntryInline(admin.TabularInline):
    model            = FormulaRunEntry
    extra            = 0
    fields           = ('record', 'key', 'old_value', 'new_value')
    readonly_fields  = fields
    can_delete       = False
    show_change_link = True


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
    list_display   = ('name', 'layout', 'function_type')
    list_filter    = ('function_type', 'layout')
    search_fields  = ('name',)


@admin.register(ReferenceData)
class ReferenceDataAdmin(admin.ModelAdmin):
    list_display   = ('name', 'source_year', 'source_version')
    search_fields  = ('name',)


# ── Scenario Models ───────────────────────────────────────────────────────

@admin.register(PlanningScenario)
class PlanningScenarioAdmin(admin.ModelAdmin):
    list_display   = ('code', 'name', 'layout_year', 'is_active', 'created_at')
    list_filter    = ('is_active', 'layout_year__layout', 'layout_year__year', 'layout_year__version')
    search_fields  = ('code', 'name')
    ordering       = ('code',)


@admin.register(ScenarioStage)
class ScenarioStageAdmin(admin.ModelAdmin):
    list_display   = ('scenario', 'stage', 'order')
    list_filter    = ('scenario', 'stage')
    ordering       = ('scenario', 'order')


@admin.register(ScenarioStep)
class ScenarioStepAdmin(admin.ModelAdmin):
    list_display   = ('scenario', 'stage', 'layout', 'order')
    list_filter    = ('scenario', 'stage', 'layout')
    ordering       = ('scenario', 'order')


@admin.register(ScenarioFunction)
class ScenarioFunctionAdmin(admin.ModelAdmin):
    list_display   = ('scenario', 'function', 'order')
    list_filter    = ('scenario', 'function')
    ordering       = ('scenario', 'order')


@admin.register(ScenarioOrgUnit)
class ScenarioOrgUnitAdmin(admin.ModelAdmin):
    list_display   = ('scenario', 'org_unit', 'order')
    list_filter    = ('scenario', 'org_unit')
    ordering       = ('scenario', 'order')


# ── InfoObject‐derived Dimensions ───────────────────────────────────────────

class InfoObjectAdmin(admin.ModelAdmin):
    list_display  = ('code', 'name', 'order')
    search_fields = ('code', 'name')
    ordering      = ('order', 'code')

admin.site.register(
    [Year, Version, OrgUnit, Account, Service, CBU, CostCenter, InternalOrder],
    InfoObjectAdmin
)


# ── Skill & Resource ──────────────────────────────────────────────────────

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display  = ('name',)
    search_fields = ('name',)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display   = ('unique_id', 'display_name', 'resource_type', 'current_skill', 'current_level')
    list_filter    = ('resource_type', 'current_skill', 'current_level')
    search_fields  = ('unique_id', 'display_name')


# ── Key Figures ────────────────────────────────────────────────────────────

@admin.register(KeyFigure)
class KeyFigureAdmin(admin.ModelAdmin):
    list_display   = ('code', 'name', 'is_percent')
    search_fields  = ('code', 'name')


# ── Planning Layout & Dimensions ───────────────────────────────────────────

class PlanningDimensionInline(admin.TabularInline):
    model = PlanningDimension
    extra = 1


class PlanningKeyFigureInline(admin.TabularInline):
    model = PlanningKeyFigure
    extra = 1


class LayoutYearInline(admin.TabularInline):
    model  = PlanningLayoutYear
    extra  = 1
    fields = ('year', 'version')


@admin.register(PlanningLayout)
class PlanningLayoutAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'domain', 'default')
    search_fields = ("code", "name")
    inlines      = [PlanningDimensionInline, PlanningKeyFigureInline, LayoutYearInline]

class PlanningLayoutDimensionInline(admin.TabularInline):
    model = PlanningLayoutDimension
    extra = 0
    fields = ("content_type", "is_row", "is_column", "is_header", "order", "allowed_values", "filter_criteria")
    ordering = ("order",)

class PeriodGroupingInline(admin.TabularInline):
    model = PeriodGrouping
    extra = 0
    fields = ("months_per_bucket", "label_prefix")

class PlanningLayoutYearAdminForm(forms.ModelForm):
    """
    Dynamically render a field per header dimension so admins can pick the slice.
    Saves selected PKs back into header_dims JSON as { 'ModelName': <pk or None>, ... }.
    """
    class Meta:
        model = PlanningLayoutYear
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance = self.instance if self.instance and self.instance.pk else None
        header_cfg = (instance.header_dims or {}) if instance else {}

        # For each PLD flagged as header, render a ModelChoiceField for its model
        if instance:
            for pld in instance.layout_dimensions.select_related("content_type").filter(is_header=True).order_by("order"):
                Model = pld.content_type.model_class()
                field_name = f"hdr_{pld.content_type.model}"  # e.g. hdr_orgunit, hdr_service, hdr_position …

                qs = Model.objects.all()
                # If allowed_values is provided, restrict
                if pld.allowed_values:
                    # allow IDs in allowed_values (ints) or codes (strings) if the model has a 'code' field
                    if hasattr(Model, "code"):
                        qs = qs.filter(code__in=[v for v in pld.allowed_values if isinstance(v, str)])
                    else:
                        qs = qs.filter(pk__in=[v for v in pld.allowed_values if isinstance(v, int)])

                initial_pk = header_cfg.get(pld.content_type.model)
                self.fields[field_name] = forms.ModelChoiceField(
                    queryset=qs,
                    required=False,
                    label=f"Header: {Model._meta.verbose_name.title()}"
                )
                if initial_pk:
                    try:
                        self.fields[field_name].initial = qs.get(pk=initial_pk).pk
                    except Model.DoesNotExist:
                        pass  # ignore stale selection

    def clean(self):
        cleaned = super().clean()
        # Ensure period_grouping stays present in header_dims if already used
        return cleaned

    def save(self, commit=True):
        inst = super().save(commit=False)
        header = inst.header_dims or {}
        # Carry forward non-dimension header settings (e.g., period_grouping_id)
        # Then overwrite/add dimension selections
        if inst.pk:
            for pld in inst.layout_dimensions.select_related("content_type").filter(is_header=True):
                field_name = f"hdr_{pld.content_type.model}"
                sel = self.cleaned_data.get(field_name)
                header[pld.content_type.model] = sel.pk if sel else None
        inst.header_dims = header
        if commit:
            inst.save()
            self.save_m2m()
        return inst
    
@admin.register(PlanningLayoutYear)
class PlanningLayoutYearAdmin(admin.ModelAdmin):
    form = PlanningLayoutYearAdminForm
    list_display      = ('layout', 'year', 'version')
    filter_horizontal = ('org_units', 'row_dims')
    search_fields     = ('layout__code',)
    list_filter       = ('layout', 'year', 'version')
    inlines = [PlanningLayoutDimensionInline, PeriodGroupingInline]


# ── Period & Grouping ──────────────────────────────────────────────────────

@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display   = ('code', 'name', 'order')
    ordering       = ('order',)
    search_fields  = ('code', 'name')


@admin.register(PeriodGrouping)
class PeriodGroupingAdmin(admin.ModelAdmin):
    list_display   = ('layout_year', 'months_per_bucket', 'label_prefix')
    list_filter    = ('months_per_bucket', 'layout_year')
    search_fields  = ('layout_year__layout__code',)


# ── Planning Workflow & Sessions ───────────────────────────────────────────

@admin.register(PlanningStage)
class PlanningStageAdmin(admin.ModelAdmin):
    list_display       = ('order', 'code', 'name', 'can_run_in_parallel')
    list_display_links = ('code',)
    list_editable      = ('order', 'name', 'can_run_in_parallel')
    ordering           = ('order',)


@admin.register(PlanningSession)
class PlanningSessionAdmin(admin.ModelAdmin):
    list_display   = ('org_unit', 'scenario', 'status', 'created_at')
    list_filter    = ('status', 'scenario')
    search_fields  = ('org_unit__name', 'scenario__code')
    actions        = ('make_completed', 'make_frozen')

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
    model              = PlanningFact
    extra              = 0
    readonly_fields    = (
        'request', 'session', 'version', 'year', 'period', 'org_unit',
        'service', 'account', 'key_figure', 'value', 'uom', 'ref_value', 'ref_uom'
    )
    fields             = readonly_fields
    can_delete         = False
    show_change_link   = True
    verbose_name_plural = "Planning Facts"


class DataRequestLogInline(admin.TabularInline):
    model              = DataRequestLog
    extra              = 0
    readonly_fields    = ('fact', 'old_value', 'new_value', 'created_at', 'created_by')
    fields             = readonly_fields
    can_delete         = False
    show_change_link   = True
    verbose_name_plural = "Change Log"


@admin.register(DataRequest)
class DataRequestAdmin(admin.ModelAdmin):
    list_display  = ('id', 'session', 'description', 'action_type', 'is_summary', 'created_at')
    list_filter   = ('action_type', 'is_summary')
    inlines       = [FactInline, DataRequestLogInline]
    search_fields = ('description',)


@admin.register(PlanningFact)
class PlanningFactAdmin(admin.ModelAdmin):
    list_display   = (
        'session', 'version', 'year', 'period', 'org_unit',
        'service', 'account', 'key_figure', 'value', 'uom', 'ref_value', 'ref_uom'
    )
    list_filter    = ('year', 'period', 'uom', 'service', 'account', 'key_figure')
    search_fields  = ('key_figure__code', 'org_unit__name')

@admin.register(RateCard)
class RateCardAdmin(admin.ModelAdmin):
    list_display = (
        'year',
        'skill',
        'level',
        'resource_type',
        'country',
        'hourly_rate',
        'efficiency_factor',
    )
    list_filter = ('year','resource_type','country')
    search_fields = ('skill__name','level')

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('year','code','skill','level','fte','is_open')
    list_filter  = ('year','level','is_open')
    search_fields = ('code','skill__name')    