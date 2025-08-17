# System Service Cost Planning - Management Commands

## Overview

This document outlines the management commands for generating comprehensive demo data for **System Service Cost Planning** in IT organizations. The planning model supports multi-dimensional cost allocation across resources, services, and organizational units with benchmarking capabilities.

## Planning Model Design

### Core Planning Layouts

#### 1. Resource Capacity Planning Layout
**Purpose**: Plan FTE, contractor, and MSP capacity by skill and seniority level.

**Dimensions**:
- **Rows**: Resource Type, Skill, Seniority Level, Country
- **Columns**: Monthly periods (Jan-Dec)
- **Key Figures**: FTE_COUNT, MAN_MONTHS, HOURLY_RATE, TOTAL_COST

**Sample Structure**:
```
| Resource Type | Skill           | Level  | Country | Jan FTE | Jan MM | Hourly Rate | Jan Cost |
|---------------|-----------------|--------|---------|--------:|-------:|------------:|---------:|
| FTE           | Developer       | Senior | USA     |     2.0 |    2.0 |      $85.00 | $27,200  |
| CON           | DevOps Engineer | Mid    | India   |     3.0 |    3.0 |      $45.00 | $21,600  |
| MSP           | Security Analyst| Senior | Mexico  |     1.0 |    1.0 |      $65.00 | $10,400  |
```

#### 2. Service Resource Allocation Layout
**Purpose**: Allocate resource capacity across business systems with utilization tracking.

**Dimensions**:
- **Rows**: Resource ID, Service Code
- **Columns**: Monthly allocation percentages and man-months
- **Key Figures**: ALLOCATION_PCT, ALLOCATED_MM, UTILIZATION_RATE

**Sample Structure**:
```
| Resource ID | Service Code | Allocation % | Jan MM | Utilization | Efficiency |
|-------------|--------------|-------------:|-------:|------------:|-----------:|
| FTE-DEV-01  | CRM_SYSTEM   |          60% |    0.6 |        95% |       1.2x |
| FTE-DEV-01  | ERP_SYSTEM   |          40% |    0.4 |        95% |       1.2x |
| CON-QA-02   | CRM_SYSTEM   |         100% |    1.0 |        85% |       1.0x |
```

#### 3. Service Demand Planning Layout
**Purpose**: Aggregate skill demand by service with capacity gap analysis.

**Dimensions**:
- **Rows**: Service Code, Skill, Seniority Level
- **Columns**: Monthly demand and supply metrics
- **Key Figures**: DEMAND_MM, SUPPLY_MM, GAP_MM, COST_PER_MM

**Sample Structure**:
```
| Service Code | Skill       | Level  | Jan Demand | Jan Supply | Gap MM | Cost/MM |
|--------------|-------------|--------|-----------:|-----------:|-------:|--------:|
| CRM_SYSTEM   | Developer   | Senior |        3.5 |        3.0 |   -0.5 | $13,600 |
| ERP_SYSTEM   | DevOps      | Mid    |        2.0 |        2.5 |    0.5 |  $7,200 |
```

#### 4. Software License Cost Planning Layout
**Purpose**: Plan software licensing costs with usage-based drivers and benchmarking.

**Dimensions**:
- **Rows**: Service Code, Software Product, License Type
- **Columns**: Monthly usage metrics and costs
- **Key Figures**: USER_COUNT, UNIT_PRICE, LICENSE_COST, BENCHMARK_PRICE

**Sample Structure**:
```
| Service Code | Software Product | License Type | Jan Users | Unit Price | Jan Cost | Benchmark |
|--------------|------------------|--------------|----------:|-----------:|---------:|----------:|
| CRM_SYSTEM   | Salesforce       | Professional |       150 |     $75.00 | $11,250  |    $70.00 |
| ERP_SYSTEM   | SAP S/4HANA      | Named User   |        80 |    $180.00 | $14,400  |   $175.00 |
```

#### 5. Infrastructure Cost Planning Layout
**Purpose**: Plan infrastructure costs including cloud, hardware, and network expenses.

**Dimensions**:
- **Rows**: Service Code, Infrastructure Component, Provider
- **Columns**: Monthly usage and cost metrics
- **Key Figures**: COMPUTE_HOURS, STORAGE_GB, NETWORK_GB, INFRA_COST

**Sample Structure**:
```
| Service Code | Component Type | Provider | Jan Compute | Storage GB | Network GB | Jan Cost |
|--------------|----------------|----------|------------:|-----------:|-----------:|---------:|
| CRM_SYSTEM   | Compute        | AWS      |       2,400 |      1,000 |        500 |   $3,200 |
| ERP_SYSTEM   | Database       | Azure    |       1,800 |      5,000 |        800 |   $4,500 |
```

#### 6. Service Total Cost Layout (Consolidated)
**Purpose**: Aggregate all cost components per service with variance analysis.

**Dimensions**:
- **Rows**: Service Code, Cost Category
- **Columns**: Monthly costs and variance metrics
- **Key Figures**: LABOR_COST, LICENSE_COST, INFRA_COST, TOTAL_COST, BUDGET_VAR

**Sample Structure**:
```
| Service Code | Jan Labor | Jan License | Jan Infra | Jan Total | Budget Var | Benchmark |
|--------------|----------:|------------:|----------:|----------:|-----------:|----------:|
| CRM_SYSTEM   |   $85,000 |    $11,250 |    $3,200 |   $99,450 |      +5.2% |   $94,500 |
| ERP_SYSTEM   |   $65,000 |    $14,400 |    $4,500 |   $83,900 |      -2.1% |   $85,800 |
```

## Benchmarking & Best Practices

### Industry Benchmarks Integration
- **Labor Rates**: Market rate comparison by skill/location
- **License Costs**: Vendor benchmark pricing
- **Infrastructure**: Cloud cost optimization metrics
- **Productivity**: Industry standard efficiency ratios

### Cost Optimization Features
- **Capacity Utilization**: Target 85-95% utilization rates
- **Skill Mix Optimization**: Balance senior/junior ratios
- **Geographic Arbitrage**: Offshore/nearshore cost benefits
- **License Optimization**: Usage-based vs. fixed licensing

### Performance Metrics
- **Cost per Service**: Total cost of ownership tracking
- **Resource Efficiency**: Output per man-month metrics
- **Budget Variance**: Plan vs. actual analysis
- **Trend Analysis**: YoY cost growth patterns

## Management Commands

### Command Execution Sequence
```bash
# 1. Clean existing data
python manage.py bps_demo_0clean

# 2. Generate master data with benchmarks
python manage.py bps_demo_1master --with-benchmarks

# 3. Setup planning environment
python manage.py bps_demo_2env --service-focus

# 4. Generate planning facts with scenarios
python manage.py bps_demo_3plan --year 2025 --scenario baseline
python manage.py bps_demo_3plan --year 2026 --scenario optimistic
python manage.py bps_demo_3plan --year 2026 --scenario conservative

# 5. Generate benchmark data
python manage.py bps_demo_4benchmark --industry-data
```

## Master Data Generation

### 1. Skills & Competencies
```python
SKILLS = [
    'Application Developer', 'DevOps Engineer', 'Test Analyst', 
    'Security Analyst', 'Data Engineer', 'Cloud Architect',
    'Product Manager', 'Scrum Master', 'Business Analyst'
]

SENIORITY_LEVELS = ['Junior', 'Mid', 'Senior', 'Lead', 'Principal']

COUNTRIES = [
    {'code': 'USA', 'cost_factor': 1.0, 'currency': 'USD'},
    {'code': 'IND', 'cost_factor': 0.3, 'currency': 'USD'},
    {'code': 'MEX', 'cost_factor': 0.6, 'currency': 'USD'},
    {'code': 'POL', 'cost_factor': 0.4, 'currency': 'USD'}
]
```

### 2. Service Portfolio
```python
SERVICES = [
    {'code': 'CRM_SYS', 'name': 'Customer Relationship Management', 'category': 'Business'},
    {'code': 'ERP_SYS', 'name': 'Enterprise Resource Planning', 'category': 'Business'},
    {'code': 'HCM_SYS', 'name': 'Human Capital Management', 'category': 'Business'},
    {'code': 'BI_SYS', 'name': 'Business Intelligence Platform', 'category': 'Analytics'},
    {'code': 'SEC_SYS', 'name': 'Security Operations Center', 'category': 'Security'},
    {'code': 'INFRA_SYS', 'name': 'Infrastructure Services', 'category': 'Infrastructure'}
]
```

### 3. Key Figures & Metrics
```python
KEY_FIGURES = [
    {'code': 'FTE_COUNT', 'name': 'Full-Time Equivalent Count', 'uom': 'EA', 'decimals': 1},
    {'code': 'MAN_MONTHS', 'name': 'Man-Months', 'uom': 'MM', 'decimals': 2},
    {'code': 'HOURLY_RATE', 'name': 'Hourly Rate', 'uom': 'USD', 'decimals': 2},
    {'code': 'LABOR_COST', 'name': 'Labor Cost', 'uom': 'USD', 'decimals': 0},
    {'code': 'LICENSE_COST', 'name': 'License Cost', 'uom': 'USD', 'decimals': 0},
    {'code': 'INFRA_COST', 'name': 'Infrastructure Cost', 'uom': 'USD', 'decimals': 0},
    {'code': 'TOTAL_COST', 'name': 'Total Service Cost', 'uom': 'USD', 'decimals': 0},
    {'code': 'UTILIZATION_RATE', 'name': 'Utilization Rate', 'uom': 'PCT', 'decimals': 1},
    {'code': 'EFFICIENCY_FACTOR', 'name': 'Efficiency Factor', 'uom': 'RATIO', 'decimals': 2}
]
```

### 4. Benchmark Data Sources
```python
BENCHMARK_SOURCES = [
    {'name': 'Gartner IT Metrics', 'category': 'Labor', 'reliability': 'High'},
    {'name': 'IDC Software Pricing', 'category': 'License', 'reliability': 'High'},
    {'name': 'AWS Cost Calculator', 'category': 'Infrastructure', 'reliability': 'Medium'},
    {'name': 'Industry Survey 2024', 'category': 'Productivity', 'reliability': 'Medium'}
]
```

## Planning Scenarios

### Baseline Scenario (2025 Actual)
- Historical data with 90% resource utilization
- Market-rate labor costs
- Actual license and infrastructure spending
- Productivity metrics based on delivered projects

### Optimistic Scenario (2026 Plan)
- 15% productivity improvement through automation
- 10% cost reduction via geographic optimization
- 95% resource utilization target
- Strategic vendor negotiations (-5% license costs)

### Conservative Scenario (2026 Plan)
- 5% inflation on all cost categories
- 85% resource utilization (market uncertainty)
- 20% contingency buffer for critical services
- Vendor price increases (+3% license costs)

## Formula Examples

### Resource Cost Calculation
```python
# Monthly labor cost per resource
MONTHLY_COST = FTE_COUNT * HOURLY_RATE * HOURS_PER_MONTH * EFFICIENCY_FACTOR

# Service allocation cost
SERVICE_COST = MONTHLY_COST * ALLOCATION_PERCENTAGE * UTILIZATION_RATE
```

### Benchmark Variance Analysis
```python
# Cost variance from benchmark
COST_VARIANCE = (ACTUAL_COST - BENCHMARK_COST) / BENCHMARK_COST * 100

# Efficiency benchmark
EFFICIENCY_SCORE = ACTUAL_OUTPUT / (BENCHMARK_OUTPUT * RESOURCE_COUNT)
```

### Capacity Planning
```python
# Resource gap analysis
RESOURCE_GAP = DEMAND_MM - SUPPLY_MM

# Utilization optimization
OPTIMAL_FTE = DEMAND_MM / (TARGET_UTILIZATION * MONTHS_PER_YEAR)
```

## Data Quality & Validation

### Validation Rules
- Resource allocation percentages sum to 100% per resource
- Service demand matches allocated capacity within 5% tolerance
- Cost calculations reconcile across all dimensions
- Benchmark data freshness (updated quarterly)

### Data Lineage
- Source system tracking for all imported data
- Calculation audit trail for derived metrics
- Version control for planning assumptions
- Change log for benchmark updates

## Reporting & Analytics

### Standard Reports
- **Service Cost Dashboard**: Real-time cost tracking
- **Resource Utilization Report**: Capacity optimization insights
- **Benchmark Analysis**: Market position assessment
- **Variance Analysis**: Plan vs. actual performance
- **Trend Analysis**: Multi-year cost evolution

### KPI Metrics
- Cost per service per month
- Resource utilization percentage
- Benchmark variance (±%)
- Budget accuracy (forecast vs. actual)
- Productivity trends (output per FTE)

This planning model provides comprehensive cost management for IT service organizations with industry benchmarking and optimization capabilities.