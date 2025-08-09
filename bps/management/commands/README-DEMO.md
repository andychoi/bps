# Input Context for Demo Data Generation

## How to run
```
python manage.py bps_demo_0clean
python manage.py bps_demo_1master
python manage.py bps_demo_2env
# Optional: limit to a year, e.g. 2025 or 2026
python manage.py bps_demo_3plan --year 2025
python manage.py bps_demo_3plan --year 2026
```

## 1. Master & Reference Data

1. **Skills & Seniorities**
   - **SKILLS**: Developer, DevOps Engineer, Test Analyst, Security Analyst, etc. (App DevSecOps org)
   - **SENIORITIES**: Junior / Mid / Senior

2. **Units of Measure & Conversions**
   - **UOMs**:
     - HRS (base)
     - USD
     - EA (each)
     - MAN-MONTH (alias: 160 HRS)
   - **ConversionRates**:
     - 12 MAN-MONTH → 1 headcount
     - 168 HRS → 1 MAN-MONTH

3. **Key Figures**
   - FTE (float)
   - MAN-MONTH (decimal)
   - COST (decimal, USD)
   - LICENSE_COST (decimal, USD)
   - ADMIN_OVERHEAD (decimal, USD)

4. **Global Constants / Sub-Formulas**
   - INFLATION_RATE = 3%
   - GROWTH_FACTOR = 5%
   - _Optional_: TAX_RATE, BENEFITS_RATE, etc.

---

## 2. Time & Version Dimensions

1. **Years**: FY 2025, FY 2026  
2. **Versions**:
   - ACTUAL (historical) → for 2025 actuals  
   - DRAFT, PLAN V1 (“Realistic”), PLAN V2 (“Optimistic”) → for planning 2026  
3. **Periods**: 12 months (codes “01”–“12”, names “Jan”–“Dec”)  
4. **PeriodGroupings**:
   - Monthly buckets (1 month)
   - Quarterly buckets (3 months)

---

## 3. Organizational Structure

1. **OrgUnit tree**  
   - ROOT “Head Office”  
     - Division 1  
       - Dept 1.1, Dept 1.2, Dept 1.3  
     - Division 2  
       - Dept 2.1, Dept 2.2, Dept 2.3  
     - Division 3  
       - Dept 3.1, Dept 3.2, Dept 3.3  

2. **CBUs**  
   - CBU1–CBU3 (“Demo” group, is_active)

3. **CostCenters & InternalOrders**  
   - One CostCenter per Division/Department  
   - InternalOrder links to its CostCenter via code

---

## 4. Service (System) Inventory

1. **For each CBU**: register 5 distinct business systems (e.g. CRM, Warranty, Dealer Service…)  
2. **Service attributes**:
   - SLA targets (response, resolution)
   - Availability (%)
   - Support hours (e.g. “9×5”)
   - Category/Subcategory (Ops, Enhancements, Innovation)
   - is_shared flag for common services (e.g. platform, identity management)

3. **Multi-CBU sharing**: some systems may span multiple CBUs  
4. **Resource allocation metadata**: each service will track allocated “man hours” per resource role

---

## 5. Labor Headcount / Man-Month & Allocation

1. **Resource types**:
   - FTE (Employee)
   - CON (Contractor)
   - MSP (Managed Service Provider)

2. **Positions (FTE)**:
   - For each Year × Skill × Seniority × Open/Closed flag (10% open / 90% filled)

3. **Contractor / MSP**:
   - Can attach multiple budget codes (CostCenter / InternalOrder)

4. **Fill logic**:
   - 2025 ACTUAL: fill 90% of positions, random start ±5% availability
   - 2026 PLAN: hire up to additional 5% spread randomly across months

5. **RateCards**:
   - HourlyRate & EfficiencyFactor per Year × ResourceType × Skill × Seniority
   - If CON / MSP: by Country (USA: 1.0, India: 0.7, Mexico: 0.9)

6. **Allocation roll-up**:
   - Resource → Position → OrgUnit/Department → Service
   - Shared positions (manager, architect) split capacity across multiple services

---

## 6. Software Licenses

1. Link 1–2 software products per Service  
2. **Drivers**:
   - UserCount, SystemCount, ConsumptionQty  
3. **2025 ACTUAL**: randomly generate driver volumes & total license cost  
4. **2026 PLAN**:
   - driver_volume = ACTUAL × (1 + GROWTH_FACTOR)
   - unit_price = ACTUAL price × (1 + INFLATION_RATE)
   - license_cost = driver_volume × unit_price

---

## 7. Admin & Overhead Costs

1. **Admin OrgUnit**: single “Corporate Admin” node  
2. **Admin KeyFigure**: ADMIN_OVERHEAD for ACTUAL & PLAN  
3. **Allocation steps**:
   1. Dept-level overhead = total Dept labor cost × Dept’s share of total labor cost  
   2. Service-level overhead = Dept overhead × (service’s man-months ÷ Dept total man-months)

---

## 8. Fact Generation (Sessions & DataRequests)

1. **Sessions**: one per OrgUnit × LayoutYear  
   - Captures all PlanningFact entries for that slice

2. **DataRequests**:
   - 2025 ACTUAL: single request “Historical 2025”
   - 2026 PLANS: one per submission round (“Draft Plan”, “V1 Update”, “V2 Update”)

3. **Historical Facts** (version=ACTUAL, Year=2025):
   - For each Service × Period:
     - Headcount & Man-Months (per ResourceType)
     - Labor Cost (actual rate)
     - License Cost
     - Service Cost = labor + license + allocated overhead

4. **Planning Facts** (for DRAFT, PLAN V1, PLAN V2 in 2026):
   - Resource plan (FTE, CON, MSP)
   - Service inventory changes (new/decommissioned)
   - Resource → Service allocation (man-months)
   - License plan (volumes & cost)
   - Overhead allocation per above
   - Show 2025 ACTUAL values alongside for variance comparison

---

## 9. Calculations & Formulas

1. **Inflation Formula**  
   ```text
   FOREACH OrgUnit,Period:
     COST_PLANNED_Inflated = COST_BASE × (1 + INFLATION_RATE)
   ```

2. **Business Growth Formula**  
   ```text
   FOREACH Service,Period:
     FTE_Planned = FTE_Actual × (1 + GROWTH_FACTOR)
   ```

3. **Copy Cost Baseline**  
   - PlanningFunction “Copy Cost Baseline” (COPY) from PLAN V1 → PLAN V2 for 2026

4. **Overhead Allocation**  
   ```text
   AdminDeptCost    = TotalLaborCost_Dept × DeptShare
   Overhead_Service = AdminDeptCost × (ManMonths_Service ÷ ManMonths_Dept)
   ```

5. **Execution & Auditing**  
   - All formulas run via `FormulaExecutor` → `FormulaRun` / `FormulaRunEntry` logs
``