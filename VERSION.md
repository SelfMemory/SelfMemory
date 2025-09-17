# Automatic Versioning

This project uses automatic versioning in the CI/CD pipeline. Every commit to the `master` branch will automatically increment the version number.

## How it works

### Patch Versions (Default)
- **Any commit** to master automatically increments the patch version
- Example: `0.2.0` → `0.2.1` → `0.2.2` → `0.2.3`

### Minor Versions
Include `[minor]` or `feat!:` in your commit message to increment the minor version:
```bash
git commit -m "Add new feature [minor]"
git commit -m "feat!: Add new API endpoint"
```
- Example: `0.2.5` → `0.3.0`

### Major Versions
Include `[major]` or `BREAKING:` in your commit message to increment the major version:
```bash
git commit -m "Complete API rewrite [major]"
git commit -m "BREAKING: Remove deprecated methods"
```
- Example: `0.3.2` → `1.0.0`

## What happens automatically

1. **Version Update**: The version in `pyproject.toml` is automatically updated
2. **Git Tag**: A new git tag (e.g., `v0.2.1`) is created
3. **Build**: The package is built with the new version
4. **Publish**: If the version changed, the package is automatically published to PyPI

## Current Version
The current version is: **0.2.0** (as defined in `pyproject.toml`)

## Next Steps
- Next commit will create version `0.2.1`
- To bump to `0.3.0`, include `[minor]` in your commit message
- To bump to `1.0.0`, include `[major]` in your commit message
