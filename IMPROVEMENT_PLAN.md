# Plan de Mejora — Financial Modeling Tool

> Documento vivo. Se actualiza a medida que se completan tareas o se descubren nuevas. Principio guía: **mantenerlo lean** — añadir solo lo necesario, borrar lo que ya no aplique, evitar abstracciones prematuras.

Última actualización: 2026-04-18

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
| 1.5 | Vitest + primer test frontend | ⏳ pendiente | Meta: 20% cobertura |
| 1.6 | Ampliar tests: `debt_schedule`, `historical_validator`, steps del motor | ⏳ pendiente | Avanzar hacia 40% backend |
| 1.7 | Añadir linter al CI (ruff) | ⏳ pendiente | Primero sin romper, solo reporte |

### Fase 2 — Tooling y seguridad (P1)

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 2.1 | Ruff + mypy + pre-commit | ⏳ pendiente | Backend |
| 2.2 | ESLint + Prettier + tsconfig strict | ⏳ pendiente | Activar `noUnusedLocals` |
| 2.3 | RBAC enforcement en `project_shares` | ⏳ pendiente | viewer/editor |
| 2.4 | Exception handlers globales + structlog | ⏳ pendiente | Error schema unificado |
| 2.5 | Pinnear deps con `>=` y auditar usadas | ⏳ pendiente | yfinance, reportlab, fuzzywuzzy |

### Fase 3 — Refactor del core (P1/P2)

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 3.1 | Descomponer `projection_engine.py` (934 LOC) | ⏳ pendiente | Por dominio, NO por paso |
| 3.2 | Descomponer `ModuleConfigurator.tsx` (537 LOC) | ⏳ pendiente | Subcomponentes por método |
| 3.3 | Descomponer `ProjectionsView.tsx` (491 LOC) | ⏳ pendiente | Tabla/Chart/Selector |
| 3.4 | Cerrar transición Phase 0 (entity_id NOT NULL) | ⏳ pendiente | Eliminar ramas legacy |

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
