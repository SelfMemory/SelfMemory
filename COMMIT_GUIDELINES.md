# Commit Guidelines

SelfMemory uses [Conventional Commits](https://www.conventionalcommits.org/) to automate versioning and changelog generation. All commits to `master` are parsed by [python-semantic-release](https://python-semantic-release.readthedocs.io/) to determine version bumps.

## Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

## Types

| Type | Description | Version Bump |
|------|-------------|--------------|
| `feat` | New feature | Minor (0.8.0 → 0.9.0) |
| `fix` | Bug fix | Patch (0.8.0 → 0.8.1) |
| `perf` | Performance improvement | Patch (0.8.0 → 0.8.1) |
| `docs` | Documentation only | None |
| `style` | Code style (formatting, whitespace) | None |
| `refactor` | Code change that neither fixes a bug nor adds a feature | None |
| `test` | Adding or updating tests | None |
| `build` | Build system or external dependencies | None |
| `ci` | CI/CD configuration | None |
| `chore` | Maintenance tasks | None |

## Scopes

Use scopes to indicate the area of the codebase affected:

| Scope | Area |
|-------|------|
| `core` | Core memory engine (`selfmemory/`) |
| `api` | REST API server (`selfmemory/api/`) |
| `mcp` | MCP server (`selfmemory-mcp/`) |
| `search` | Search engine (`selfmemory/search/`) |
| `security` | Security and encryption (`selfmemory/security/`) |
| `auth` | Authentication (`selfmemory/auth/`) |
| `store` | Storage backends (`selfmemory/stores/`) |
| `config` | Configuration (`selfmemory/config/`) |
| `cli` | CLI interface |
| `deps` | Dependencies |
| `docker` | Docker configuration |

Scopes are optional but encouraged for clarity.

## Examples

```bash
# New feature
feat(search): add fuzzy matching support

# Bug fix
fix(store): resolve connection timeout on large datasets

# Breaking change (note the !)
feat(api)!: redesign search endpoint response format

BREAKING CHANGE: The search endpoint now returns results in a paginated format.
The `results` field is now wrapped in a `data` object with `items` and `total` fields.

# Performance improvement
perf(core): optimize embedding batch processing

# Documentation
docs(api): update authentication guide

# Refactor
refactor(security): extract encryption logic into separate module

# Tests
test(search): add integration tests for semantic search

# CI/CD
ci: add CodeQL security scanning workflow

# Dependencies (used by Dependabot)
chore(deps): bump fastapi from 0.115.0 to 0.116.0
```

## Breaking Changes

For breaking changes, either:

1. Add `!` after the type/scope: `feat(api)!: redesign search endpoint`
2. Add a `BREAKING CHANGE:` footer in the commit body

Breaking changes trigger a **major** version bump (when `major_on_zero` is enabled).

## Multi-line Commits

Use the body for additional context:

```
fix(store): resolve race condition in concurrent writes

The Qdrant store was not properly locking during batch upsert operations,
causing intermittent failures when multiple agents wrote simultaneously.

Added a mutex lock around the upsert operation and increased the
connection pool size to handle concurrent requests.

Closes #123
```

## Commit Validation

Commits are validated locally by [commitizen](https://commitizen-tools.github.io/commitizen/) via a pre-commit hook. Invalid commit messages will be rejected:

```bash
# This will be rejected
git commit -m "fixed the bug"

# This will pass
git commit -m "fix(core): resolve memory deduplication issue"
```

To install the hooks:

```bash
uv run pre-commit install
```

## Automated Releases

Every push to `master` with `feat:` or `fix:` commits triggers:

1. Version bump (determined from commit types)
2. CHANGELOG.md update
3. Git tag creation
4. GitHub release with release notes
5. PyPI package publish
