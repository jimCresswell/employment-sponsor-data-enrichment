# Pipeline Run Issues

## 2026-01-31

1. **Stage 2 (Companies House) – Authentication failure**
   - Error: `AuthenticationError: Companies House API returned 401 Unauthorised`
   - Impact: Stage 2 halted immediately; Stage 3 not executed.
   - Measured:
     - `.env` value is a valid UUID format with no whitespace or quotes.
     - The generated `Authorization` header is `Basic base64(API_KEY:)` (decoded ends with a colon).
     - Direct request to `https://api.company-information.service.gov.uk/company/00000006` returns:
       `{"error":"Invalid Authorization","type":"ch:service"}` (HTTP 401).
     - Retried Stage 2 using `HTTPBasicAuth(api_key, "")`; still returns 401 with the same body.
     - Re-run after key update still returns 401 with the same response body.
   - Additional issue: Stage 2 currently prints the raw API key to stdout from
     `src/uk_sponsor_pipeline/stages/stage2_companies_house.py:_basic_auth`,
     which leaks a secret during runs.
   - Likely cause: key is not valid for the public API (revoked, wrong app type, or not activated).
   - Next action: Create/confirm an **API Key** app in Companies House, update `.env`, retry `uv run uk-sponsor stage2`.
