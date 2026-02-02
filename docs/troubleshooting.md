# Troubleshooting

## Companies House Authentication (401/403)

If Transform Enrich fails with `401 Unauthorized` or `Invalid Authorization`:

- Confirm you created a **Companies House API Key** application (not OAuth).
- Set `CH_API_KEY` in `.env` or your environment.
- Transform Enrich uses HTTP Basic Auth with the API key as the username and a blank password.
- If failures persist, regenerate the key and retry.

## Rate Limits, Circuit Breaker, and Resume

Transform Enrich fails fast on authentication, rate‑limit exhaustion, circuit breaker open, or unexpected HTTP errors. This is intentional to protect the API and preserve data quality.

- Fix the underlying issue (wait for limits to reset, reduce batch size, or correct configuration).
- Re‑run with `--resume` to continue from the last checkpoint.
- Check `data/processed/companies_house_resume_report.json` for the exact resume command (or the run subdirectory if `--no-resume` was used).
