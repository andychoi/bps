# 🧠 Business Planning System (BPS)

A Django-based enterprise-grade **Business Planning System** supporting dynamic dimension models, planning cubes, key figures (amount, quantity), formulas, reference distribution, version control, approval workflow, and configurable layouts — inspired by **SAP BW-BPS**.

## ✨ Features

- 📐 **Dynamic Planning Layouts**: Define any combination of dimensions (OrgUnit, Account, Product, Period, etc.) with customizable structure.
- 📊 **Flexible Fact Storage**: EAV-style `PlanningFact` supports amount, quantity, and custom key figures with unit-of-measure (UoM).
- 🧮 **Formula Engine**: Excel-like rules using constants, sub-formulas, and dimension-based expressions.
- 🔄 **Distribution Functions**: Support for even/key/reference-based distribution of planning data.
- 🔐 **Version & Workflow**:
  - Planning versions (draft, frozen)
  - Approval steps per OrgUnit
  - Locking / copying between versions
- 📦 **Pluggable Dimensions**: Using Django ContentTypes for flexible dimension extensibility.
- 🔎 **UI**:
  - Bootstrap 5 + crispy-forms
  - Vue.js components for planning grids
  - django-autocomplete-light for fast dimension lookup

---

## 🛠️ Technology Stack

- **Backend**: Django 4.x+, PostgreSQL 13+
- **Frontend**: Bootstrap 5, Vue 3 (optional), crispy-forms
- **Database**: PostgreSQL with JSONB and GIN index
- **Others**: Celery (for background processing), Redis (optional)

---

## 🧱 Data Model Highlights

| Model             | Description |
|------------------|-------------|
| `PlanningLayout` | Layout definition with dimensions, column axis, and key figures |
| `PlanningFact`   | Fact table storing values for dynamic dimension combinations |
| `Formula`        | Planning formula with loop dimensions and expressions |
| `FormulaRun`     | Audit log of formula executions |
| `PlanningSession`| Grouping of planning cycles, tied to versions |
| `OrgUnit`        | Supports parent-child hierarchy, head user, cost center |
| `ConversionRate` | Exchange or quantity conversion rates |
| `HierarchyNode`  | Common hierarchy tree for any dimension |

---

## 🐘 PostgreSQL Setup

> Ensure your PostgreSQL installation supports `jsonb` and `gin` indexes (default in 12+).

```sql
CREATE DATABASE bps;
CREATE USER bps_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE bps TO bps_user;