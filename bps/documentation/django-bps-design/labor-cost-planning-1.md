You've provided crucial context\! Understanding that `version` and `year` are part of your `PlanningFact` (a fact table in a data warehousing sense) and `DataRequest` models, rather than directly on your `RateCard` and `Position` master data, significantly changes the ideal approach.

This setup indicates a strong desire for:

1.  **Auditable Planning Sessions/Versions:** Each `DataRequest` (which implicitly ties to a `PlanningSession` and `Version`) represents a specific set of planning inputs.
2.  **Flexible Fact Data:** `PlanningFact` allows for storing various metrics (`key_figure`) across different dimensions (OrgUnit, Service, Account, Period, Year, Version).

Given this, the previously suggested direct `ForeignKey` to `Year` on `RateCard` and `Position` would create a "redundancy" or a different kind of dependency than your `PlanningFact` system.

### Rethinking `RateCard` and `Position` in an EAV/Fact Table Context

The goal is to leverage your `PlanningFact` model for year and version control, while `RateCard` and `Position` define the *master data* or *templates* for these rates and positions.

**Core Idea:**

  * `RateCard` and `Position` should represent *generic definitions* of rates and positions (e.g., "Senior Python Developer Rate," "Open PM Position").
  * The **specific rate for a given year/version/period** (e.g., "Senior Python Developer Rate for 2025 Q1, Version A") will be stored as a `PlanningFact` entry.
  * Similarly, the **budgeted FTE for a specific position in a given year/version/period** will be a `PlanningFact` entry.

### Proposed Model Adjustments

Let's refine `RateCard` and `Position` to act more as master data, and then define how their *values* are stored in `PlanningFact`.

-----

#### 1\. Redefined `RateCard` (Master Data/Template)

`RateCard` now defines the *type* of rate, not the year-specific value.

```python
class Skill(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    def __str__(self): return self.name

class RateCardTemplate(models.Model): # Renamed to emphasize its template nature
    """
    Defines the structural elements of a rate. The actual rates (value)
    are stored as PlanningFact entries, linked by this template.
    """
    RESOURCE_CATEGORY_CHOICES = [
        ('EMP', 'Employee'),
        ('CON', 'Contractor'),
        ('MSP', 'MSP'),
    ]

    skill             = models.ForeignKey(Skill, on_delete=models.PROTECT)
    level             = models.CharField(max_length=20)      # e.g. Junior/Mid/Senior/Manager/Executive
    resource_category = models.CharField(max_length=20, choices=RESOURCE_CATEGORY_CHOICES,
                                         help_text="Type of resource (Employee, Contractor, MSP, etc.)")
    country           = models.CharField(max_length=50) # Could be FK to a Country model

    # Efficiency factor is still a property of the *type* of resource,
    # so it can live here, or also become a KeyFigure in PlanningFact.
    # For simplicity, keeping it here for now as a default/expected efficiency.
    efficiency_factor = models.DecimalField(max_digits=5, decimal_places=2,
                                            help_text="0.00-1.00 - Reflects effective productivity. For employees, often 1.0.")

    class Meta:
        unique_together = ('skill','level','resource_category','country') # No 'year' here
        ordering = ['skill','level','resource_category','country']
        verbose_name = "Rate Card Template"
        verbose_name_plural = "Rate Card Templates"

    def __str__(self):
        return (f"{self.resource_category} | {self.skill} ({self.level}) @ "
                f"{self.country}")

# Add KeyFigures for the actual rates and their components
class KeyFigure(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    # ... other attributes like is_rate, is_cost, is_revenue etc.
    def __str__(self): return self.name

# Pre-populate some KeyFigures for your rates:
# hourly_rate = KeyFigure.objects.create(code='HOURLY_RATE', name='Hourly Rate (Fully Loaded)')
# base_salary_hourly_equiv = KeyFigure.objects.create(code='BASE_SALARY_HRLY', name='Base Salary Hourly Equivalent')
# benefits_hourly_equiv = KeyFigure.objects.create(code='BENEFITS_HRLY', name='Benefits Hourly Equivalent')
# payroll_tax_hourly_equiv = KeyFigure.objects.create(code='PAYROLL_TAX_HRLY', name='Payroll Tax Hourly Equivalent')
# overhead_allocation_hourly = KeyFigure.objects.create(code='OVERHEAD_HRLY', name='Overhead Allocation Hourly')
```

**Changes and Reasoning:**

  * **`RateCardTemplate`**: Renamed to distinguish it from the actual *values* that will reside in `PlanningFact`.
  * **`year` removed from `RateCardTemplate`**: This model now solely defines the *structure* of a rate.
  * **`unique_together` updated**: `('skill','level','resource_category','country')` ensures you only define each template once.
  * **`hourly_rate` and its components removed**: These are the *values* that will change by year/version/period, so they belong in `PlanningFact`.
  * **`KeyFigure` Integration**: The actual hourly rates (and their components for employees) will be stored in `PlanningFact` with a `key_figure` pointing to `HOURLY_RATE`, `BASE_SALARY_HRLY`, etc.
  * **`driver_refs` in `PlanningFact`**: This is where you link the `PlanningFact` entry back to the `RateCardTemplate` master data.

-----

#### 2\. Redefined `Position` (Master Data/Template)

`Position` also becomes a template for roles, not tied to a specific year or version.

```python
class PositionTemplate(InfoObject): # Renamed
    """
    Defines a generic position or role. Actual budgeted FTEs and costs
    are stored as PlanningFact entries, linked by this template.
    """
    code        = models.CharField(max_length=20, unique=True) # Unique globally now
    skill       = models.ForeignKey(Skill, on_delete=models.PROTECT) # FK to Skill model
    level       = models.CharField(max_length=20)      # e.g. Junior/Mid/Senior/Manager/Executive
    department  = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True)
    # is_open and intended_resource_category relate to a *specific planning scenario*,
    # so they should ideally be handled by a KeyFigure in PlanningFact.

    class Meta(InfoObject.Meta):
        unique_together = None # No year, so `code` can be unique globally for a template
        ordering = ['code'] # Simple ordering for templates
        verbose_name = "Position Template"
        verbose_name_plural = "Position Templates"

    def __str__(self):
        return f"{self.code} ({self.skill}/{self.level})"

# New KeyFigures for Position budgeting:
# budgeted_fte = KeyFigure.objects.create(code='BUDGETED_FTE', name='Budgeted Full-Time Equivalent')
# position_status = KeyFigure.objects.create(code='POSITION_STATUS', name='Position Status (Open/Filled)')
# intended_category = KeyFigure.objects.create(code='INTENDED_CATEGORY', name='Intended Resource Category')
```

**Changes and Reasoning:**

  * **`PositionTemplate`**: Renamed to indicate it's a structural definition.
  * **`year` removed from `PositionTemplate`**: Budgeted FTE for a position will be a `PlanningFact`.
  * **`unique_together = ('year', 'code')` removed**: `code` should now be unique globally for the template.
  * **`fte`, `is_open`, `intended_resource_category` removed**: These are *values* or *attributes that change per planning scenario*. They should be `KeyFigure`s in `PlanningFact`.

-----

#### 3\. Adjustments to `PlanningFact`

The `PlanningFact` model will be the central place where all these values (rates, FTEs, position statuses) are stored, linked back to their respective templates.

```python
class PlanningFact(models.Model):
    """
    Core Models (EAV-style with fixed dimension FK)
    One “row” of plan data for a given DataRequest + Period.
    """
    request     = models.ForeignKey(DataRequest, on_delete=models.PROTECT)
    session     = models.ForeignKey(PlanningSession, on_delete=models.CASCADE)
    version     = models.ForeignKey(Version, on_delete=models.PROTECT)

    year        = models.ForeignKey(Year, on_delete=models.PROTECT)
    period      = models.ForeignKey(Period, on_delete=models.PROTECT)
    
    org_unit    = models.ForeignKey(OrgUnit, on_delete=models.PROTECT)

    service   = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT)
    account   = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT)

    # Optional domain-specific dimensions
    # THIS IS THE CRITICAL CHANGE: Link to your template models here
    driver_refs = models.JSONField(default=dict, help_text="e.g. {'rate_template_id':123, 'position_template_id':456}")

    key_figure  = models.ForeignKey(KeyFigure, on_delete=models.PROTECT)
    value       = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    uom         = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='+', null=True)
    ref_value   = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    ref_uom     = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='+', null=True)

    class Meta:
        # Re-evaluate unique_together, as driver_refs is JSON.
        # It's better to ensure that for a given (request, version, year, period, org_unit, service, account, key_figure),
        # there's only one entry for a specific driver reference.
        # This might require custom validation or a different strategy if driver_refs isn't just a single ID.
        # If driver_refs will contain ONLY one of `rate_template_id` or `position_template_id`,
        # then the unique_together should reflect that.
        unique_together = ('request', 'version', 'year', 'period', 'org_unit', 'service', 'account', 'key_figure', 'driver_refs') # Keep for now, but be mindful of JSON for uniqueness
        indexes = [
            models.Index(fields=['year', 'version', 'org_unit']),
            models.Index(fields=['key_figure']),
            # Add indexes for driver_refs if you often query by specific template IDs
            # models.Index(fields=[Key('driver_refs', opclass='jsonb_ops')]), # PostgreSQL specific
        ]
    # ... (rest of the methods)
```

**How to Use `PlanningFact` for Rates and Positions:**

**For Rates (e.g., Senior Python Developer Employee Hourly Rate for 2025, Q1, Version A):**

1.  **Define `RateCardTemplate`**:

      * `skill`: Python
      * `level`: Senior
      * `resource_category`: EMP
      * `country`: USA
      * (This template gets an `id`, say `101`)

2.  **Store the Rate Value in `PlanningFact`**:

      * `request`: (your specific DataRequest for this planning cycle)
      * `session`: (your PlanningSession)
      * `version`: (your Version for this plan, e.g., 'A')
      * `year`: (e.g., 2025)
      * `period`: (e.g., '01' for Jan)
      * `org_unit`: (e.g., 'IT Development')
      * `service`: (optional)
      * `account`: (optional, e.g., 'Labor Cost')
      * `driver_refs`: `{'rate_template_id': 101}`
      * `key_figure`: `HOURLY_RATE` (pre-defined KeyFigure)
      * `value`: `120.50` (the actual fully loaded hourly rate)
      * `uom`: `USD`

    You would repeat this for `BASE_SALARY_HRLY`, `BENEFITS_HRLY`, etc., each as a separate `PlanningFact` row, all linking to the same `rate_template_id: 101`.

**For Positions (e.g., Budgeted FTE for "DEV-001" in 2025, Q1, Version A):**

1.  **Define `PositionTemplate`**:

      * `code`: DEV-001
      * `skill`: Java
      * `level`: Mid
      * `department`: Engineering
      * (This template gets an `id`, say `201`)

2.  **Store Position Budget Data in `PlanningFact`**:

      * `request`, `session`, `version`, `year`, `period`, `org_unit`, `service`, `account` (as appropriate)
      * `driver_refs`: `{'position_template_id': 201}`
      * `key_figure`: `BUDGETED_FTE`
      * `value`: `1.0` (for 1 FTE)
      * `uom`: `FTE` (a UnitOfMeasure)

    *And for its status:*

      * `driver_refs`: `{'position_template_id': 201}`
      * `key_figure`: `POSITION_STATUS`
      * `value`: `1` (or some other code for 'Open')
      * `uom`: `Boolean` (or a custom UoM for status codes)

    *And for its intended resource category:*

      * `driver_refs`: `{'position_template_id': 201}`
      * `key_figure`: `INTENDED_CATEGORY`
      * `value`: `0` (or some code for 'EMP')
      * `uom`: `CategoryCode` (custom UoM for your `RESOURCE_CATEGORY_CHOICES`)

### Pros and Cons of this EAV/Fact Table Approach

**Pros:**

  * **Highly Flexible:** Easily add new `KeyFigure`s (metrics) without altering `PlanningFact` schema.
  * **Full Versioning and History:** Every piece of data is tied to a specific `Request`, `Session`, `Version`, `Year`, and `Period`. Excellent for auditing, "what-if" scenarios, and comparing different planning scenarios.
  * **Scalability for Dimensions:** If you introduce more dimensions, they can be added to `PlanningFact`.
  * **Normalized Master Data:** `RateCardTemplate` and `PositionTemplate` are clean, stable master data.

**Cons:**

  * **Increased Query Complexity:** Retrieving all attributes for a single rate or position (e.g., getting `HOURLY_RATE`, `BASE_SALARY_HRLY`, and `BENEFITS_HRLY` for one `RateCardTemplate`) requires multiple joins to `PlanningFact` and filtering, or complex aggregation queries.
  * **Data Entry/Management Complexity:** Entering a single "rate" might now involve creating multiple `PlanningFact` records (one for total hourly, one for salary component, one for benefits component, etc.). This needs careful UI/API design.
  * **`driver_refs` (JSONField) in `unique_together`**: While possible with PostgreSQL's JSONB operators, using `JSONField` in `unique_together` can be tricky and less performant for large datasets compared to direct FKs. You might need to enforce this uniqueness at the application level or reconsider `driver_refs`.
      * **Alternative for `driver_refs`:** If you often only link to *one* type of template at a time, consider having explicit `ForeignKey`s to `RateCardTemplate` and `PositionTemplate` directly on `PlanningFact`, but make them `null=True, blank=True` and mutually exclusive (enforced by validation).
    <!-- end list -->
    ```python
    class PlanningFact(models.Model):
        # ... existing fields
        rate_card_template = models.ForeignKey(RateCardTemplate, on_delete=models.PROTECT, null=True, blank=True)
        position_template = models.ForeignKey(PositionTemplate, on_delete=models.PROTECT, null=True, blank=True)

        class Meta:
            unique_together = (
                'request', 'version', 'year', 'period', 'org_unit', 'service', 'account', 'key_figure',
                'rate_card_template', 'position_template' # These would be nullable in unique_together
            )
            # You'd need to ensure only ONE of rate_card_template or position_template is set per row.
            # Or adjust unique_together if a row can refer to BOTH but for different KeyFigures.
    ```
    This explicit FK approach is generally more performant and easier to query than `JSONField` for primary links.

### Conclusion

Your existing `PlanningFact` and `DataRequest` structure is designed for highly flexible, versioned, and period-based data. To integrate `RateCard` and `Position` effectively into this, they must become **master data templates** that define the *structure* of what's being planned, while their actual *values* for a given year/version/period are stored as `PlanningFact` entries.

This is a powerful but more complex design. It requires careful planning of your `KeyFigure`s and how `driver_refs` (or explicit template FKs) link back to your master data. The main challenge will be data retrieval and ensuring data integrity given the `JSONField` for `driver_refs` in `unique_together` (if you stick with that).