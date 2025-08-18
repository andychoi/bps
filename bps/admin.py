# bps/admin.py

from django.contrib import admin
from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Count
from .models.admin_proxy import PlanningAdminDashboard
from django.template.response import TemplateResponse

from .models.models import (
    UnitOfMeasure, ConversionRate, Constant, SubFormula, Formula, FormulaRun, FormulaRunEntry,
    PlanningFunction, ReferenceData, KeyFigure, DataRequest, DataRequestLog, PlanningFact,
    PlanningSession, PlanningStage, Period, PeriodGrouping, RateCard, Position, Resource, Skill
)
from .models.models_extras import DimensionKey, PlanningFactExtra

from .models.models_layout import (
    PlanningLayout, PlanningLayoutYear, PlanningLayoutDimension, LayoutDimensionOverride, PlanningKeyFigure
)

from .models.models_dimension import (
    Year, Version, OrgUnit, Account, Service, CBU, CostCenter, InternalOrder
)

from .models.models_resource import Skill, Resource
from .models.models_workflow import (
    PlanningScenario, ScenarioStep, ScenarioStage, ScenarioFunction, ScenarioOrgUnit
)

from .admin_access import OrgUnitAccessAdmin, DelegationAdmin

@admin.register(PlanningAdminDashboard)
class PlanningAdminDashboardAdmin(admin.ModelAdmin):
    change_list_template = "admin/bps/planning_dashboard.html"

    def changelist_view(self, request, extra_context=None):
        stats = {
            "layouts": PlanningLayout.objects.count(),
            "layout_years": PlanningLayoutYear.objects.count(),
            "key_figs": PlanningKeyFigure.objects.count(),
            "scenarios": PlanningScenario.objects.count(),
            "years": Year.objects.count(),
            "versions": Version.objects.count(),
            "org_units": OrgUnit.objects.count(),
        }
        layouts = (
            PlanningLayout.objects
            .annotate(n_dims=Count("dimensions"), n_kf=Count("planningkeyfigure"))
            .order_by("code")
        )
        ctx = {
            "title": "Planning Admin Dashboard",
            "stats": stats,
            "layouts": layouts,
        }
        return TemplateResponse(request, self.change_list_template, ctx)
    
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
    list_display   = ('code', 'name', 'is_percent', 'display_decimals')
    list_filter    = ('is_percent',)
    search_fields  = ('code', 'name')
    fields         = ('code', 'name', 'is_percent', 'default_uom', 'display_decimals')


# ── Planning Layout & Dimensions ───────────────────────────────────────────

# class PlanningDimensionInline(admin.TabularInline):
#     model = PlanningDimension
#     extra = 1


class PlanningKeyFigureInline(admin.TabularInline):
    model = PlanningKeyFigure
    extra = 1
    fields = ("key_figure", "is_editable", "is_computed", "is_yearly", "formula", "display_order")
    ordering = ("display_order",)


class LayoutYearInline(admin.TabularInline):
    model  = PlanningLayoutYear
    extra  = 1
    fields = ('year', 'version')

# Template-level dimensions live under the Layout now
class PlanningLayoutDimensionInlineForm(forms.ModelForm):
    class Meta:
        model = PlanningLayoutDimension
        fields = ("content_type", "is_row", "is_column", "is_header", "order", "group_priority")
    def clean(self):
        cleaned = super().clean()
        flags = [cleaned.get("is_row"), cleaned.get("is_column"), cleaned.get("is_header")]
        if sum(bool(x) for x in flags) != 1:
            raise ValidationError("Exactly one of Row / Column / Header must be checked.")
        return cleaned

class PlanningLayoutDimensionInline(admin.TabularInline):
    model = PlanningLayoutDimension
    form  = PlanningLayoutDimensionInlineForm
    extra = 0
    fields = ("content_type", "is_row", "is_column", "is_header", "order", "group_priority")
    ordering = ("order",)

# Per-year overrides inline under LayoutYear
class LayoutDimensionOverrideInline(admin.TabularInline):
    model = LayoutDimensionOverride
    extra = 0
    fields = ("dimension", "allowed_values", "filter_criteria")


@admin.register(PlanningLayout)
class PlanningLayoutAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'domain', 'default')
    search_fields = ("code", "name")
    inlines = [PlanningLayoutDimensionInline, PlanningKeyFigureInline, LayoutYearInline]
    
# Show template-level dimensions inline on the layout page too
# PlanningLayoutAdmin.inlines.insert(0, PlanningLayoutDimensionInline)


class PeriodGroupingInline(admin.TabularInline):
    model = PeriodGrouping
    extra = 0
    fields = ("months_per_bucket", "label_prefix")

class PlanningLayoutYearAdminForm(forms.ModelForm):
    class Meta:
        model = PlanningLayoutYear
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, "instance", None)
        if not (instance and instance.pk):
            return
        header_cfg = instance.header_dims or {}

        # Build header pickers using template dimensions + per-year overrides
        overrides = {
            o.dimension_id: o for o in instance.dimension_overrides.select_related("dimension__content_type")
        }
        for dim in instance.layout.dimensions.filter(is_header=True).select_related("content_type").order_by("order"):
            Model = dim.content_type.model_class()
            fname = f"hdr_{dim.content_type.model}"

            qs = Model.objects.all()
            ov = overrides.get(dim.id)
            if ov and ov.allowed_values:
                pks = [v for v in ov.allowed_values if isinstance(v, int)]
                codes = [v for v in ov.allowed_values if isinstance(v, str)]
                if pks:
                    qs = qs.filter(pk__in=pks)
                if codes and hasattr(Model, "code"):
                    qs = qs.filter(code__in=codes)

            self.fields[fname] = forms.ModelChoiceField(
                queryset=qs,
                required=False,
                label=f"Header: {Model._meta.verbose_name.title()}",
            )

            raw = header_cfg.get(dim.content_type.model)
            if raw:
                try:
                    if isinstance(raw, int):
                        self.fields[fname].initial = raw
                    elif hasattr(Model, "code"):
                        inst = qs.filter(code=raw).first()
                        if inst:
                            self.fields[fname].initial = inst.pk
                except Exception:
                    pass

    def save(self, commit=True):
        inst = super().save(commit=False)
        header = dict(inst.header_dims or {})
        for dim in inst.layout.dimensions.filter(is_header=True).select_related("content_type"):
            fname = f"hdr_{dim.content_type.model}"
            sel = self.cleaned_data.get(fname)
            header[dim.content_type.model] = sel.pk if sel else None
        inst.header_dims = header
        if commit:
            inst.save()
            self.save_m2m()
        return inst

@admin.register(PlanningLayoutYear)
class PlanningLayoutYearAdmin(admin.ModelAdmin):
    form = PlanningLayoutYearAdminForm
    list_display      = ("layout", "year", "version", "header_summary")
    list_filter       = ("layout", "year", "version")
    search_fields     = ("layout__code", "layout__name")
    filter_horizontal = ("org_units",)  # row_dims removed
    inlines           = [LayoutDimensionOverrideInline, PeriodGroupingInline]

    def header_summary(self, obj):
        if not obj.header_dims:
            return "—"
        parts = []
        from django.contrib.contenttypes.models import ContentType
        for k, v in obj.header_dims.items():
            try:
                ct = ContentType.objects.get(model=k)
                Model = ct.model_class()
                if not v:
                    continue
                inst = Model.objects.filter(pk=v).first() if isinstance(v, int) else (
                    Model.objects.filter(code=v).first() if hasattr(Model, "code") else None
                )
                if inst:
                    parts.append(f"{Model._meta.verbose_name.title()}: {inst}")
            except Exception:
                continue
        return " • ".join(parts) or "—"
    header_summary.short_description = "Header Defaults"


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

@admin.register(DimensionKey)
class DimensionKeyAdmin(admin.ModelAdmin):
    list_display = ('key', 'content_type')
    list_filter = ('content_type',)
    search_fields = ('key',)

@admin.register(PlanningFactExtra)
class PlanningFactExtraAdmin(admin.ModelAdmin):
    list_display = ('fact', 'key', 'content_type', 'object_id', 'value_obj')
    list_filter = ('key', 'content_type')
    search_fields = ('fact__id', 'key__key')    