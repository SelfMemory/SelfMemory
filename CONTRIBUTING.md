# Contributing to SelfMemory

We welcome contributions to SelfMemory! This document provides guidelines for contributing to the project.

## 🚀 Quick Start

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/selfmemory/selfmemory.git
   cd selfmemory
   ```
3. **Set up development environment**:
   ```bash
   # Create virtual environment
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate

   # Install development dependencies
   pip install -e .[dev,test]

   # Install pre-commit hooks
   pre-commit install
   ```

## 📋 Development Guidelines

### Code Standards

- **Python Version**: Python 3.12+
- **Code Style**: We use `ruff` for linting and formatting
- **Type Hints**: Use type hints for all public APIs
- **Documentation**: Docstrings required for all public functions and classes

### Code Quality Tools

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Fix auto-fixable issues
ruff check --fix .

# Run pre-commit hooks manually
pre-commit run --all-files
```

### Testing

We maintain comprehensive test coverage across three levels:

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/          # Unit tests
pytest tests/integration/   # Integration tests
pytest tests/examples/      # README example validation

# Run with coverage
pytest --cov=selfmemory --cov-report=html
```

**Test Requirements:**
- All new features must include tests
- Maintain >90% test coverage
- Integration tests for end-to-end workflows
- Example tests to validate README code samples

## 🛠️ Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Development Process

1. **Write tests first** (TDD approach recommended)
2. **Implement feature** following existing patterns
3. **Update documentation** if needed
4. **Run tests** to ensure nothing breaks
5. **Format and lint** code

### 3. Commit Guidelines

We use **Conventional Commits** to enable automated versioning and changelog generation. Please read our comprehensive [Commit Guidelines](COMMIT_GUIDELINES.md) for detailed information.

**Quick Format:**
```
<type>(<scope>): <description> | #<issue> | [@username]
```

**Examples:**
```bash
# Feature with issue tracking
git commit -m "feat(search): add semantic search support | #62 | [@shrijayan]"

# Bug fix
git commit -m "fix(storage): resolve connection timeout | #45 | [@shrijayan]"

# Documentation
git commit -m "docs(api): update authentication guide | #78 | [@shrijayan]"

# Breaking change
git commit -m "feat(api)!: redesign search API | #89 | [@shrijayan]"
```

**Commit Types & Version Bumps:**

| Type | Description | Version Bump |
|------|-------------|--------------|
| `feat` | New feature | MINOR (0.3.0 → 0.4.0) |
| `fix` | Bug fix | PATCH (0.3.0 → 0.3.1) |
| `perf` | Performance | PATCH (0.3.0 → 0.3.1) |
| `feat!` | Breaking change | MAJOR (0.3.0 → 1.0.0) |
| `docs` | Documentation | No release |
| `test` | Tests | No release |
| `chore` | Maintenance | No release |

**Important Notes:**
- Every push to `master` with `feat:` or `fix:` commits triggers an **automated release**
- Version is automatically determined from commit messages
- CHANGELOG.md is automatically updated
- Package is automatically published to PyPI

📖 **For detailed guidelines, examples, and best practices, see [COMMIT_GUIDELINES.md](COMMIT_GUIDELINES.md)**

### 4. Pull Request Process

1. **Update your branch** with latest main:
   ```bash
   git checkout main
   git pull upstream main
   git checkout your-branch
   git rebase main
   ```

2. **Push your changes**:
   ```bash
   git push origin your-branch
   ```

3. **Create Pull Request** with:
   - Clear title and description
   - Reference related issues
   - Screenshots/examples if applicable
   - Checklist completion

4. **Pull Request Template:**
   ```markdown
   ## Description
   Brief description of changes made.

   ## Type of Change
   - [ ] Bug fix (non-breaking change)
   - [ ] New feature (non-breaking change)
   - [ ] Breaking change (fix or feature causing existing functionality to change)
   - [ ] Documentation update

   ## Testing
   - [ ] Tests pass locally
   - [ ] New tests added for new functionality
   - [ ] Documentation updated

   ## Related Issues
   Fixes #(issue number)
   ```

## 🏗️ Project Structure

```
selfmemory/
├── selfmemory/           # Core package
│   ├── __init__.py     # Package exports
│   ├── memory.py       # Main Memory class
│   ├── client.py       # Managed service client
│   ├── config/         # Configuration management
│   ├── stores/         # Storage backends
│   ├── search/         # Search engine
│   ├── services/       # Business logic
│   ├── repositories/   # Data access layer
│   ├── api/           # API server
│   ├── security/      # Security utilities
│   └── utils/         # Common utilities
├── tests/             # Test suite
│   ├── unit/          # Unit tests
│   ├── integration/   # Integration tests
│   └── examples/      # Example validation tests
├── docs/              # Documentation
├── examples/          # Usage examples
└── pyproject.toml     # Project configuration
```

## 🎯 Contribution Areas

### High Priority
- **Performance optimizations** for large datasets
- **Additional storage backends** (PostgreSQL, Redis)
- **Enhanced search capabilities** (fuzzy search, faceted search)
- **Security improvements** (audit logging, encryption)

### Medium Priority
- **TypeScript SDK** for Node.js integration
- **More embedding providers** (OpenAI, Cohere, local models)
- **Advanced analytics** (memory usage patterns, search analytics)
- **Migration tools** between storage backends

### Documentation
- **API reference** improvements
- **Tutorial content** for common use cases
- **Architecture documentation** for contributors
- **Performance benchmarks** and optimization guides

### Testing
- **Load testing** for high-volume scenarios
- **Security testing** for enterprise features
- **Cross-platform testing** (Windows, macOS, Linux)
- **Database compatibility testing**

## 🐛 Bug Reports

### Before Reporting
1. **Search existing issues** to avoid duplicates
2. **Test with latest version** to ensure bug still exists
3. **Prepare minimal reproduction** case

### Bug Report Template
```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Initialize Memory with '...'
2. Add memory '...'
3. Search for '...'
4. See error

**Expected behavior**
What you expected to happen.

**Environment:**
- SelfMemory version: [e.g. 0.1.0]
- Python version: [e.g. 3.12.0]
- Operating System: [e.g. macOS 14.0]
- Storage backend: [e.g. file, mongodb]

**Additional context**
Add any other context about the problem here.
```

## 💡 Feature Requests

### Feature Request Template
```markdown
**Is your feature request related to a problem?**
A clear description of what the problem is.

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Any alternative solutions or features you've considered.

**Use case**
Describe your specific use case and how this feature would help.

**Additional context**
Add any other context or screenshots about the feature request.
```

## 📚 Documentation

### Writing Guidelines
- **Clear and concise** language
- **Code examples** for all features
- **Installation instructions** for different environments
- **Troubleshooting guides** for common issues

### Documentation Structure
```
docs/
├── installation-guide.md      # Setup and installation
├── api-reference/            # Complete API documentation
├── examples/                 # Usage examples
├── architecture/             # Technical architecture
├── contributing/             # This file and related guides
└── troubleshooting/          # Common issues and solutions
```

## 🔒 Security

### Reporting Security Issues
- **Do not** open public issues for security vulnerabilities
- **Email** security concerns to: [info@cpluz.com]
- **Include** detailed description and steps to reproduce
- **Allow** reasonable time for investigation before public disclosure

### Security Considerations
- **Input validation** for all user data
- **Secure defaults** in configuration
- **Encryption** for sensitive data
- **API key management** best practices

## 🤝 Community Guidelines

### Code of Conduct
We are committed to providing a welcoming and inspiring community for all. Please read our full [Code of Conduct](CODE_OF_CONDUCT.md).

### Communication Channels
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and community discussion
- **Pull Requests**: Code contributions and reviews

### Getting Help
- **Documentation**: Check existing docs first
- **Examples**: Look at usage examples
- **Issues**: Search existing issues
- **Discussions**: Ask questions in GitHub Discussions

## 🏆 Recognition

Contributors are recognized in:
- **CHANGELOG.md** for their contributions
- **README.md** contributors section
- **Release notes** for significant contributions

### Maintainer Responsibilities
- **Code review** within 48 hours
- **Issue triage** and labeling
- **Release management** and versioning
- **Community engagement** and support

## 📄 License

By contributing to SelfMemory, you agree that your contributions will be licensed under the [Apache 2.0 License](LICENSE.txt).

---

## 🙏 Thank You

Thank you for your interest in contributing to SelfMemory! Your contributions help make this project better for everyone. If you have questions about contributing, please don't hesitate to ask in GitHub Discussions or open an issue.

**Happy coding!** 🚀
