# Standalone Review: UK Sponsor Tech Hiring Pipeline (Code-Verified)

**Date:** 2026-02-02
**Scope:** Architecture, data pipeline correctness, security/reliability, testing, documentation alignment.
**Method:** Evidence-based review cross-checking prior reports with current code. All findings include file/line evidence and are re-framed where earlier reports overstated or understated issues.

---

## 1) Findings (ordered by severity)

### High

#### 1. Systemic Application → Infrastructure coupling via defaults
**Evidence:** Application modules import concrete infrastructure and default to `LocalFileSystem()` instead of requiring injection.
- `src/uk_sponsor_pipeline/application/extract.py:14,129`
- `src/uk_sponsor_pipeline/application/transform_register.py:20,113`
- `src/uk_sponsor_pipeline/application/transform_enrich.py:37,217`
- `src/uk_sponsor_pipeline/application/transform_score.py:17,52`
- `src/uk_sponsor_pipeline/application/usage.py:24,76`
- `src/uk_sponsor_pipeline/application/pipeline.py:17,73`

**Context check:** The CLI does not inject a filesystem into these calls, so the default concrete dependency is always exercised in normal usage.
- `src/uk_sponsor_pipeline/cli.py:153-163`
- `src/uk_sponsor_pipeline/cli.py:188-193`
- `src/uk_sponsor_pipeline/cli.py:243-254`
- `src/uk_sponsor_pipeline/cli.py:296-305`

**Impact:** Violates the intended dependency direction (application should depend on protocols, not concrete infrastructure). This makes the application layer harder to reuse in non-local environments and weakens boundary clarity. The issue is systemic, not isolated to `pipeline.py`.

**Frame:** This is an architectural consistency issue against the stated “clean breaks” principle, not a functional bug.

---

### Medium

#### 2. Type coercion masks upstream data corruption in scoring
**Evidence:** `transform_score` coerces `match_score` to numeric with `errors="coerce"`, silently converting non-numeric values to `0.0`.
- `src/uk_sponsor_pipeline/application/transform_score.py:65-66`

**Impact:** If upstream data becomes malformed, the pipeline does not fail fast and instead produces incorrect ranking. This undermines artefact integrity and auditability. The existing contract enforcement validates columns only, not types, so this is a real silent-failure risk.

**Frame:** Not a contract violation per current column-only validation, but a data integrity risk that conflicts with fail-fast directives.

---

#### 3. Broad exception classification contaminates circuit breaker state
**Evidence:** `CachedHttpClient.get_json` catches `Exception`, records a circuit breaker failure, and re-raises.
- `src/uk_sponsor_pipeline/infrastructure/io/http.py:185-197`

**Impact:** Programming errors (e.g., `TypeError`) inside the try block are classified as network failures. This does not swallow errors but contaminates resilience state and makes failures look like infra issues. Debugging and reliability signals are distorted.

**Frame:** A reliability/observability concern, not a correctness bug.

---

#### 4. HTML scraping is structurally brittle
**Evidence:** Extract depends on GOV.UK HTML structure and link heuristics with regex.
- `src/uk_sponsor_pipeline/application/extract.py:32-88`

**Impact:** Changes to GOV.UK page structure or link text can break extraction or pick the wrong CSV. There is schema validation of headers, but no stronger content validation (e.g., approximate row count or currency). This is a known fragility.

**Frame:** A known risk with an acceptable mitigation (`--url` override), but still operationally brittle.

---

### Low

#### 5. Pipeline config contains secrets without redaction safeguards
**Evidence:** `PipelineConfig` contains `ch_api_key` and uses default dataclass repr.
- `src/uk_sponsor_pipeline/config.py:12-35`

**Context check:** No evidence of logging or printing `PipelineConfig` objects was found in the codebase during this review (logging calls are present, but none format config objects).
- `src/uk_sponsor_pipeline/application/extract.py:139-190`
- `src/uk_sponsor_pipeline/application/transform_register.py:130-204`
- `src/uk_sponsor_pipeline/application/transform_enrich.py:226-510`
- `src/uk_sponsor_pipeline/application/transform_score.py:68-94`
- `src/uk_sponsor_pipeline/application/usage.py:106-120`

**Impact:** If a config instance is logged or printed, the key would be exposed. With no current evidence of config logging, this remains a conditional risk rather than a confirmed leak.

**Frame:** “Potential” security risk; severity depends on logging practices.

---

## 2) Corrections to earlier report conclusions

- **Python 3.14 requirement is intentional.** Prior report flagged it as invalid. Directives explicitly require Python 3.14+ (`.agent/directives/AGENT.md`). This is a deliberate policy choice, not a defect.
- **Application–Infrastructure coupling is broader than previously stated.** Multiple application modules import `LocalFileSystem`, not just `pipeline.py` or `transform_enrich.py`.
- **`match_score` coercion is a silent-failure risk, not a strict contract violation.** Contract enforcement currently validates column presence only, not types. The risk remains but should be framed accurately.

---

## 3) Architecture and boundary alignment (actual vs intended)

**Intended:** CLI → Application → Protocols ← Infrastructure; domain is pure.

**Actual:** Application imports infrastructure defaults, violating dependency direction across all application steps. Domain remains pure and isolated.

**Import-linter constraints:**
- Infrastructure is forbidden from importing `domain` or `types` (`pyproject.toml:115-119`).
- This necessitates shared contracts in `protocols.py` and `types.py` at the package root, which is consistent with a “shared kernel” compromise.

---

## 4) Data pipeline integrity and contracts

**Strengths:**
- Every pipeline stage validates column sets via `schemas.py` and `validate_columns`.
- IO boundaries are parsed and validated via `infrastructure/io/validation.py` before use.

**Weaknesses:**
- Type enforcement inside CSV artefacts is weak (column presence only). `transform_score` compensates by coercing types, risking silent corruption.
- Extract relies on HTML scraping without deeper content validation.

---

## 5) Documentation alignment

- README and ADRs generally match the split between scoring and usage-shortlist, and the pipeline order.
- No evidence of doc/code divergence found during this review, but review did not audit every ADR vs code line-by-line.

## 6) Testing and maintainability notes

- **Fail-fast coverage gaps:** There are strong happy-path integration tests, but limited negative integration coverage to prove the pipeline halts on malformed CSVs or corrupted artefacts. This matters given the explicit fail-fast directives.
- **Transform-enrich testability:** `transform_enrich` combines batching, I/O orchestration, and enrichment logic in one loop, which makes unit testing the enrichment strategy in isolation harder and can lead to broader mocks in tests.

---

## 7) Open questions / assumptions

1. Should application modules **require** filesystem injection (to enforce architectural boundaries), or is defaulting to `LocalFileSystem` an explicit pragmatic exception?
2. Is it acceptable to treat `match_score` as “best-effort” input, or must it be strictly validated to fail fast on corruption?
3. Should the circuit breaker classify *only* HTTP/request failures as failures, or is it intended to record any runtime exception during requests?
4. Is there any logging of `PipelineConfig` objects that would elevate the API key risk from conditional to real?

---

## 8) Top recommended follow-ups (non-exhaustive, ordered)

1. **Architectural clean break:** remove application-level defaults to concrete infrastructure; instantiate in CLI composition root.
2. **Add import-linter guard:** forbid `uk_sponsor_pipeline.application` from importing `uk_sponsor_pipeline.infrastructure` to enforce the clean break.
2. **Fail-fast enforcement:** replace `errors="coerce"` in `transform_score` with strict numeric validation and explicit failure.
3. **Resilience signal accuracy:** narrow the `except Exception` scope in the HTTP client to avoid misclassifying programming errors.
4. **Extraction robustness:** add stronger content validation or stronger link-selection heuristics beyond header validation.

---

## 9) Overall assessment

The system is architecturally disciplined with clear layering intent, strong IO validation patterns, and good operational structure. The primary issues are **boundary purity (application ↔ infrastructure)** and **silent data corruption risk in scoring**, both of which conflict with stated “clean break” and “fail fast” principles. Most other concerns are conditional or operational rather than structural defects.
