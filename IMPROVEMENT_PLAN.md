# Plan de Mejora — Financial Modeling Tool

> Documento vivo. Se actualiza a medida que se completan tareas o se descubren nuevas. Principio guía: **mantenerlo lean** — añadir solo lo necesario, borrar lo que ya no aplique, evitar abstracciones prematuras.

Última actualización: 2026-04-19

---

## Principios

1. **Ship small, ship often** — cada PR debe dejar el repo más sano, no más grande.
2. **No añadir features sin tests** (a partir de la Fase 1).
3. **Borrar código muerto agresivamente** — el diagnóstico ya detectó deps y campos sin uso.
4. **Preferir la solución simple** — evitar frameworks, capas y helpers "por si acaso".
5. **Medir antes de refactorizar** — si un módulo funciona y no bloquea, no es prioridad.

---

## Estado por fase

### Fase 1 — Fundamentos de calidad (P0)

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 1.1 | Sacar secrets de `docker-compose.yml` | ✅ | `.env`/`.env.example` en raíz, validación en `config.py` |
| 1.2 | Alembic baseline + migrar Phase 0/2/3 | ✅ | `0001_baseline`, SQL sueltos en `backend/migrations_legacy/`, `init_db` auto-stamp |
| 1.3 | CI básico (lint + tests + build) | ✅ | `.github/workflows/ci.yml` (pytest + `npm run build`) |
| 1.4 | Scaffold pytest + tests iniciales | ✅ | 7 tests (utils, DCF). `requirements-dev.txt`, `pytest.ini`, `tests/conftest.py` |
| 1.5 | Vitest + primer test frontend | ✅ | `formatters.test.ts` (6 tests). Script `npm test`, CI corre vitest antes del build. Fix de errores TS preexistentes en `ValuationView` y `LiveProjectionsView` |
| 1.6 | Ampliar tests: `debt_schedule`, `historical_validator` | ✅ | 10 tests nuevos (7 validator + 3 debt schedule). Total backend: 17 tests |
| 1.7 | Añadir ruff al CI | ✅ | `pyproject.toml` con reglas F+I, `ruff check` bloqueante. Codebase limpio tras auto-fix (45 imports ordenados) |
| 1.8 | Tests del `projection_engine` (21 pasos) | ✅ | Snapshot test golden-file (`test_projection_engine_snapshot.py` + `snapshots/projection_engine_v1.json`); 213 líneas de output PNL/BS/CF locked. Para refactores intencionales: borrar el JSON y rerun |

### Fase 2 — Tooling y seguridad (P1)

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 2.1 | Ruff + pre-commit (mypy diferido) | ✅ | `.pre-commit-config.yaml` con ruff + hooks estándar |
| 2.2 | ESLint + Prettier + tsconfig strict | ✅ | `noUnusedLocals/Parameters` activos, ESLint mínimo (recommended + react-hooks) |
| 2.3 | RBAC enforcement en `project_shares` | ✅ | 3 helpers (`get_project_or_404` / `_for_write` / `_for_owner`); 13 routes con write permission; sharing.py owner-only; 4 tests (`test_rbac.py`) |
| 2.4 | Exception handlers globales + structlog | ✅ | `app/core/{logging,errors}.py`, schema uniforme `{error: {code, message, request_id, details?}}`, X-Request-ID middleware, 4 tests |
| 2.5 | Auditar y limpiar dependencias | ✅ | Eliminadas 8 deps no usadas (`pandas`, `httpx` movido a dev, `yfinance`, `fuzzywuzzy`, `python-Levenshtein`, `numpy`, `numpy-financial`, `reportlab`); todas pinneadas con `==`; añadido `structlog` |

### Fase 3 — Refactor del core (P1/P2)

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 3.1 | Descomponer `projection_engine.py` (934 LOC) | ✅ | Subpackage `app/services/projections/` con 4 mixins (`_state`/`income_statement`/`balance_sheet`/`cash_flow`) orquestados en `engine.py`. Mayor archivo: 317 LOC (income_statement). Snapshot test pasa sin cambios → behavior idéntico. Shim en `projection_engine.py` para back-compat |
| 3.2 | Descomponer `ModuleConfigurator.tsx` (537 LOC) | ✅ | Carpeta `ModuleConfigurator/` con 5 archivos: `constants.ts` (165, maps + types), `HistoricalContext.tsx` (34), `PxQForm.tsx` (99), `ParamFields.tsx` (81), `index.tsx` (257, main). Default export preservado |
| 3.3 | Descomponer `ProjectionsView.tsx` (484 LOC) | ✅ | Carpeta `ProjectionsView/` con 5 archivos: `constants.ts` (60, PNL/BS/CF_ITEMS + helpers), `FinancialTable.tsx` (151, con SubRow), `KeyMetricsStrip.tsx` (81), `AssumptionsSummary.tsx` (75), `index.tsx` (240 main) |
| 3.4 | Cerrar transición Phase 0 (entity_id NOT NULL) | ✅ | Alembic `0002_entity_id_not_null` (backfill + ALTER), modelos `nullable=False` en 3 tablas, `create_project` siembra entity por defecto, ramas legacy removidas de `entities.py`/`projections.py`, test de migración |

### Fase 4 — Robustez operacional (P2)

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 4.1 | Celery real para jobs largos | ⏳ pendiente | Sólo si projection_years > 10 |
| 4.2 | Structured logging + /health + /metrics | ⏳ pendiente | structlog JSON |

### Fase 5 — Docs y DX (P3)

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 5.1 | Diagrama ER + ARCHITECTURE.md | ⏳ pendiente | Mermaid en README |
| 5.2 | CONTRIBUTING.md | ⏳ pendiente | Convenciones commits |

---

## Leyenda

- ✅ completado
- 🟡 en curso
- ⏳ pendiente
- ❌ descartado (con nota del motivo)

---

## Registro de cambios

<!-- Formato: fecha · tarea · resultado -->

- 2026-04-18 · Plan inicial creado tras revisión exhaustiva del proyecto.
- 2026-04-18 · **1.1** secrets fuera de `docker-compose.yml`: POSTGRES_* y SECRET_KEY se leen de `.env` de la raíz; el backend aborta si `DEBUG=false` y `SECRET_KEY` es un default conocido.
- 2026-04-18 · **1.2** Alembic activado con revisión `0001_baseline` vacía. Scripts Phase 0/2/3 movidos a `backend/migrations_legacy/` con README del orden. `init_db.create_tables` hace `command.stamp("head")` para fresh installs.
- 2026-04-18 · **1.4** Scaffold de pytest: `backend/requirements-dev.txt`, `backend/pytest.ini`, `backend/tests/{__init__,conftest}.py`, `backend/tests/unit/test_utils.py` y `test_dcf_engine.py`. 7 tests verdes (Gordon growth invariant, FCFF happy path, mid-year > end-of-year, helpers de `Decimal`).
- 2026-04-18 · **1.3** CI en `.github/workflows/ci.yml`: job `backend` ejecuta `pytest`, job `frontend` ejecuta `npm run build` (tsc + vite build). Con cache de pip y npm.
- 2026-04-18 · **1.5** Vitest configurado (`vite.config.ts#test`, `package.json#scripts.test`). Primer test: `formatters.test.ts` (6 casos). Corregidos errores TS preexistentes en `ValuationView.tsx` (campos opcionales de `ValuationResult`) y `LiveProjectionsView.tsx` (narrowing de tabs PNL/BS/CF/RATIOS) para desbloquear `npm run build` en CI.
- 2026-04-18 · **1.6** 10 tests backend adicionales: `test_historical_validator.py` (7 reglas, happy + fail por regla) y `test_debt_schedule.py` (revolver draw, bullet maturity, empty config). Total backend = 17 tests.
- 2026-04-18 · **1.7** Ruff integrado: `backend/pyproject.toml` con selección F+I, auto-fix aplicado a 45 imports. `ruff check` añadido como paso bloqueante del job backend en CI.
- 2026-04-19 · **2.1** `.pre-commit-config.yaml` con ruff (lint + format) y hooks estándar (trailing-whitespace, end-of-file, yaml/json/toml). Mypy se difiere a fase 3 para no bloquear con un codebase aún en evolución.
- 2026-04-19 · **2.2** ESLint + Prettier + tsconfig strict. `noUnusedLocals/Parameters=true` desbloquea detección temprana de muerto en componentes. ESLint mínimo: extends recommended + react-hooks (sin reglas estilísticas por encima de Prettier).
- 2026-04-19 · **2.3** RBAC end-to-end. Tres helpers en `app/api/deps.py`: `get_project_or_404` (lectura: owner/viewer/editor), `get_project_for_write` (owner/editor; viewer→403), `get_project_for_owner` (sólo owner; outsider→404 para no filtrar existencia). Sweep automatizado actualizó 13 routes (POST/PUT/DELETE/PATCH) a `_for_write`; `sharing.py` a `_for_owner`. 4 tests en `tests/unit/test_rbac.py`. Bug fixes aflorados: índices duplicados en `project.py` (`ix_*_entity_id`) y self-referential relationship rota en `entity.py` (faltaba `remote_side`). `Settings.Config.extra="ignore"` para tolerar variables extra en `.env`.
- 2026-04-19 · **2.4** Schema de errores uniforme: `{"error": {"code", "message", "request_id", "details?"}}`. Tres handlers en `app/core/errors.py` (HTTPException, RequestValidationError, Exception catch-all). `request_id_middleware` propaga/genera `X-Request-ID` y lo enlaza a `structlog.contextvars` para correlación logs↔respuesta. `app/core/logging.py` con structlog (JSON en prod, ConsoleRenderer en DEBUG). 4 tests cubren los tres handlers + propagación de request_id entrante.
- 2026-04-19 · **2.5** Auditoría de deps: 8 paquetes sin un solo `import` en `app/` eliminados (`pandas`, `yfinance`, `fuzzywuzzy`, `python-Levenshtein`, `numpy`, `numpy-financial`, `reportlab`); `httpx` movido a `requirements-dev.txt` (sólo lo usa `TestClient`). `requirements.txt` pasa de 24 a 17 líneas, todas con `==`. Añadido `structlog==24.4.0`. Resultado: install más rápido y menos superficie de seguridad.
- 2026-04-19 · **1.8** Snapshot test del `projection_engine` como red de seguridad pre-refactor 3.1. `tests/unit/test_projection_engine_snapshot.py` corre el motor con input fijo (1 año histórico + 2 de proyección, todos los módulos) y compara el output canonical-JSON contra `snapshots/projection_engine_v1.json` (213 líneas: PNL+BS+CF+errors+warnings). Si el snapshot no existe el test lo crea y falla con instrucción de revisar/commit; refactor intencional → borrar JSON y rerun.
- 2026-04-19 · **3.4** Cerrada transición Phase 0. Nueva migración `0002_entity_id_not_null.py` backfill-and-tighten: para cada proyecto con filas legacy (`entity_id IS NULL`) asegura una Entity por defecto (crea una con nombre = nombre del proyecto si no existe), actualiza las filas, y ALTERa a NOT NULL las 3 tablas afectadas (`historical_data`, `projection_assumptions`, `projected_financials`). Modelos migrados a `nullable=False`. `create_project` siembra una Entity por defecto inline (todo proyecto nuevo ya cumple invariante). Eliminado `get_or_create_default_entity` y auto-provision en `list_entities`; `projections.py` hace un simple `first()` fallback-404. Test `test_phase0_finalize_migration.py` verifica backfill + attach en SQLite.
- 2026-04-19 · **3.3** `ProjectionsView.tsx` (484 LOC) → carpeta con 5 archivos: `constants.ts` (ordenes de líneas PNL/BS/CF + SUBTOTALS/COST_LINES + helpers `fmtVal`/`growth`), `FinancialTable.tsx` (+SubRow interno), `KeyMetricsStrip.tsx` (Net Debt / Equity / EBITDA), `AssumptionsSummary.tsx` (collapsible), `index.tsx` (main component con react-query + tabs). Importadores (`ProjectWorkspace`, `EntityWorkspace`) sin cambios. tsc + ESLint + vitest verdes.
- 2026-04-19 · **3.2** `ModuleConfigurator.tsx` (537 LOC) → carpeta con 5 archivos: `constants.ts` (MODULE_DEFAULTS, METHOD_PARAMS, MODULE_METHODS, METHOD_LABELS, MODULE_STATEMENT, LINE_ITEM_HIST_KEY + types), `HistoricalContext.tsx`, `PxQForm.tsx` (con sub-helper interno), `ParamFields.tsx` (los 3 layouts: optional/per-year/single), `index.tsx` main (257 LOC, todos los updaters + JSX). Importadores sin cambios (default export + `index.tsx` resuelve igual que el .tsx antiguo). tsc + ESLint + vitest verdes.
- 2026-04-19 · **3.1** `projection_engine.py` (934 LOC) → subpackage `app/services/projections/` con 5 archivos: `_state.py` (138, constructor + helpers + `ProjectionResult`), `income_statement.py` (317, Revenue/COGS/OpEx/EBIT/Interest Income/Other Non-Op/EBT/Tax/NOL/Net Income/Dividends), `balance_sheet.py` (276, PP&E+D&A, Intangibles+Amort, Debt+Interest Expense, RE, Equity, Working Capital, Non-Op Assets), `cash_flow.py` (135, CF derivation + Cash BS + BS validation), `engine.py` (82, orquesta los 21 pasos componiendo los mixins). Shim de 8 líneas en `projection_engine.py` preserva la API pública. Snapshot test pasa sin cambios → behavior 100% equivalente.
