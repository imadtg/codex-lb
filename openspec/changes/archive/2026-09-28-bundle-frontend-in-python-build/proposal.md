## Why

Python installations built directly from a Git checkout currently omit the
dashboard because only the release workflow builds `app/static` before Hatch
assembles the wheel. Every supported Python build path should produce the same
complete application package.

## What Changes

- Add a wheel build hook that installs the locked frontend dependencies and
  builds the dashboard before Hatch collects wheel artifacts.
- Fail the wheel build unless the generated dashboard contains its HTML entry
  point plus JavaScript and CSS assets.
- Remove the release workflow's duplicate frontend build steps while retaining
  its independent inspection of the finished wheel.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release-automation`: every Python wheel build owns frontend compilation and
  produces the complete application package.

## Impact

- `pyproject.toml`, `hatch_build.py`, and `.github/workflows/release.yml`
- Git based `uvx` installs now require Bun while building the wheel.
