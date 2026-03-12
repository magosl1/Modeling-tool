# Financial Modeling Tool — MVP

A full-stack web-based financial modeling platform. Users upload historical financial statements, configure projection assumptions module by module through a tree-based UI, and generate projected P&L, Balance Sheet, Cash Flow, and DCF valuation.

## Architecture

```
financial_modeler/
├── backend/           # Python + FastAPI
│   ├── app/
│   │   ├── api/routes/      # Auth, Projects, Historical, Assumptions, Projections, Valuation
│   │   ├── core/            # Config, Security (JWT)
│   │   ├── db/              # SQLAlchemy engine, session, init
│   │   ├── models/          # User, Project, HistoricalData, Assumptions, Projections, Valuation
│   │   ├── schemas/         # Pydantic schemas
│   │   └── services/
│   │       ├── template_generator.py    # Excel template generation (openpyxl)
│   │       ├── historical_validator.py  # 8-rule validation engine
│   │       ├── projection_engine.py     # 21-step projection compilation
│   │       └── dcf_engine.py           # DCF + sensitivity analysis
│   └── requirements.txt
├── frontend/          # React + TypeScript + Tailwind CSS
│   └── src/
│       ├── components/
│       │   ├── auth/         # Login, Register
│       │   ├── dashboard/    # Project list
│       │   ├── project/      # Workspace, Upload Historical, Setup
│       │   ├── modules/      # Assumptions Panel, Module Configurator
│       │   ├── projections/  # P&L / BS / CF views + export
│       │   └── valuation/    # DCF inputs, outputs, sensitivity table
│       ├── services/api.ts   # Axios API client
│       └── store/            # Zustand auth store
└── docker-compose.yml
```

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL, openpyxl, pandas
- **Auth:** JWT (access + refresh tokens), bcrypt
- **Task Queue:** Celery + Redis (async projection runs >10 years)
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, React Query, Zustand
- **Storage:** AWS S3 (file uploads)

## Quick Start

### 1. With Docker Compose (recommended)

```bash
cd financial_modeler
cp backend/.env.example backend/.env
# Edit backend/.env with your settings

docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 2. Local Development

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit with your DB/Redis settings
python -m app.db.init_db     # create tables
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Core User Flow

1. **Create Project** — name, currency, scale, fiscal year end, projection years
2. **Download Historical Template** — pre-structured 3-tab Excel (P&L, BS, CF)
3. **Upload Historical Data** — 8-rule validation engine rejects invalid files with inline error messages
4. **Configure Assumptions** — module by module via tree-based UI:
   - Module 1: Revenue (streams, price×qty, growth rates)
   - Module 2: COGS / Gross Margin
   - Module 3: Operating Expenses
   - Module 4: D&A (PP&E + Intangibles roll-forward)
   - Module 5: Working Capital (DIO/DSO/DPO methods)
   - Module 6: Capex
   - Module 7: Debt & Financing
   - Module 8: Tax (with optional NOL carry-forward)
   - Module 9: Dividends
   - Module 10: Interest Income
   - Module 11: Non-Operating & Other Items
5. **Run Projections** — 21-step strict compilation order
6. **Export to Excel** — historical + projected side by side (blue columns)
7. **DCF Valuation** — FCFF, WACC, terminal value (Gordon Growth or Exit Multiple), 5×5 sensitivity table

## Key Design Decisions

### No Circular References (MVP)
Interest Expense = Debt(t-1) × Rate — uses beginning-of-period balance, eliminating the classic interest ↔ cash circularity.

### Validation (Historical Upload)
All 8 rules run per year:
1. Balance Sheet: Assets = Liabilities + Equity (±0.5 tolerance)
2. Cash reconciliation: Cash(t) = Cash(t-1) + Net Change in Cash
3–6. P&L cross-checks: Gross Profit, EBIT, EBT, Net Income formulas
7. No blank required fields
8. Revenue decomposition (validated post module config)

Returns `{ tab, line_item, year, error_message }[]` — no partial acceptance.

### Projection Engine Order (21 steps)
```
Revenue → COGS → OpEx → PP&E roll-forward → Intangibles →
EBIT → Debt/Interest → Interest Income → Other Non-Op →
EBT → NOL → Tax → Net Income → Dividends → RE roll-forward →
Equity → Working Capital → Cash Flow (derived) → Cash BS →
Non-Op Assets/Goodwill → BS validation
```

Cash Flow is fully derived — zero user assumption inputs required.

## API Reference

Full OpenAPI docs available at `/docs` when running the backend.

Key endpoints:
- `POST /api/v1/auth/register` — register
- `POST /api/v1/auth/login` — login → JWT
- `GET /api/v1/projects/:id/template/historical` — download Excel template
- `POST /api/v1/projects/:id/upload/historical` — upload + validate
- `PUT /api/v1/projects/:id/assumptions/:module` — save module config
- `POST /api/v1/projects/:id/run` — run projection engine
- `GET /api/v1/projects/:id/projections/export` — export to Excel
- `POST /api/v1/projects/:id/valuation` — run DCF

## Phase 2 Roadmap

See product spec for 15 planned Phase 2 features including: Monte Carlo simulation, scenario manager, circular reference resolution, revolver/cash sweep, multi-currency, LBO/M&A modules, collaboration/sharing.
