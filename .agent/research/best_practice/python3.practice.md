# Modern Python 3 Best Practices: Deep Dive Research

> Comprehensive research into software engineering excellence for Python 3.12+ covering architecture, conventions, and data pipeline patterns.

---

## 1. Python 3.12+ Language Features

### Python 3.13 Highlights (October 2024)

| Feature | Impact |
|---------|--------|
| **Experimental JIT Compiler** | 10-15% CPU performance boost, up to 40% in some scenarios |
| **Free-threaded CPython (No-GIL)** | Experimental support for disabling GIL for true parallelism |
| **Incremental Garbage Collector** | Reduced memory usage |
| **Improved Error Messages** | Contextual hints, IntelliSense-style suggestions |
| **Stripped Docstring Indentation** | Cleaner docstrings |

### Modern Python Idioms

- **f-strings**: Preferred for string formatting (t-strings coming in 3.14)
- **`pathlib`**: Use `Path` objects instead of string path manipulation
- **`zoneinfo`**: Always use timezone-aware `datetime` objects (prefer UTC)
- **`os.scandir()`**: More efficient than `os.listdir()` for directory iteration
- **`breakpoint()`**: Use for debugging instead of `import pdb; pdb.set_trace()`
- **`subprocess`**: Safe external command execution (avoid `os.system`)

---

## 2. Project Structure & Tooling

### The `src` Layout (Recommended)

```
project-root/
├── src/
│   └── my_package/
│       ├── __init__.py
│       ├── domain/           # Business logic, pure functions
│       ├── application/      # Use-cases, orchestration
│       ├── infrastructure/   # External dependencies (HTTP, DB, FS)
│       └── cli.py            # Entry point
├── tests/
│   ├── conftest.py           # Fixtures only
│   ├── fakes/                # Test doubles
│   └── test_*.py
├── pyproject.toml            # All config here
├── README.md
└── .gitignore
```

**Why `src` Layout?**

- Prevents accidental imports of in-development code
- Tests run against the *installed* package
- Clear separation of source from config/docs/tests
- Smaller, cleaner distribution packages

### Modern Tooling Stack

| Tool | Purpose | Replaces |
|------|---------|----------|
| **`uv`** | Package/project manager (extremely fast, Rust-based) | pip, poetry, pyenv, pipx, virtualenv, twine |
| **`ruff`** | Linter + formatter (Rust-based, extremely fast) | black, flake8, isort, pylint |
| **`pyright`** | Static type checker | mypy (either works; pyright is faster) |
| **`pytest`** | Testing framework | unittest |
| **`import-linter`** | Architecture enforcement | Manual review |

### `pyproject.toml` as Single Config Source

All tool configuration in one file:

- Project metadata (PEP 621)
- Dependencies and dev groups
- `ruff`, `pyright`, `pytest`, `import-linter` config

---

## 3. Type System & Data Modelling

### Type Hints Best Practices

```python
# ✅ Modern Python 3.10+ style
def process_items(items: list[str]) -> dict[str, int]:
    ...

# ✅ Use Optional for nullable types
def find_user(id: int) -> User | None:
    ...

# ✅ Use Union sparingly
def parse_input(data: str | bytes) -> Result:
    ...
```

**Guidelines:**

- Apply type hints consistently throughout the codebase
- Use built-in generics (`list[str]`) over `typing.List[str]`
- Avoid over-complicated hints; keep them readable
- No `Any` in domain code; allow only at IO boundaries

### Dataclasses vs Pydantic

| Use Case | Prefer |
|----------|--------|
| Internal data structures | `dataclasses` |
| IO validation & parsing | Pydantic |
| Immutable value objects | `dataclasses(frozen=True)` |
| Configuration objects | Pydantic with `frozen=True` |
| API request/response | Pydantic |

**Dataclass Best Practices:**

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)  # Immutable + memory efficient
class Company:
    name: str
    number: str
    incorporated_date: date | None = None
```

**Pydantic Best Practices:**

```python
from pydantic import BaseModel, Field
from typing import Annotated

class CompanyProfile(BaseModel):
    model_config = {"frozen": True}  # Immutable
    
    name: str
    employees: Annotated[int, Field(ge=0)]  # Constraints via Annotated
```

**Pydantic Guidelines:**

- Validate at IO boundaries (as soon as data enters the system)
- Keep validators narrow (one rule per validator)
- Compose with sub-models for complex structures
- Avoid business logic in models; keep them as validated containers

### Protocol vs ABC

| Criteria | `typing.Protocol` | `abc.ABC` |
|----------|-------------------|-----------|
| Subtyping | Structural ("duck typing") | Nominal (explicit inheritance) |
| When to use | Third-party integration, flexibility | Internal hierarchy, code reuse |
| Runtime enforcement | Only with `@runtime_checkable` | Yes, raises on instantiation |
| Ideal for | DI contracts, adapters | Internal frameworks with shared implementations |

**Preferred Pattern for DI:**

```python
from typing import Protocol

class HttpClient(Protocol):
    def get(self, url: str) -> bytes: ...
    def post(self, url: str, data: bytes) -> bytes: ...

# Any class with matching methods satisfies HttpClient
# No inheritance required
```

---

## 4. Architecture Patterns

### Domain-Driven Layered Architecture

```
┌─────────────────────────────────────────────────┐
│                      CLI                        │  Entry point only
├─────────────────────────────────────────────────┤
│               Application Layer                 │  Use-cases, orchestration
├─────────────────────────────────────────────────┤
│                 Domain Layer                    │  Business logic, entities
├─────────────────────────────────────────────────┤
│             Infrastructure Layer                │  HTTP, DB, FS adapters
└─────────────────────────────────────────────────┘
```

**Dependency Rules (enforce with `import-linter`):**

- Domain → (nothing external)
- Application → Domain only
- Infrastructure → Implements Protocols from Domain/Application
- CLI → Application (wires dependencies)

### Hexagonal Architecture (Ports & Adapters)

- **Core (Domain):** Pure business logic, no external dependencies
- **Ports (Protocols):** Define interfaces for external interactions
- **Adapters:** Implement ports for specific technologies (HTTP, DB, etc.)

Benefits:

- Swap adapters without changing domain logic
- Core is fully testable in isolation
- Framework independence

### Clean Architecture Principles

1. **Dependency Rule:** Dependencies point inward (outer layers depend on inner)
2. **Entities:** Core business objects and rules
3. **Use Cases:** Application-specific business rules
4. **Interface Adapters:** Convert data between layers
5. **Frameworks/Drivers:** External tools and frameworks

---

## 5. Dependency Injection

### Benefits

- Improved testability (inject fakes/mocks)
- Reduced coupling between components
- Easier component replacement
- Clear dependency visibility

### Python DI Pattern

```python
# protocols.py - Define contracts
from typing import Protocol

class FileSystem(Protocol):
    def read(self, path: str) -> bytes: ...
    def write(self, path: str, data: bytes) -> None: ...

# infrastructure/filesystem.py - Production implementation
class LocalFileSystem:
    def read(self, path: str) -> bytes: ...
    def write(self, path: str, data: bytes) -> None: ...

# tests/fakes/filesystem.py - Test implementation
class InMemoryFileSystem:
    def __init__(self):
        self._files: dict[str, bytes] = {}
    def read(self, path: str) -> bytes: ...
    def write(self, path: str, data: bytes) -> None: ...

# application/use_case.py - Depends on Protocol, not implementation
def process_data(fs: FileSystem, input_path: str) -> Result:
    data = fs.read(input_path)
    ...

# cli.py - Wire up at entry point
def main():
    fs = LocalFileSystem()
    result = process_data(fs, "/path/to/input")
```

**Key Principle:** Read configuration and construct dependencies once at the entry point; pass them through to all layers.

---

## 6. Error Handling

### Exception Best Practices

1. **Catch specific exceptions** (never bare `except:`)
2. **Define custom exceptions** for domain-specific errors
3. **Fail fast** with meaningful error messages
4. **Handle at the right level** (where you have context to recover)
5. **Never silently suppress** exceptions
6. **Use `finally`/context managers** for cleanup
7. **Top-level catch-all** at entry point for graceful degradation

### The Result Pattern (for Expected Failures)

Use for predictable failures (validation, business rules); reserve exceptions for truly exceptional conditions.

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")

@dataclass(frozen=True)
class Success(Generic[T]):
    value: T

@dataclass(frozen=True)
class Failure(Generic[E]):
    error: E

Result = Success[T] | Failure[E]

# Usage with pattern matching (Python 3.10+)
def process(result: Result[Company, str]) -> None:
    match result:
        case Success(company):
            print(f"Found: {company.name}")
        case Failure(error):
            print(f"Error: {error}")
```

---

## 7. Logging & Observability

### Structured Logging with `structlog`

**Why structured logging?**

- Key-value pairs (often JSON) are parseable by log aggregation tools
- Context can be bound incrementally
- Better for distributed systems tracing

```python
import structlog

logger = structlog.get_logger(__name__)

# Bind context incrementally
log = logger.bind(request_id="abc123", user_id=42)
log.info("processing_started", step="validation")
log.info("processing_complete", duration_ms=150)
```

**Best Practices:**

- Configure logging once at startup
- Use `__name__` for module-level loggers
- Log to `stdout` in containerised environments
- Use appropriate log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Never log sensitive data** (passwords, PII, API keys)
- Include correlation IDs for request tracing

---

## 8. Resilience Patterns

### Circuit Breaker

Prevents repeated calls to a failing service; allows recovery time.

| State | Behaviour |
|-------|-----------|
| **Closed** | Normal operation; failures counted |
| **Open** | Requests fail immediately; timer running |
| **Half-Open** | Test requests allowed; success closes, failure re-opens |

Libraries: `pybreaker`, `circuitbreaker`

### Retry with Exponential Backoff

Use `tenacity` for robust retry logic:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(TransientError)
)
def fetch_data(url: str) -> bytes:
    ...
```

**Guidelines:**

- Only retry transient/recoverable errors
- Add jitter to prevent thundering herd
- Set reasonable attempt limits
- Log retry attempts

### Rate Limiting

Control request rate to external APIs:

- Libraries: `ratelimit`, `tenacity` (with `wait` strategies)
- Respect `429 Too Many Requests` responses
- Implement at the client level

---

## 9. Testing Strategy

### Test Organisation

```
tests/
├── conftest.py              # Fixtures only
├── fakes/                   # Test doubles
│   ├── __init__.py
│   ├── http.py              # FakeHttpClient
│   ├── filesystem.py        # InMemoryFileSystem
│   └── resilience.py        # FakeRateLimiter, FakeCircuitBreaker
├── test_domain_*.py         # Domain unit tests
├── test_application_*.py    # Use-case tests
├── test_integration_*.py    # Integration tests
└── characterisation/        # Temporary refactor scaffolding
```

### Pytest Best Practices

1. **Descriptive names:** `test_company_search_returns_best_match_by_similarity`
2. **Simple & focused:** One assertion per test where practical
3. **Independent:** No test should depend on another's outcome
4. **Edge cases:** Test boundaries, empty inputs, error conditions
5. **Network isolation:** Block real HTTP in all unit tests

### Fixture Best Practices

- Keep fixtures simple (setup/teardown only)
- Use appropriate scope (`function`, `module`, `session`)
- Share via `conftest.py`
- Use `tmp_path` for temporary files
- Parameterise for comprehensive coverage

### Mocking Best Practices

- Use `unittest.mock` or `pytest-mock`
- **`autospec=True`** to enforce method signatures
- Mock at boundaries (HTTP, DB, FS), not internal code
- Avoid over-mocking; prefer real collaborators where practical

### TDD Cycle

1. **Red:** Write a failing test for desired behaviour
2. **Green:** Write minimum code to pass
3. **Refactor:** Improve design while keeping tests green

---

## 10. Data Pipeline Best Practices

### Core Principles

| Pillar | Description |
|--------|-------------|
| **Generalisability** | Adapt to data changes without reconfiguration |
| **Scalability** | Handle growing data volumes |
| **Maintainability** | Clear, modular, easy to debug |

### ETL Architecture Patterns

```
Extract → Triage → Transform → Load/Publish
```

**Best Practices:**

- **Filter early:** Reduce data volume as early as possible
- **Incremental loads:** Process only new/changed data
- **Efficient formats:** Parquet for columnar, JSON with compression for semi-structured
- **Minimise joins:** Denormalise where appropriate
- **Parallel processing:** Use Dask, PySpark for large datasets
- **Immutable artefacts:** ETL outputs should not be mutated after creation

### Separate ETL from Usage

- **ETL (Transform):** Produces scored/enriched artefacts
- **Usage (Query):** Filters and selects from artefacts; does not mutate

### Monitoring & Observability

- Structured logging at each stage
- Data lineage tracking
- Quality checks (row counts, schema validation)
- Alerting on failures

### Key Libraries

| Purpose | Libraries |
|---------|-----------|
| Data manipulation | pandas, polars, DuckDB |
| Big data | PySpark, Dask |
| Orchestration | Airflow, Prefect, Dagster, Mage |
| Database | SQLAlchemy |
| Streaming | Apache Kafka |
| Validation | Pydantic, pandera |

---

## 11. Code Quality Guidelines

### Size & Complexity Limits

| Element | Limit |
|---------|-------|
| Functions | ≤ 50 lines |
| Classes | ≤ 200 lines |
| Modules | ≤ 400 lines |
| Complexity | Enforce via Ruff rules |

### SOLID Principles in Python

- **S**ingle Responsibility: One reason to change per module/class
- **O**pen/Closed: Open for extension, closed for modification
- **L**iskov Substitution: Subtypes replaceable for base types
- **I**nterface Segregation: Many specific protocols > one general
- **D**ependency Inversion: Depend on abstractions (Protocols), not implementations

### Additional Principles

- **DRY:** Don't Repeat Yourself
- **YAGNI:** You Aren't Gonna Need It
- **EAFP:** Easier to Ask Forgiveness than Permission (Pythonic exception handling)
- **First Question:** Could it be simpler without compromising quality?

---

## 12. Configuration Management

### Best Practices

1. **Read once at entry point** (CLI); pass config through
2. **Use environment variables or TOML** (avoid INI, prefer TOML over YAML)
3. **Validate early** with Pydantic
4. **Fail fast** on invalid config
5. **No env-branching in code** (pass config values, not env names)

---

## 13. Documentation & Naming

### Conventions

- **British spelling** in docs (organisation, colour) unless constrained by external APIs
- **Docstrings:** Google or NumPy style; document "why" not just "what"
- **Module docstrings:** Required for all public modules
- **README:** Keep current with CLI, config, and architecture

### Naming

- **snake_case:** functions, variables, modules
- **PascalCase:** classes
- **SCREAMING_SNAKE_CASE:** constants
- **Descriptive names:** Avoid abbreviations; clarity over brevity

---

## References

- [Packaging Python Projects (PyPA)](https://packaging.python.org/)
- [PEP 8 – Style Guide](https://peps.python.org/pep-0008/)
- [PEP 484 – Type Hints](https://peps.python.org/pep-0484/)
- [PEP 544 – Protocols](https://peps.python.org/pep-0544/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [structlog Documentation](https://www.structlog.org/)
- [Tenacity Documentation](https://tenacity.readthedocs.io/)
- [Architecture Patterns with Python (Percival & Gregory)](https://www.cosmicpython.com/)
