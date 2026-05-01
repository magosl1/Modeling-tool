# Contributing to Financial Modeler

Welcome! This document outlines the development conventions and workflow for this repository.
Our primary guiding principle is **"ship small, ship often"**. We value lean code, test-driven logic, and avoiding premature abstractions.

## Development Environment

### Backend
- **Python 3.11+**
- We use `pip` for dependencies. 
- Install dev dependencies: `pip install -r requirements-dev.txt`
- We use **Ruff** for linting and formatting. It is configured in `pyproject.toml`.
- Run tests with **pytest**: `pytest tests/`

### Frontend
- **Node.js 18+**
- Install dependencies: `npm install`
- We use **ESLint** and **Prettier**.
- Run tests with **Vitest**: `npm run test`

## Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/). This means all commit messages must start with an appropriate prefix:

- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `style:` for formatting, missing semi-colons, etc.
- `refactor:` for refactoring production code, e.g. renaming a variable
- `test:` for adding missing tests or correcting existing tests
- `chore:` for updating grunt tasks etc; no production code change

Example: `feat(api): add Celery async projection task`

## Pull Request Guidelines

1. **Keep it small**: Break down large features into smaller PRs.
2. **Tests are mandatory**: Any new feature or bug fix must include an automated test (pytest for backend, vitest for frontend).
3. **No dead code**: Actively remove unused functions or imports.
4. **Pass CI**: Ensure the GitHub Actions pipeline (Lint, Pytest, NPM Build) is green before requesting review.

## Pre-commit Hooks

We strongly recommend installing the pre-commit hooks to automatically format your code before pushing:
```bash
pip install pre-commit
pre-commit install
```
