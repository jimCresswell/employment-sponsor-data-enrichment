"""Custom exceptions for the UK Sponsor Pipeline.

These exceptions provide clear error handling and enable testing of error paths.
"""

from __future__ import annotations


class PipelineError(Exception):
    """Base exception for all pipeline errors."""

    pass


class PipelineConfigMissingError(PipelineError):
    """Raised when PipelineConfig is missing at the entry point."""

    def __init__(self) -> None:
        super().__init__(
            "PipelineConfig is required. Load it once at the entry point with "
            "PipelineConfig.from_env() and pass it through."
        )


class DependencyMissingError(PipelineError):
    """Raised when a required dependency is not injected."""

    def __init__(self, dependency: str, *, reason: str | None = None) -> None:
        message = f"{dependency} is required."
        if reason:
            message = f"{message} {reason}"
        super().__init__(message)


class MissingApiKeyError(PipelineError):
    """Raised when CH_API_KEY is required but missing."""

    def __init__(self) -> None:
        super().__init__("Missing CH_API_KEY. Set it in .env or environment variables.")


class MissingSnapshotPathError(PipelineError):
    """Raised when a required snapshot path is missing in configuration."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"{field_name} is required when CH_SOURCE_TYPE is 'file'.")


class InvalidSourceTypeError(PipelineError):
    """Raised when CH_SOURCE_TYPE is invalid."""

    def __init__(self) -> None:
        super().__init__("CH_SOURCE_TYPE must be 'api' or 'file'.")


class MissingRawCsvError(PipelineError):
    """Raised when the raw sponsor register CSV cannot be found."""

    def __init__(self, raw_dir: str) -> None:
        super().__init__(f"No raw CSV found in {raw_dir}. Run `uk-sponsor refresh-sponsor` first.")


class CsvLinkNotFoundError(PipelineError):
    """Raised when no CSV link is found on the GOV.UK sponsor register page."""

    def __init__(self) -> None:
        super().__init__(
            "Could not find a CSV link on the GOV.UK sponsor register page.\n"
            "The page structure may have changed. Use --url to specify the direct CSV URL."
        )


class CsvLinkAmbiguousError(PipelineError):
    """Raised when multiple candidate CSV links match the best pattern."""

    def __init__(self, candidates: list[str]) -> None:
        sample = ", ".join(candidates[:5])
        super().__init__(
            "Multiple candidate CSV links matched the best pattern on the GOV.UK "
            "sponsor register page. Use --url to specify the correct CSV. "
            f"Candidates: {sample}"
        )


class CsvSchemaDecodeError(PipelineError):
    """Raised when CSV headers cannot be decoded."""

    def __init__(self) -> None:
        super().__init__("Could not validate CSV schema headers.")


class CsvSchemaMissingColumnsError(PipelineError):
    """Raised when required CSV schema columns are missing."""

    def __init__(self, missing: list[str]) -> None:
        missing_list = ", ".join(sorted(missing))
        super().__init__(f"CSV schema validation failed. Missing columns: {missing_list}.")


class SnapshotAlreadyExistsError(PipelineError):
    """Raised when a snapshot directory already exists for a dataset/date."""

    def __init__(self, dataset: str, snapshot_date: str) -> None:
        super().__init__(f"Snapshot already exists for dataset '{dataset}' on {snapshot_date}.")


class SnapshotNotFoundError(PipelineError):
    """Raised when no snapshots exist for a dataset."""

    def __init__(self, dataset: str, snapshot_root: str) -> None:
        super().__init__(
            f"No snapshots found for dataset '{dataset}' under {snapshot_root}. "
            "Run the refresh command to generate one."
        )


class SnapshotArtefactMissingError(PipelineError):
    """Raised when a required snapshot artefact is missing."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Required snapshot artefact missing: {path}.")


class SnapshotTimestampError(PipelineError):
    """Raised when snapshot timestamps are invalid or not timezone-aware."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"{field_name} must be timezone-aware.")


class SchemaColumnsMissingError(PipelineError):
    """Raised when a DataFrame is missing required columns."""

    def __init__(self, step_name: str, missing: list[str]) -> None:
        super().__init__(f"{step_name}: Missing required columns: {sorted(missing)}")


class InvalidBatchConfigurationError(PipelineError):
    """Raised when batch parameters are invalid."""

    def __init__(self, field_name: str, value: int) -> None:
        super().__init__(f"{field_name} must be >= 1 (got {value}).")


class InvalidMatchScoreError(PipelineError):
    """Raised when match_score values cannot be parsed as numeric."""

    def __init__(self, sample: str) -> None:
        super().__init__(f"Transform score: match_score must be numeric. Invalid values: {sample}")


class LocationAliasesNotFoundError(PipelineError):
    """Raised when the location aliases file is missing."""

    def __init__(self) -> None:
        super().__init__(
            "Location aliases file not found. Create data/reference/location_aliases.json "
            "or set LOCATION_ALIASES_PATH to a valid file."
        )


class CompaniesHouseSearchError(PipelineError):
    """Raised when Companies House search fails for a query."""

    def __init__(self, query: str, message: str) -> None:
        super().__init__(f"Companies House search failed for query '{query}': {message}")


class CompaniesHouseProfileError(PipelineError):
    """Raised when Companies House profile fetch fails."""

    def __init__(self, company_number: str, message: str) -> None:
        super().__init__(f"Companies House profile fetch failed for {company_number}: {message}")


class CompaniesHouseUriMismatchError(PipelineError):
    """Raised when Companies House URI does not match the company number."""

    def __init__(self, company_number: str, uri: str) -> None:
        super().__init__(
            f"Companies House URI mismatch for company number '{company_number}': '{uri}'."
        )


class CompaniesHouseZipMissingCsvError(PipelineError):
    """Raised when no CSV file is found in a Companies House zip archive."""

    def __init__(self) -> None:
        super().__init__("No CSV file found in Companies House zip archive.")


class CompaniesHouseCsvEmptyError(PipelineError):
    """Raised when the Companies House CSV contains no rows."""

    def __init__(self) -> None:
        super().__init__("Companies House CSV is empty.")


class CompaniesHouseFileProfileMissingError(PipelineError):
    """Raised when a file-backed profile is missing."""

    def __init__(self, company_number: str) -> None:
        super().__init__(
            "Companies House file source is missing a profile for company number "
            f"'{company_number}'."
        )


class JsonObjectExpectedError(PipelineError):
    """Raised when a payload is not a JSON object."""

    def __init__(self, source: str) -> None:
        super().__init__(f"{source} must be a JSON object.")

    @classmethod
    def for_json_file(cls) -> JsonObjectExpectedError:
        return cls("JSON file")

    @classmethod
    def for_cache_data(cls) -> JsonObjectExpectedError:
        return cls("Cache data")

    @classmethod
    def for_companies_house_response(cls) -> JsonObjectExpectedError:
        return cls("Companies House response")


class GeoFilterRegionError(PipelineError):
    """Raised when GEO_FILTER_REGIONS contains more than one region."""

    def __init__(self) -> None:
        super().__init__("GEO_FILTER_REGIONS must contain at most one region.")


class AuthenticationError(PipelineError):
    """Raised when API authentication fails (401 Unauthorised).

    This is a fatal error - the pipeline should stop immediately.
    """

    def __init__(self, message: str = "API authentication failed") -> None:
        super().__init__(
            f"{message}\n"
            "Please check your CH_API_KEY in .env is correct and not expired.\n"
            "Get a new key at: https://developer.company-information.service.gov.uk/"
        )

    @classmethod
    def for_status_401(cls, details: str) -> AuthenticationError:
        return cls(f"Companies House API returned 401 Unauthorised ({details})")

    @classmethod
    def for_status_403(cls, details: str) -> AuthenticationError:
        return cls(
            "Companies House API returned 403 Forbidden. "
            "Your IP may be temporarily blocked due to excessive requests. "
            f"({details})"
        )

    @classmethod
    def for_http_error(cls, error: Exception) -> AuthenticationError:
        return cls(f"HTTP error indicates auth failure: {error}")

    @classmethod
    def with_detail(cls, detail: str) -> AuthenticationError:
        return cls(f"API authentication failed: {detail}")

    @classmethod
    def invalid_key(cls) -> AuthenticationError:
        return cls.with_detail("invalid key")


class RateLimitError(PipelineError):
    """Raised when API rate limit is exceeded (429 Too Many Requests).

    The pipeline should back off and retry.
    """

    def __init__(self, retry_after: int = 60) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class CircuitBreakerOpen(PipelineError):
    """Raised when circuit breaker trips due to repeated failures.

    The pipeline should stop to prevent further damage.
    """

    def __init__(self, failure_count: int, threshold: int) -> None:
        self.failure_count = failure_count
        self.threshold = threshold
        super().__init__(
            f"Circuit breaker tripped: {failure_count} consecutive failures "
            f"(threshold: {threshold}). Stopping to prevent API ban."
        )
