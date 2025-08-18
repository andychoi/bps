# 🧠 Business Planning System (BPS)

A Django-based enterprise-grade **Business Planning System** supporting dynamic dimension models, planning cubes, key figures, formulas, reference distribution, version control, approval workflow, and configurable layouts — inspired by **SAP BW-BPS**.

## ✨ Features

- 📐 **Dynamic Planning Layouts**: Define any combination of dimensions (OrgUnit, Service, Account, Period, etc.) with customizable structure
- 📊 **Flexible Fact Storage**: EAV-style `PlanningFact` with proper FK-based extra dimensions via `PlanningFactExtra` and unit-of-measure (UoM) support
- 🧮 **Formula Engine**: Excel-like rules using constants, sub-formulas, and dimension-based expressions
- 🔄 **Distribution Functions**: Copy, distribute, currency convert, and reset operations
- 🔐 **Version & Workflow**:
  - Planning scenarios with multiple steps
  - Session-based planning per OrgUnit
  - Version control with audit trails
- 📦 **Pluggable Dimensions**: Using Django ContentTypes for flexible dimension extensibility
- 🔎 **Interactive UI**:
  - Bootstrap 5 + crispy-forms
  - Tabulator.js for advanced planning grids
  - django-autocomplete-light for fast dimension lookup
  - Real-time cell editing with validation

---

## 🛠️ Technology Stack

- **Backend**: Django 5.2.5, PostgreSQL 13+
- **Frontend**: Bootstrap 5, Tabulator.js, crispy-forms
- **Database**: PostgreSQL with JSONB and GIN indexes
- **API**: Django REST Framework with bulk update capabilities
- **Others**: django-treebeard for hierarchies, django-filter

---

## 🧱 Core Models

| Model | Description |
|-------|-------------|
| `PlanningLayoutYear` | Layout definition per year/version with dimensions and key figures |
| `PlanningFact` | Fact table with first-class dimensions and FK-based extras |
| `PlanningFactExtra` | Extra dimensions with proper FK relationships |
| `DimensionKey` | Registry of valid dimension keys for validation |
| `PlanningSession` | Session per OrgUnit within a scenario |
| `PlanningScenario` | Scenario with multiple workflow steps |
| `DataRequest` | Audit trail for all planning changes |
| `Formula` | Planning formulas with conditional logic and loops |
| `PlanningFunction` | Copy, distribute, convert operations |
| `OrgUnit` | Hierarchical organizational units |
| `Service` | Business services/systems |
| `KeyFigure` | Configurable metrics (FTE, COST, etc.) |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 13+
- Node.js (for frontend assets)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd bps

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup database
cp .env.example .env  # Configure your database settings
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load demo data (optional)
python manage.py bps_demo_0clean
python manage.py bps_demo_1master
python manage.py bps_demo_2env
python manage.py bps_demo_3plan --year 2025

# Run development server
python manage.py runserver
```

### Database Setup

```sql
CREATE DATABASE bps;
CREATE USER bps_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE bps TO bps_user;
```

---

## 📋 Manual Planning Interface

The system provides an advanced manual planning interface with:

- **Interactive Grid**: Tabulator.js-based grid with real-time editing
- **Dynamic Columns**: Configurable periods and key figures
- **Row Operations**: Add, delete, and modify planning rows
- **Header Filters**: Filter data by organizational dimensions
- **Bulk Operations**: Save multiple changes in a single transaction
- **Export**: Excel export functionality

### Key Features
- ✅ Cell-level editing with validation
- ✅ Row deletion with proper database cleanup
- ✅ Dimension-based filtering
- ✅ Automatic session management
- ✅ Audit trail for all changes

---

## 🔧 API Endpoints

### Planning Grid API
- `GET /api/bps/grid/` - Retrieve planning data
- `PATCH /api/bps/grid-update/` - Bulk update planning facts
- `POST /api/bps/grid-update/` - Alternative bulk update method

### Manual Planning API
- `GET /api/bps/manual-grid/` - Manual planning grid data
- `POST /api/bps/manual-grid/` - Manual planning updates

---

## 📁 Project Structure

```
bps/
├── bps/                    # Main Django app
│   ├── api/               # REST API endpoints
│   ├── models/            # Data models (split by domain)
│   ├── views/             # View controllers
│   ├── templates/         # HTML templates
│   ├── management/        # Django commands
│   └── documentation/     # Technical documentation
├── bpsproject/            # Django project settings
├── common/                # Shared utilities and user management
└── requirements.txt       # Python dependencies
```

---

## 🔒 Security & Access Control

- **Role-based Access**: Planning Admin, OrgUnit Head, Analyst roles
- **Session Security**: CSRF protection and secure authentication
- **Audit Logging**: Complete audit trail via DataRequest model
- **Permission Checks**: Layout-year and version-based permissions

---

## 📊 Demo Data

The system includes comprehensive demo data generation:

```bash
# Clean existing data
python manage.py bps_demo_0clean

# Generate master data (dimensions, users, etc.)
python manage.py bps_demo_1master

# Setup planning environment (layouts, scenarios)
python manage.py bps_demo_2env

# Generate planning facts for specific year
python manage.py bps_demo_3plan --year 2025
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.