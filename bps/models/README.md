# BPS Models Documentation

## Overview

The BPS models are organized into domain-specific modules for better maintainability and separation of concerns.

## Model Structure

### Core Models (`models.py`)
- **PlanningFact**: Central fact table with EAV pattern using JSONB
- **DataRequest**: Audit trail for all planning operations
- **KeyFigure**: Configurable metrics (FTE, COST, etc.)
- **UnitOfMeasure**: Units with conversion support
- **ConversionRate**: Exchange rates between units
- **UserMaster**: Links users to organizational structure

### Dimension Models (`models_dimension.py`)
- **OrgUnit**: Hierarchical organizational units
- **Service**: Business services/systems
- **Account**: Chart of accounts
- **CBU**: Customer Business Units
- **CostCenter**: Cost center hierarchy
- **InternalOrder**: Internal order tracking

### Layout Models (`models_layout.py`)
- **PlanningLayout**: Layout templates
- **PlanningLayoutYear**: Year-specific layout configurations
- **PlanningLayoutDimension**: Dimension configuration per layout
- **LayoutDimensionOverride**: Year-specific dimension overrides

### Period Models (`models_period.py`)
- **Year**: Planning years
- **Period**: Monthly periods (01-12)
- **PeriodGrouping**: Flexible period groupings (monthly, quarterly)

### Workflow Models (`models_workflow.py`)
- **Version**: Planning versions (ACTUAL, DRAFT, PLAN)
- **PlanningScenario**: Multi-step planning scenarios
- **ScenarioStep**: Individual workflow steps
- **PlanningSession**: Session per OrgUnit within scenario

### Function Models (`models_function.py`)
- **Formula**: Planning formulas with conditional logic
- **SubFormula**: Reusable formula components
- **Constant**: Named constants for formulas
- **PlanningFunction**: Copy, distribute, convert operations
- **ReferenceData**: Reference data for formulas

### View Models (`models_view.py`)
- **PivotedPlanningFact**: Materialized view for reporting
- **PlanningFactPivotRow**: Pivoted fact representation

## Key Design Patterns

### EAV (Entity-Attribute-Value) Pattern
The `PlanningFact` model uses JSONB `extra_dimensions_json` field to store flexible dimension combinations without schema changes.

### ContentTypes Integration
Dimensions are linked via Django's ContentTypes framework, enabling pluggable dimension models.

### Hierarchical Data
- **OrgUnit**: Parent-child relationships for organizational hierarchy
- **Account**: Chart of accounts hierarchy
- **CostCenter**: Cost center hierarchy

### Audit Trail
All changes tracked through:
- **DataRequest**: Groups related changes
- **DataRequestLog**: Individual fact changes
- **FormulaRun**: Formula execution audit

## Database Views

### Pivoted Planning Fact View
```sql
CREATE OR REPLACE VIEW pivoted_planningfact AS
SELECT
    pf.version_id AS version,
    pf.year_id AS year,
    pf.org_unit_id AS org_unit,
    pf.service_id AS service,
    pf.account_id AS account,
    pf.key_figure_id AS key_figure,
    -- Monthly columns (01-12)
    MAX(CASE WHEN per.code = '01' THEN pf.value END) AS m01,
    MAX(CASE WHEN per.code = '02' THEN pf.value END) AS m02,
    -- ... (continues for all 12 months)
    SUM(pf.value) AS total_value
FROM bps_planningfact AS pf
JOIN bps_period AS per ON pf.period_id = per.id
GROUP BY pf.version_id, pf.year_id, pf.org_unit_id, 
         pf.service_id, pf.account_id, pf.key_figure_id;
```

## Migration Notes

### Creating Empty Migrations
```bash
python manage.py makemigrations --empty bps
```

### Custom Migrations
- Database views creation
- Index optimization
- Data migration scripts

## Performance Considerations

### Indexes
- GIN indexes on JSONB fields
- Composite indexes on frequently queried combinations
- Hierarchical path indexes for tree structures

### Query Optimization
- Use `select_related()` for foreign keys
- Use `prefetch_related()` for many-to-many relationships
- Avoid N+1 queries in dimension lookups

### Caching Strategy
- Cache dimension lookups
- Cache layout configurations
- Use Redis for session data

## Best Practices

### Model Design
- Keep models focused and cohesive
- Use abstract base classes for common fields
- Implement proper `__str__` methods
- Add helpful model metadata

### Relationships
- Use appropriate `on_delete` behaviors
- Consider performance implications of relationships
- Use `related_name` for clarity

### Validation
- Implement model-level validation
- Use custom validators for business rules
- Validate JSONB structure where needed

## Future Enhancements

### Planned Improvements
- Star schema data mart for analytics
- Enhanced hierarchy management with django-mptt
- Temporal data support for historical tracking
- Advanced caching with Redis integration