Here is a more comprehensive Technical System Design Document, clearly detailing the technical design, model relationships, and expected usage based on the provided Django-based system:

⸻

Technical System Design Document

Business Planning System (BPS)

Document Overview

This document outlines the detailed technical structure and design of the Business Planning System (BPS), specifically targeting IT service companies. It includes comprehensive details of the models, their relationships, and expected usage patterns.

⸻

1. Technical Overview

The system is developed using Django 5.2, leveraging Django’s ORM, crispy-forms, Bootstrap 5, Django-Autocomplete-Light (DAL), and Vue.js for frontend interactivity.

Tech Stack
	•	Backend Framework: Django 5.2 (Python)
	•	Frontend: Crispy Forms, Bootstrap 5, Vue.js
	•	Database: PostgreSQL (using JSONB fields for dynamic attributes)
	•	Authentication & Authorization: Django’s built-in auth with custom UserMaster model
	•	Dynamic Form Handling: DAL, Crispy, Vue.js components

⸻

2. Detailed Data Models & Relationships

2.1 Abstract Base Model: InfoObject

InfoObject (abstract)
│─ code (str, unique)
│─ name (str)
│─ description (str)
│─ order (int)
│
├── Year
├── Version
├── OrgUnit
│     ├── head_user (FK:User)
│     ├── parent (self FK)
│     ├── cost_center (str)
│     └── internal_order (str)
├── CostCenter
├── InternalOrder
├── CBU
└── PriceType

Expected Usage:
These abstracted dimensions form a flexible and standardized foundation for referencing throughout planning entities.

⸻

2.2 Planning Layout Models

PlanningLayout
│─ name
│─ description
│─ key_figures (JSON array)
│
└─ PlanningLayoutYear
    │─ layout (FK:PlanningLayout)
    │─ year (FK:Year)
    │─ version (FK:Version)
    │─ org_units (M2M:OrgUnit)
    │─ row_dims (M2M:ContentType)
    └─ header_dims (JSON dict)

Expected Usage:
	•	PlanningLayout defines the general planning structure (e.g., Revenue, Expense layouts).
	•	PlanningLayoutYear allows per-year and per-version customization of dimensions.

⸻

2.3 Period Management

Period
│─ code ('01'-'12')
│─ name ('Jan'-'Dec')
│─ order (1-12)
│
└─ PeriodGrouping
    │─ layout_year (FK:PlanningLayoutYear)
    │─ months_per_bucket (1,3,6)
    └─ label_prefix ('Q','H')

Expected Usage:
Flexible definition of planning granularity (monthly, quarterly, semiannual) per layout/year.

⸻

2.4 Planning Workflow & Session

PlanningSession
│─ layout_year (FK:PlanningLayoutYear)
│─ org_unit (FK:OrgUnit)
│─ created_by (FK:User)
│─ created_at (datetime)
│─ status (DRAFT→COMPLETED→FROZEN)
│─ frozen_by (FK:User, admin)
│─ frozen_at (datetime)
│
└─ DataRequest (transaction journaling)
    │─ session (FK:PlanningSession)
    │─ description (text)
    │─ created_by (FK:User)
    │─ created_at (datetime)
    │
    └─ PlanningFact (Fact Data EAV)
        │─ request (FK:DataRequest)
        │─ period (str)
        │─ row_values (JSON dict)
        │─ key_figure (str)
        └─ value (decimal)

Expected Usage:
	•	Defines structured planning stages per org unit.
	•	Tracks changes and audits through journaling (DataRequest).

⸻

2.5 Custom User Management

UserMaster
│─ user (FK:User)
│─ org_unit (FK:OrgUnit)
└─ cost_center (FK:CostCenter)

Expected Usage:
Enables hierarchical access control and org-based workflows.

⸻

2.6 Dynamic Form & FactField Configuration

FactField
│─ layout (FK:PlanningLayout)
│─ name (str)
│─ label (str)
│─ field_type ('char', 'int', 'dec', 'fk')
│─ required (bool)
│─ order (int)
└─ content_type (FK:ContentType, for FK type)

Expected Usage:
Form field configuration without altering codebase.

⸻

2.7 Formula & Calculation Support

Formula, SubFormula, Constant (for advanced calculations)
│─ formula expressions dynamically evaluated
│─ uses global variables and sub-formulas
│─ executed via formula_executor.py

Expected Usage:
Complex financial/operational formulas executed dynamically per planning scenario.

⸻

3. Technical Design Considerations

3.1 Dynamic Dimensions via JSON/EAV Pattern
	•	Advantages:
	•	Extreme flexibility in dimension definitions.
	•	Minimal schema alterations over time.
	•	Limitations:
	•	Performance trade-offs at high scale, due to complex joins and JSON processing.
	•	Mitigation:
	•	Periodic ETL to flattened dimensional data marts for high-performance reporting.

3.2 Hierarchical Org Units and User Assignments
	•	Advantages:
	•	Hierarchical modeling of organizational structures.
	•	Supports complex approval workflows and roll-ups.
	•	Limitations:
	•	Performance considerations in deep hierarchies.
	•	Mitigation:
	•	Use django-mptt or similar libraries for optimized hierarchical queries.

3.3 Flexible Period Grouping (Monthly, Quarterly, Semiannual)
	•	Advantages:
	•	Allows granular and aggregated views dynamically.
	•	Limitation:
	•	Does not inherently support custom fiscal calendars.
	•	Mitigation:
	•	Extend Period/Grouping models for custom fiscal periods if required.

⸻

4. Expected Usage Patterns (Workflows)

4.1 Planning Cycle Workflow
	•	Planning Admin defines layouts, dimensions annually.
	•	OrgUnit Heads create draft plans.
	•	OrgUnits submit plans for approval.
	•	Admin freezes the finalized plans (prevents changes).

4.2 Scenario and Version Management
	•	Support multiple concurrent scenarios via global Versions (e.g., Best, Base, Worst case).
	•	Flexible reporting and comparative analysis across scenarios.

4.3 Calculation and Data Processing
	•	Data entered via dynamic forms, computed fields via formulas.
	•	Use Celery background tasks for computationally intensive operations.

⸻

5. Limitations & Technical Improvements

Identified Limitations
	•	Performance Impact of JSON/EAV
	•	Complexity of Dynamic Forms (frontend handling)
	•	Simple Workflow State Management
	•	Limited built-in BI/Reporting

Recommendations to Improve Technical Design
	•	Introduce Dedicated Analytical Data Mart:
Star schema and nightly ETL jobs for reporting performance.
	•	Advanced Workflow Management:
Integration with workflow engines (django-river or django-fsm) for complex approval chains.
	•	Advanced Frontend Enhancements:
Vue.js or React-based grid libraries for optimized UX.
	•	BI and Analytics Integration:
Consider integration with Superset, PowerBI Embedded, or Metabase.
	•	Asynchronous Background Processing:
Employ Celery for all heavy computational tasks (formula execution, data distribution).

⸻

6. Technical Security & Compliance
	•	Role-Based Access Control (RBAC): Django’s auth permissions combined with custom user profiles.
	•	Audit Logging: Integration with django-auditlog or similar to maintain traceability.
	•	Data Integrity Checks: Regular validation scripts and data reconciliation tasks.

⸻

7. Deployment and Operational Considerations
	•	Containerization (Docker/Kubernetes): for scalable, replicable deployments.
	•	Automated CI/CD: pipelines for efficient updates and deployments.
	•	Monitoring & Logging: integration with Prometheus/Grafana, ELK stack, or similar.

⸻

8. Implementation Roadmap

Phase	Milestone	Duration
1	Data Model & Basic Workflows	4–6 weeks
2	Dynamic Form Configuration	3–4 weeks
3	Advanced Calculation & Sequences	3–4 weeks
4	Frontend Enhancement & UX	3–5 weeks
5	Reporting & Analytics Integration	4–6 weeks
6	Performance Optimization & Production Prep	4 weeks


⸻

Conclusion

The presented detailed technical design aligns with industry-standard best practices, ensuring flexibility, maintainability, and scalability for evolving IT company planning needs. While leveraging dynamic patterns, recommended enhancements (data marts, workflows, reporting integration) significantly enhance robustness, performance, and user experience.

⸻

End of Technical Design Document