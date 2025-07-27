Your current PlanningFact model is a good baseline, but to fully meet the extensive requirements for a captive IT company’s service-cost planning—particularly related to resource capacity, employee/contractor management, outsourcing, software cost drivers, admin costs, and cross-allocation across services/systems—you’ll need several enhancements and additional, specialized models.

Here’s a comprehensive assessment and revised recommended data model for your scenario:

⸻

🎯 A. Limitations of the Current PlanningFact Model

Your current model is insufficient due to:
	•	Lack of detail: No dedicated fields for:
	•	Skill Groups and Levels
	•	Resource Types (Employee, Contractor, MSP)
	•	Positions (Existing, Open, New)
	•	Allocation details (Insourcing/Outsourcing ratio, MSP country, efficiency, hourly rates)
	•	Software-specific attributes (licenses, servers, users)
	•	Admin costs and allocation
	•	Shared services allocations across CBUs
	•	Inflexibility:
Using only a single product and account dimension won’t sufficiently represent multi-dimensional allocations.

⸻

🎯 B. Recommended Model Enhancements

A detailed, extended model structure would be:

✅ 1. SkillGroup & Level (Dimension Tables)

class SkillGroup(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)

class SkillLevel(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50)

Examples:

SkillGroup	SkillLevel
Manager	L1, L2
Architect	Senior, Junior
BA/BSA	Senior, Mid, Junior
Developer	Senior, Mid, Junior
QA	Senior, Mid, Junior


⸻

✅ 2. Resource & Position Tracking

class Position(models.Model):
    POSITION_TYPE_CHOICES = [('EXISTING', 'Existing'), ('OPEN', 'Open'), ('NEW', 'New')]
    position_no = models.CharField(max_length=20, null=True, blank=True, unique=True)
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.CASCADE)
    skill_group = models.ForeignKey(SkillGroup, on_delete=models.PROTECT)
    skill_level = models.ForeignKey(SkillLevel, on_delete=models.PROTECT)
    position_type = models.CharField(max_length=10, choices=POSITION_TYPE_CHOICES)
    available_man_months = models.DecimalField(max_digits=6, decimal_places=2, default=12)


⸻

✅ 3. Outsourcing/MSP Management

class OutsourcingPlan(models.Model):
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.CASCADE)
    internal_order = models.ForeignKey('InternalOrder', null=True, on_delete=models.SET_NULL)
    skill_group = models.ForeignKey(SkillGroup, on_delete=models.PROTECT)
    country = models.CharField(max_length=30)
    efficiency_factor = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    sourcing_country = models.CharField(max_length=30)


⸻

✅ 4. System/Service Dimension

class SystemService(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.CASCADE, related_name='systems')
    cbu = models.ForeignKey(CBU, on_delete=models.SET_NULL, null=True, blank=True)
    is_shared_service = models.BooleanField(default=False)


⸻

✅ 5. Software Cost Drivers

class SoftwareCost(models.Model):
    software_name = models.CharField(max_length=100)
    cost_driver_type = models.CharField(max_length=50, choices=[('LICENSE', 'License'), ('SERVER', 'Server'), ('USER', 'User')])
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)


⸻

✅ 6. Enhanced Planning Fact Model

With the above dimensions clearly defined, we integrate these to the main planning fact table.

class PlanningFact(models.Model):
    request = models.ForeignKey(DataRequest, on_delete=models.PROTECT)
    session = models.ForeignKey(PlanningSession, on_delete=models.CASCADE)
    period = models.ForeignKey(Period, on_delete=models.PROTECT)
    year = models.ForeignKey(Year, on_delete=models.PROTECT)
    version = models.ForeignKey(Version, on_delete=models.PROTECT)
    
    # Core dimensions
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.PROTECT)
    system_service = models.ForeignKey(SystemService, null=True, blank=True, on_delete=models.PROTECT)
    skill_group = models.ForeignKey(SkillGroup, null=True, blank=True, on_delete=models.PROTECT)
    skill_level = models.ForeignKey(SkillLevel, null=True, blank=True, on_delete=models.PROTECT)
    position = models.ForeignKey(Position, null=True, blank=True, on_delete=models.PROTECT)
    outsourcing_plan = models.ForeignKey(OutsourcingPlan, null=True, blank=True, on_delete=models.PROTECT)
    internal_order = models.ForeignKey('InternalOrder', null=True, blank=True, on_delete=models.PROTECT)
    software_cost = models.ForeignKey(SoftwareCost, null=True, blank=True, on_delete=models.PROTECT)
    cbu = models.ForeignKey(CBU, null=True, blank=True, on_delete=models.PROTECT)

    # Cost Values
    quantity = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    quantity_uom = models.ForeignKey(UnitOfMeasure, null=True, on_delete=models.PROTECT, related_name='+')
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount_uom = models.ForeignKey(UnitOfMeasure, null=True, on_delete=models.PROTECT, related_name='+')

    class Meta:
        unique_together = ('session', 'period', 'org_unit', 'version', 'year', 'system_service',
                           'skill_group', 'skill_level', 'position', 'outsourcing_plan',
                           'internal_order', 'software_cost', 'cbu')


⸻

🎯 C. Planning Workflow Enhancements

Track the planning completion explicitly per org unit:

class PlanningSession(models.Model):
    layout_year = models.ForeignKey(PlanningLayoutYear, on_delete=models.CASCADE)
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[('DRAFT', 'Draft'), ('COMPLETED', 'Completed'), ('REVIEW', 'Review'), ('FROZEN', 'Frozen')], default='DRAFT')
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')


⸻

🎯 D. Is this Enhanced Model Sufficient?

Yes, the revised structure addresses your specific business requirements:
	•	Captures skill-group/level allocations clearly.
	•	Manages detailed positions & available man-months.
	•	Supports detailed outsourcing plan dimensions (efficiency, hourly rates).
	•	Handles shared service allocation through explicit dimensions.
	•	Allows detailed tracking of software-related costs by defined cost drivers.
	•	Admin costs and allocations can be handled through InternalOrder or Account.
	•	Supports planning per org unit clearly, with relationships to System/Service & CBUs.
	•	Flexible enough to handle annual adjustments or changing dimensions.

⸻

🎯 E. Further Recommendations
	•	Indexes: To enhance performance, index heavily queried fields (org_unit, system_service, skill_group, period, year, version).
	•	Aggregation Cache: Use pre-computed summaries or OLAP cubes for quicker reporting.
	•	Planning Workflow Automation: Incorporate automated workflow tasks to facilitate review, approval, and version freezing.

⸻

📌 Conclusion & Best Practice References

The proposed enhanced PlanningFact and related models are robust and sufficiently comprehensive for IT service-cost planning. Similar dimensional designs and concepts are standard in tools like SAP BW-BPS, SAP Analytics Cloud, Oracle EPM Cloud, and Anaplan.

Your model is now well-positioned to support complex, multi-dimensional, scenario-based IT planning.


Thank you for the clarification. Your original intent — to support domain-specific planning layouts dynamically through admin configuration — is both powerful and aligns with advanced planning solutions like SAP BW-BPS, Anaplan, or Oracle PBCS.

Given your enterprise-scale planning requirements, we recommend a hybrid architecture that combines:

⸻

✅ Recommended Architecture Overview

Layer	Approach
1. Core Models	Flexible EAV-based fact model with special-case dimensions normalized (e.g., OrgUnit, Version, Period, Year).
2. Planning Layout Metadata	Admin-defined PlanningLayout, PlanningDimension, and PlanningKeyFigure models to define forms/tables.
3. Planning Domain Templates	Each planning domain (Resource, Demand, Cost, etc.) gets its own layout configuration and form logic.
4. Rendering Engine	Dynamic form/grid builder using Django + Vue + Bootstrap5 (or AG Grid) based on layout metadata.
5. Storage	Store facts in a single normalized EAV table (e.g., PlanningFact) or domain-specific fact tables (if required for performance).


⸻

🔧 1. Core Models (EAV-style with fixed dimension FK)

class PlanningFact(models.Model):
    request     = models.ForeignKey(DataRequest, on_delete=models.PROTECT)
    session     = models.ForeignKey(PlanningSession, on_delete=models.CASCADE)
    org_unit    = models.ForeignKey(OrgUnit, on_delete=models.PROTECT)
    version     = models.ForeignKey(Version, on_delete=models.PROTECT)
    year        = models.ForeignKey(Year, on_delete=models.PROTECT)
    period      = models.ForeignKey(Period, on_delete=models.PROTECT)
    
    # Optional domain-specific dimensions
    driver_refs = models.JSONField(default=dict, help_text="e.g. {'Position':123, 'SkillGroup':'Developer'}")

    # Key figure
    key_figure  = models.CharField(max_length=100)
    amount      = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    quantity    = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    uom         = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, null=True)

    class Meta:
        unique_together = ('request', 'period', 'org_unit', 'version', 'year', 'key_figure', 'driver_refs')


⸻

🧱 2. Planning Layout Admin Models

a) PlanningLayout

Defines a specific domain template (e.g., Resource Planning, Cost Allocation).

class PlanningLayout(models.Model):
    code = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=200)
    domain = models.CharField(max_length=100)  # e.g. 'resource', 'cost', 'demand'
    default = models.BooleanField(default=False)

b) PlanningDimension

Specifies what dimensions are visible, editable, filtered.

class PlanningDimension(models.Model):
    layout = models.ForeignKey(PlanningLayout, related_name="dimensions", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # e.g. "SkillGroup", "System", "ServiceType"
    label = models.CharField(max_length=100)
    is_row = models.BooleanField(default=False)
    is_column = models.BooleanField(default=False)
    is_filter = models.BooleanField(default=True)
    is_editable = models.BooleanField(default=False)
    required = models.BooleanField(default=True)
    data_source = models.CharField(max_length=100)  # optional: e.g. 'SkillGroup.objects.all()'

c) PlanningKeyFigure

Key figures used in the layout: amount, quantity, derived ones.

class PlanningKeyFigure(models.Model):
    layout = models.ForeignKey(PlanningLayout, related_name="key_figures", on_delete=models.CASCADE)
    code = models.CharField(max_length=100)  # e.g. 'amount', 'quantity', 'cost_per_mm'
    label = models.CharField(max_length=100)
    is_editable = models.BooleanField(default=True)
    is_computed = models.BooleanField(default=False)
    formula = models.TextField(blank=True)  # e.g. 'amount = quantity * rate'


⸻

🧩 3. Dynamic Form/Grid Renderer

Use layout config to render:
	•	Django form (via Crispy Forms + autocomplete + bootstrap5) for single record
	•	Table/grid (via Vue component + AG Grid or bootstrap-table) for bulk planning

At runtime:
	•	Layout → rows: PlanningDimension.is_row=True
	•	Layout → columns: key_figure or dynamic period buckets
	•	Filters: dimensions with is_filter=True

⸻

📌 4. Advantages of This Approach

Advantage	Description
✅ Flexible	Admins define and adjust layouts without code change.
✅ Extensible	Easy to add new dimensions/key figures.
✅ Scalable	You can later shard into domain-specific fact tables or materialized views.
✅ Aligned with SAP BW-BPS	Mimics InfoObjects, layouts, planning sequences.
✅ Multidimensional Support	Lead columns, data columns, header filters all supported.
✅ Pluggable Workflow	Each layout can have its own workflow steps and version control.


⸻

⚠️ Limitations and Mitigations

Limitation	Mitigation
EAV-based fact model may slow aggregation	Use materialized summary tables per layout/year/version
JSON filtering can be costly	Extract indexed foreign keys from JSON when needed
Schema evolution risks	Enforce validation rules via layout config and computed field checks
Admin config UI complexity	Provide a wizard-style UI or template presets for layout creation


⸻

🧠 Recommendation

Use this admin-defined layout model + generic fact store for:
	•	MVP, initial rollout, dynamic UX
	•	Cases with flexible dimensions (like Resource, Demand)
	•	Domain-specific UI generation

Then, supplement with dedicated fact tables or summary views for:
	•	Reporting
	•	Data exports
	•	Workflow auditing

⸻

If you’d like, I can generate the full models.py, admin.py, dynamic form renderer, and Vue + Bootstrap5 grid renderer starter. Just let me know.