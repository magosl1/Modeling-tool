# Handoff — Modeling Tool

Documento de continuación para retomar el trabajo en otra sesión / IDE.

## Repo & branch
- Repo: `magosl1/Modeling-tool`
- Trabajo actual mergeado a `main` (último commit `41b92c1`).
- Branch de feature donde se hizo el trabajo: `claude/fix-ai-ingestion-pipeline-TGOWt` (ya fast-forwarded a main).

## Levantar el entorno
- Windows: `start_app.bat` (Docker Compose, proyecto `modelo-tool-new`).
- Servicios: `backend` (FastAPI), `frontend` (Vite/React), `db` (Postgres), `redis`, `celery_worker`.
- **Antes de probar el sector + AI**: aplicar migraciones nuevas dentro del backend container:
  ```
  alembic upgrade head
  ```
  Migraciones añadidas: `0009_project_sector`, `0010_assumption_rationale`.

## Visión del producto (norte)
"Cualquier analista con conocimientos básicos modela una empresa": elige sector → sube históricos → la IA arma el primer modelo con justificaciones → el usuario juega con sliders y ve el equity value en vivo. Compliance/sofisticación (audit trail, versionado, peers) son Tier 1.

---

## Lo que YA está hecho (Tier 0 v2)

| # | Feature | Commit | Archivos clave |
|---|---|---|---|
| F | Polling async proyecciones >10 años | `7ecdeca` | `frontend/src/services/api.ts` (`projectionsApi.run`) |
| 4 | Edición de assumptions por escenario | `246bc66` | `backend/app/api/routes/assumptions.py`, `frontend/src/store/scenarioStore.ts`, `frontend/src/components/modules/AssumptionsPanel.tsx` |
| 3 | ScenarioCompare side-by-side con Δ% | `155c54d` | `frontend/src/components/scenarios/ScenarioCompare.tsx` |
| A+B | Sector picker + auto-seed sector-aware | `b64fbe7` | `backend/app/services/sectors.py` (catálogo 13 sectores), `backend/app/services/assumption_service.py`, `backend/alembic/versions/0009_project_sector.py`, `frontend/src/components/project/ProjectSetup.tsx` |
| C | AI Hypothesis Engine + rationale inline | `6ac4a49` | `backend/app/services/ai_hypothesis_service.py`, `backend/alembic/versions/0010_assumption_rationale.py`, `frontend/src/components/modules/ModuleConfigurator/index.tsx` (banner 💡), `frontend/src/components/project/ProjectDashboard.tsx` (botón "Build with AI") |
| D | What-If sliders en vivo (sin persistir) | `41b92c1` | `backend/app/api/routes/whatif.py`, `frontend/src/components/whatif/WhatIfPanel.tsx` |

### Convenciones útiles
- **Escenarios**: el "base" siempre se persiste con `scenario_id IS NULL` en DB. Override scenarios usan su UUID. Ver `_resolve_scenario_id` en `backend/app/api/routes/assumptions.py`.
- **Catálogo de sectores**: `backend/app/services/sectors.py::SECTORS`. Cada sector tiene `defaults: SectorDefaults` (growth, margin, opex %, capex %, días WC, tax, WACC, terminal growth, exit multiple) y `line_item_hints` para que el matcher reconozca cuentas específicas (SaaS → ARR/MRR, Real Estate → NOI).
- **What-if** nunca persiste — para hacer permanente un escenario, crear un nuevo Scenario y editar sus assumptions.
- **Rationale** se persiste en `ProjectionAssumption.rationale` (≤500 chars).

---

## Próximos pasos — Tier 1 (analista pro / compliance)

Recomendación de orden:

### 1. Audit trail global (compliance LP) — alta prioridad
- **Por qué**: ningún fondo serio acepta una herramienta sin "quién cambió qué cuándo".
- **Qué hacer**:
  - Tabla nueva `change_log` (`id`, `project_id`, `user_id`, `entity` ej: 'assumption'/'historical'/'scenario', `entity_id`, `action` (`create`/`update`/`delete`), `before_json`, `after_json`, `created_at`).
  - SQLAlchemy event listeners (`before_update`, `after_insert`, `after_delete`) en los modelos críticos (`ProjectionAssumption`, `AssumptionParam`, `HistoricalData`, `Scenario`, `ValuationInput`).
  - Endpoint `GET /projects/{id}/changelog?entity=&since=`.
  - UI: timeline en sidebar del project workspace.

### 2. Versionado de históricos
- **Por qué**: re-subir Excel hoy sobreescribe — no se puede revertir ni comparar versiones.
- **Qué hacer**:
  - Tabla `historical_snapshots` (`id`, `project_id`, `version`, `created_at`, `created_by`, `source_file_id`).
  - `HistoricalData` añade `snapshot_id` (NOT NULL, default activo).
  - Endpoint `POST /projects/{id}/historical/snapshot` (clona current), `GET /historical/snapshots`, `POST /historical/snapshots/{id}/activate`.
  - UI: dropdown de versiones en `UploadHistorical*.tsx` + diff visual.

### 3. Formula audit drill-down (motivo #1 por el que analistas no confían)
- **Por qué**: click en "Net Income" → ver fórmula `EBT − Tax = NI` y trace de dónde sale cada componente.
- **Qué hacer**:
  - Modificar `ProjectionEngine` para emitir `provenance: Dict[(year, statement, line_item) → {formula: str, inputs: list[(line_item, year, value)]}]`.
  - Devolver `provenance` en `/projections` GET (opcional, query param `?include=provenance`).
  - UI: tooltip/popover en cada celda de las tablas P&L/BS/CF con la fórmula.

### 4. Comparables / peer multiples
- **Por qué**: cierra el loop de valoración (DCF dice $X equity → ¿qué EV/EBITDA implica vs peers?).
- **Qué hacer**:
  - Tabla `peer_companies` (`id`, `project_id`, `ticker`, `name`, `ev_ebitda`, `ev_revenue`, `pe_ratio`, `as_of`).
  - Endpoint CRUD + uno opcional `/projects/{id}/peers/auto-suggest` que llama LLM con el sector + descripción para sugerir peers.
  - UI: tab "Comparables" en `ValuationView` con tabla peers + multiples implícitos del DCF lado a lado.

### 5. Reportes PDF (investment memo)
- **Por qué**: hoy el Excel es raw — el output presentable a IC se hace a mano en PowerPoint.
- **Qué hacer**:
  - Backend: librería `reportlab` o `weasyprint`. Endpoint `GET /projects/{id}/report.pdf`.
  - Plantilla: portada con sector + tesis, sumario ejecutivo (KPIs terminales por escenario), 3 estados financieros formateados, DCF + sensitivity, gráfico de revenue/EBITDA.
  - UI: botón "Download Memo" en dashboard.

### 6. (Bonus) Conflict warning multi-usuario
- WebSocket o polling: "Alice está editando Revenue ahora". Evita last-write-wins silencioso.

---

## Bugs/deuda conocidos
- **Gemini 503**: el endpoint AI Hypothesis llama a `smart_complete` que usa el modelo configurado del usuario. Si Gemini está caído, el fallback es cambiar modelo en Settings → AI. Considerar retry con backoff en `llm_client.py`.
- **Schema strip para Gemini**: ver `llm_client.py` — limpieza de `additionalProperties` puede romper schemas con `Dict`. Si la IA devuelve `values: []` vacíos, ese es el lugar a investigar.
- **`ScenarioCompare` necesita que cada escenario haya corrido proyecciones al menos una vez** — el aviso amarillo lo indica pero podría auto-correrlas en demand.
- **`WhatIfPanel`** asume que ya hay assumptions configuradas y al menos un año histórico — devuelve 400 si no.

## Archivos importantes que NO debes tocar sin entender
- `backend/app/services/projection_engine.py` — 21 steps deterministas, snapshot-tested. Romper el orden rompe todo.
- `backend/app/services/dcf_engine.py` — FCFF + sensitivity. Math frágil con WACC ≤ g.
- `backend/app/services/projections_runner.py::transform_assumptions` — pega entre formato DB (módulos planos) y el formato anidado que `ProjectionEngine` espera.

## Para empezar rápido
1. `git pull origin main`
2. Levantar entorno y aplicar migraciones.
3. Crear un proyecto con sector "SaaS" y subir un Excel histórico.
4. Click "Build with AI" → verificar que las cards muestran 💡 con justificación.
5. Mover sliders del WhatIfPanel → equity value debe cambiar en vivo.

Si todo eso funciona, atacar Tier 1 #1 (audit trail).
