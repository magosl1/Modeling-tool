# Financial Modeler - Architecture

## Overview

The Financial Modeler is a web application that allows users to ingest historical financial data (from CSV, Excel, or via AI extraction), map it to a standard Chart of Accounts, configure projection assumptions, and generate projected P&L, Balance Sheet, and Cash Flow statements.

## Tech Stack

- **Frontend:** React (Vite), TypeScript, Tailwind CSS, React Query
- **Backend:** FastAPI, Python 3.11, SQLAlchemy, Celery (for async tasks)
- **Database:** PostgreSQL (primary), Redis (cache & message broker)

## Database Schema (ER Diagram)

Below is the Entity-Relationship diagram for the core data models:

```mermaid
erDiagram
    users {
        uuid id PK
        string email
        string hashed_password
        string role
    }
    
    projects {
        uuid id PK
        uuid owner_id FK
        string name
        int projection_years
        string status
    }
    
    entities {
        uuid id PK
        uuid project_id FK
        uuid parent_entity_id FK
        string name
        string entity_type
        float ownership_pct
        string consolidation_method
    }
    
    historical_data {
        uuid id PK
        uuid project_id FK
        uuid entity_id FK
        string statement_type
        string line_item
        int year
        decimal value
    }
    
    projection_assumptions {
        uuid id PK
        uuid project_id FK
        uuid entity_id FK
        string module
        string line_item
        string projection_method
    }
    
    assumption_params {
        uuid id PK
        uuid assumption_id FK
        string param_key
        int year
        decimal value
    }
    
    projected_financials {
        uuid id PK
        uuid project_id FK
        uuid entity_id FK
        uuid scenario_id FK
        string statement_type
        string line_item
        int year
        decimal value
    }

    user_mapping_memory {
        uuid id PK
        uuid user_id FK
        string original_name
        string mapped_to
        float confidence
    }

    users ||--o{ projects : owns
    projects ||--o{ entities : contains
    entities ||--o{ entities : "has children"
    projects ||--o{ historical_data : has
    entities ||--o{ historical_data : has
    projects ||--o{ projection_assumptions : has
    projection_assumptions ||--o{ assumption_params : has
    projects ||--o{ projected_financials : has
    users ||--o{ user_mapping_memory : has
```

## Application Flow

1. **Upload & Mapping:** Users upload a file (e.g., Excel). `document_extractor.py` reads it safely. `ai_mapper.py` guesses the mapping to canonical line items.
2. **Configuration:** Users review the historical data and setup assumptions per module (Revenue, COGS, OpEx, etc).
3. **Projection Engine:** `projections_runner.py` reads historicals and assumptions, running the 21-step accounting logic.
4. **Celery Worker:** If the projection is long (>10 years), the HTTP endpoint returns a `202 Accepted` and offloads the calculation to a Redis-backed Celery worker.
