

⸻

1. FTE Resource Planning Layout

Purpose: Plan headcount (FTE) by position, skill, level across months.
Rows: Position (ID), Skill, Level
Columns: Headcount per month (Jan–Dec), plus annual total
Key Figures: Headcount (HC), Man-Months

Sample Table:

| Position ID | Skill            | Level   | Jan HC | Feb HC | … | Dec HC | Annual Avg |
|-------------|------------------|---------|-------:|-------:|---|-------:|-----------:|
| FTE-DEV-01  | Developer        | Junior  |   1.00 |   1.00 | … |   1.00 |       1.00 |
| FTE-DEV-02  | Developer        | Senior  |   0.80 |   1.00 | … |   1.00 |       0.95 |
| FTE-QA-01   | Test Analyst     | Mid     |   1.00 |   1.00 | … |   1.00 |       1.00 |


⸻

2. Contractor/MSP Resource Planning Layout

Layout Name: CON_MSP_RESOURCE
Purpose: Plan and track man-months & cost of Contractors/MSP by budget code (InternalOrder)
Columns:
	1.	Budget – InternalOrder (cost bucket for resource allocation)
	2.	Resource Type – Contractor or MSP
	3.	Skill – Developer, DevOps, etc.
	4.	Level – Junior / Mid / Senior
	5.	Country – USA, India, Mexico
Key Figures: Monthly KeyFigures – MM (Man-Months), COST (USD)

| Budget (InternalOrder) | ResourceType | Skill            | Level   | Country | Jan MM | Jan Cost | … | Dec MM | Dec Cost |
|------------------------|--------------|------------------|---------|---------|--------|----------|---|--------|----------|
| ORDER_1                | Contractor   | Developer        | Junior  | India   | 2.0    | 8,000    | … | 2.0    | 8,000    |
| ORDER_2                | Contractor   | Test Analyst     | Senior  | USA     | 1.5    | 12,000   | … | 1.5    | 12,000   |
| ORDER_1                | MSP          | DevOps Engineer  | Mid     | Mexico  | 3.0    | 18,000   | … | 3.0    | 18,000   |
| ORDER_3                | MSP          | Security Analyst | Senior  | USA     | 1.0    | 10,000   | … | 1.0    | 10,000   |

⸻

3. Resource Allocation to Systems Layout  (NEW — revised as per your requirement)

Purpose: Allocate each resource position’s capacity across one or more systems; ensure allocation % sums to 100% per resource.
Rows: Position ID (or Resource ID), Role
Columns: Service (System), Allocation %, Man-Months per month
Key Figures: Man-Months, % Utilization

Sample Table:

| Position ID | Resource Role     | Service        | Allocation % | Jan MM | Feb MM | … | Dec MM |
|-------------|-------------------|----------------|-------------:|-------:|-------:|---|-------:|
| FTE-DEV-01  | Developer         | CBU1_CRM       |          50% |    0.5 |    0.5 | … |    0.5 |
| FTE-DEV-01  | Developer         | CBU2_CRM       |          50% |    0.5 |    0.5 | … |    0.5 |
| CON-QA-02   | Test Analyst      | CBU2_WARRANTY  |          70% |    0.7 |    0.7 | … |    0.7 |
| CON-QA-02   | Test Analyst      | CBU3_INVENTORY |          30% |    0.3 |    0.3 | … |    0.3 |


⸻

4. System Demand by Skill & Level Layout (NEW)

Purpose: Aggregate demand for each system by skill and level (from allocation or direct estimation).
Rows: Service (System), Skill, Level
Columns: Man-Months per month
Key Figures: Man-Months

Sample Table:

| Service        | Skill            | Level   | Jan MM | Feb MM | … | Dec MM |
|----------------|------------------|---------|-------:|-------:|---|-------:|
| CBU1_CRM       | Developer        | Senior  |    2.0 |    2.0 | … |    2.0 |
| CBU1_CRM       | DevOps Engineer  | Mid     |    1.0 |    1.0 | … |    1.0 |
| CBU2_WARRANTY  | Test Analyst     | Junior  |    0.8 |    0.8 | … |    0.8 |
| CBU3_INVENTORY | Security Analyst | Senior  |    0.3 |    0.3 | … |    0.3 |


⸻
5. Software License Cost Planning Layout

Purpose:
Plan software license drivers & costs per system (service), linked to a budget bucket (InternalOrder).

Rows:
	•	Service (System)
	•	Internal Order (Budget for Software Product)

Columns:
	•	Driver Volume per month (e.g., Users, Systems, Consumption Qty)
	•	Unit Price (USD)
	•	Annual Cost (calculated)

Key Figures:
	•	LICENSE_VOLUME (EA)
	•	LICENSE_UNIT_PRICE (USD)
	•	LICENSE_COST (USD)

Sample Table

| Service        | Internal Order  | Jan Users | Feb Users | … | Dec Users | Unit Price (USD) | Annual Cost |
|----------------|-----------------|----------:|----------:|---|----------:|-----------------:|------------:|
| CBU1_CRM       | IO_CRM_LIC      |       100 |       105 | … |       110 |             50.0 |       63,000 |
| CBU2_WARRANTY  | IO_WAR_LIC      |        50 |        52 | … |        54 |             75.0 |       45,000 |
| CBU3_BILLING   | IO_BIL_LIC      |       200 |       205 | … |       210 |            120.0 |      288,000 |

Notes:
	•	Driver Volume grows month-by-month (e.g., growth factor applied).
	•	Unit Price inflated by the INFLATION_RATE constant.
	•	Annual Cost = SUM(Jan..Dec Users × Unit Price)

⸻

6. Admin & Overhead Allocation Layout

Purpose: Allocate corporate/admin overhead to departments and services.
Rows: Dept / Service
Columns: Overhead cost per month
Key Figures: Admin Overhead (USD)

Sample Table:

| Org Unit      | Service        | Jan Overhead (USD) | Feb Overhead (USD) | … | Dec Overhead (USD) |
|---------------|----------------|-------------------:|-------------------:|---|-------------------:|
| Dept 1.1      | CBU1_CRM       |              2,500 |              2,500 | … |              2,500 |
| Dept 1.2      | CBU2_WARRANTY  |              1,800 |              1,800 | … |              1,800 |


⸻

7. Total Service Cost Layout (Result)

Purpose: Summarize total cost per service combining labor, licenses, overhead.
Rows: Service (System)
Columns: Cost components per month (Labor, License, Overhead), Total Cost
Key Figures: Labor Cost, License Cost, Overhead, Total

Sample Table:

| Service        | Jan Labor | Jan License | Jan Overhead | Jan Total | … | Annual Total |
|----------------|----------:|------------:|-------------:|----------:|---|-------------:|
| CBU1_CRM       |    50,000 |      5,000  |        2,500 |    57,500 | … |       690,000 |
| CBU2_WARRANTY  |    30,000 |      3,000  |        1,800 |    34,800 | … |       420,000 |


