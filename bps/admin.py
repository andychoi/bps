# admin.py
from django.contrib import admin
from bps.models import Constant, SubFormula, Formula
from bps.formula_executor import FormulaExecutor

@admin.register(Constant)
class ConstantAdmin(admin.ModelAdmin):
    list_display = ('name', 'value')

@admin.register(SubFormula)
class SubFormulaAdmin(admin.ModelAdmin):
    list_display = ('name', 'layout')

@admin.register(Formula)
class FormulaAdmin(admin.ModelAdmin):
    list_display = ('name', 'layout', 'loop_dimension')
    actions = ['execute_formula', 'preview_formula']

    def execute_formula(self, request, queryset):
        for f in queryset:
            FormulaExecutor(f, preview=False).execute()
        self.message_user(request, "Formulas executed.")
    execute_formula.short_description = "Execute selected formulas"

    def preview_formula(self, request, queryset):
        for f in queryset:
            FormulaExecutor(f, preview=True).execute()
        self.message_user(request, "Preview completed.")
    preview_formula.short_description = "Preview selected formulas"


from .models import Hierarchy, HierarchyNode

class HierarchyNodeInline(admin.TabularInline):
    model = HierarchyNode
    extra = 1
    fields = ('name', 'parent', 'regex', 'order')
    show_change_link = True

@admin.register(Hierarchy)
class HierarchyAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    inlines = [HierarchyNodeInline]


@admin.register(HierarchyNode)
class HierarchyNodeAdmin(admin.ModelAdmin):
    list_display  = ('name', 'hierarchy', 'parent', 'order')
    list_filter   = ('hierarchy',)
    search_fields = ('name', 'regex')