## ADDED Requirements

### Requirement: Python wheel builds include the dashboard

Every Python wheel build SHALL compile the locked frontend and package the
resulting dashboard with the backend.

#### Scenario: A wheel is built outside the release workflow

- **GIVEN** a clean source checkout with Bun available
- **WHEN** a PEP 517 frontend builds the codex-lb wheel
- **THEN** the build installs the frontend dependencies from the lockfile
- **AND** compiles the frontend
- **AND** the wheel contains `app/static/index.html`
- **AND** the wheel contains generated JavaScript and CSS assets

#### Scenario: Frontend compilation is incomplete

- **GIVEN** the frontend build does not produce its HTML entry point, JavaScript, or CSS
- **WHEN** the wheel build validates the generated assets
- **THEN** the wheel build fails instead of publishing a backend-only package
