# EmployeeFlow

**Intelligent Leave and Expense Management System**

EmployeeFlow is a business workflow management application that demonstrates how an organization can manage employee leave requests, expense claims, approval workflows, reimbursements, and policy exceptions through a centralized system.

It combines a Python FastAPI backend, a Streamlit dashboard, and a relational SQLite database.

## Project Overview

Organizations need more than a form to process leave and expense requests. They need to validate policies, check employee eligibility and balances, route requests to the correct approvers, track decisions, and maintain an auditable history.

EmployeeFlow models this process using structured business rules and approval workflows.

### Key Features

- **Employee Management:** Employee records, departments, countries, employment status, and organizational roles.
- **Leave Management:** Leave requests, policy assignments, leave balances, business-day calculations, and holiday-aware processing.
- **Expense Management:** Expense claims, itemized expense lines, categories, receipts metadata, policy limits, and cost centers.
- **Approval Center:** Pending approvals, approval history, multi-step approval workflows, and approval or rejection decisions.
- **Reimbursements:** Reimbursement records created after final expense approval.
- **Exception Management:** Detection of missing information, policy violations, and unusual transactions.
- **Analytics Dashboard:** Workforce distribution, leave and expense summaries, reimbursement information, and exception insights.
- **Audit Trail:** Records workflow events and decisions for traceability.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Main programming language |
| FastAPI | REST API and backend services |
| Streamlit | Interactive business dashboard |
| SQLAlchemy | ORM and database interaction |
| SQLite | Relational database |
| Pydantic | Request and data validation |
| Pandas | Data processing and analytics |
| Faker | Synthetic employee data generation |
| Pytest | Automated testing |
| Uvicorn | ASGI application server |

## Architecture

```text
                 User
                  |
                  v
          Streamlit Frontend
             frontend/app.py
                  |
             HTTP / REST
                  |
                  v
             FastAPI API
              app/main.py
                  |
       +----------+----------+
       |          |          |
       v          v          v
    API Routes  Services   Schemas
       |          |          |
       +----------+----------+
                  |
                  v
             SQLAlchemy ORM
                  |
                  v
             SQLite Database
          data/employeeflow.db
```

The Streamlit frontend communicates with the FastAPI backend. The backend handles business operations, interacts with the database through SQLAlchemy, and returns structured responses to the frontend.

## Project Structure

```text
EmployeeFlow/
|
|-- app/
|   |-- api/
|   |   |-- routes/
|   |       |-- analytics.py
|   |       |-- approvals.py
|   |       |-- dashboard.py
|   |       |-- employees.py
|   |       |-- exceptions.py
|   |       |-- expenses.py
|   |       |-- health.py
|   |       |-- leave.py
|   |
|   |-- db/
|   |   |-- base.py
|   |   |-- session.py
|   |
|   |-- models/
|   |-- schemas/
|   |-- services/
|   |   |-- approval_service.py
|   |   |-- exception_service.py
|   |
|   |-- main.py
|
|-- frontend/
|   |-- app.py
|
|-- scripts/
|   |-- create_tables.py
|   |-- generate_master_data.py
|   |-- generate_leave_transactions.py
|   |-- generate_expense_transactions.py
|   |-- validate_leave_transactions.py
|   |-- validate_expense_transactions.py
|   |-- check_database.py
|
|-- data/
|   |-- ground_truth/
|       |-- leave_request_labels.csv
|       |-- expense_claim_labels.csv
|       |-- expense_line_labels.csv
|       |-- expense_control_test_scenarios.csv
|
|-- requirements.txt
|-- .gitignore
|-- README.md
```

## Database Design

The application uses SQLite with SQLAlchemy ORM.

The database contains 15 tables:

| Area | Tables |
|---|---|
| Employees | employees |
| Leave | leave_policies, leave_balances, leave_requests, employee_leave_policy_assignments |
| Expenses | expense_policies, cost_centers, expense_claims, expense_lines, employee_cost_center_assignments |
| Approvals | approval_rules, approval_steps |
| Reimbursements | reimbursements |
| Audit | audit_events |
| Supporting data | holidays |

SQLite foreign-key enforcement is enabled through the database connection configuration.

The database file is generated locally at:

`data/employeeflow.db`

The database itself is excluded from Git. A fresh database can be created using the setup instructions below.

## Synthetic Dataset

EmployeeFlow includes deterministic synthetic data for demonstrating business workflows.

The generated dataset contains:

- 400 employees across India and the United States.
- 6 leave policies.
- 12 expense policies.
- 16 cost centers.
- 13 company holidays.
- 42 approval rules.
- 800 leave requests.
- 1,000 expense claims.
- Itemized expense lines, approval steps, reimbursements, and audit events.

The dataset is generated using Faker and seeded random generators. It is intended for demonstration and testing, not as real employee or financial information.

### Ground-Truth Data

The `data/ground_truth/` directory contains CSV labels generated alongside the synthetic transactions.

These include:

- Leave request labels.
- Expense claim labels.
- Expense line labels.
- Expense control test scenarios.

Ground-truth labels represent expected outcomes and known characteristics of generated records. They are separate from the operational transaction tables.

## Getting Started

### Prerequisites

- Python 3.11 or later.
- Git.
- PowerShell on Windows, or a compatible terminal.
- A browser.

### 1. Clone the Repository

```bash
git clone https://github.com/Mashood-git/EmployeeFlow.git
cd EmployeeFlow
```

### 2. Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Create Database Tables

Run these commands from the project root, in the specified order.

```bash
python -m scripts.create_tables
```

### 5. Generate Master Data

```bash
python -m scripts.generate_master_data
```

This generates employee records, leave and expense master data, cost centers, holidays, and approval rules.

### 6. Generate Leave Transactions

```bash
python -m scripts.generate_leave_transactions
```

This generates leave requests, approval steps, audit events, and leave ground-truth labels.

### 7. Generate Expense Transactions

```bash
python -m scripts.generate_expense_transactions
```

This generates expense claims, expense lines, approval steps, reimbursement records, audit events, and expense ground-truth CSV files.

**Important:** Run the database generation sequence only against a fresh database. Do not rerun transaction generators against an already populated database. The generators are designed to protect existing data, and some master-data setup operations are intended for initial creation.

### 8. Validate the Database

```bash
python -m scripts.check_database
python -m scripts.validate_leave_transactions
python -m scripts.validate_expense_transactions
```

## Running the Application

Start the backend and frontend in separate terminal windows.

### Terminal 1 — FastAPI Backend

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend:

`http://127.0.0.1:8000`

Interactive API documentation:

`http://127.0.0.1:8000/docs`

### Terminal 2 — Streamlit Frontend

Activate the virtual environment if needed, then run:

```bash
python -m streamlit run frontend/app.py
```

Frontend:

`http://localhost:8501`

## API Overview

The backend exposes versioned REST endpoints under `/api/v1`.

| Module | Endpoint |
|---|---|
| Health | `/api/v1/health` |
| Dashboard | `/api/v1/dashboard/summary` |
| Employees | `/api/v1/employees` |
| Leave | `/api/v1/leave/requests` |
| Leave Balances | `/api/v1/leave/balances/{employee_id}` |
| Expenses | `/api/v1/expenses/claims` |
| Reimbursements | `/api/v1/expenses/reimbursements` |
| Pending Approvals | `/api/v1/approvals/pending` |
| Approval History | `/api/v1/approvals/history` |
| Approval Decisions | `/api/v1/approvals/{approval_step_id}/decision` |
| Exceptions | `/api/v1/exceptions/` |
| Analytics | `/api/v1/analytics/breakdown` |

For complete request and response schemas, start the backend and visit `/docs`.

## Business Workflow

### Leave Workflow

1. An employee submits a leave request.
2. The system evaluates the employee's leave policy and available balance.
3. The request is routed through the applicable approval rules.
4. Approvers approve or reject their assigned steps.
5. The system updates the request and leave balance as appropriate.
6. Workflow events are recorded in the audit history.

### Expense Workflow

1. An employee submits an expense claim with itemized lines.
2. The system evaluates expense policies and relevant claim information.
3. The claim is routed through the applicable approval rules.
4. Approvers review and decide on their assigned steps.
5. After final approval, a reimbursement record is created.
6. Reimbursement status and workflow events can be tracked.

### Exception Workflow

The exception engine evaluates transaction records for selected data-quality and policy-control conditions. Findings are surfaced in the Exception Management dashboard for investigation.

## Security and Demo Limitations

This project is a demonstration of business workflow design, not a production-ready HR or finance platform.

- Approval decisions currently use an actor employee ID supplied by the API request. This is a demonstration mechanism, not secure identity verification.
- Production deployment would require authentication, authorization, secure session handling, and stronger access controls.
- SQLite is used for local demonstration. A production deployment would require an appropriately managed database.
- Receipt handling currently focuses on transaction metadata and control scenarios; it should not be interpreted as a complete secure document-storage system.
- Synthetic records must not be treated as real employee information or actual financial transactions.



## Future Enhancements

- Authentication and role-based access control.
- Production database support using PostgreSQL.
- Secure receipt uploads and document storage.
- More extensive automated workflow and edge-case tests.
- Deployment using Docker and a cloud hosting platform.
- Advanced analytics and configurable policy administration.

## Author

**Mashood Ahmed Shariff**

- GitHub: [Mashood-git](https://github.com/Mashood-git)
- LinkedIn: [Mashood Ahmed Shariff](https://www.linkedin.com/in/mashoodahmedshariff/)

---

EmployeeFlow — Making employee leave and expense workflows more transparent, traceable, and structured.



## Running Tests

The project includes automated API smoke tests using Pytest and FastAPI TestClient.

Run the test suite from the project root:

```bash
python -m pytest tests -v
```

The current tests cover:
- Root API response.
- Successful health check.
- Database connection failure handling.
