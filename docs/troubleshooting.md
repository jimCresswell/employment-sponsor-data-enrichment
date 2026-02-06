# Troubleshooting

## Missing Snapshots (Cache-Only Runs)

If `run-all` fails because clean snapshots are missing:

- Run `refresh-sponsor` and `refresh-companies-house` (default `--only all`), or
  run `--only acquire` then `--only clean` for each command.
- For explicit sources, use `refresh-sponsor --url <csv-url>` and
  `refresh-companies-house --url <zip-url>`.
- Or set `SPONSOR_CLEAN_PATH`, `CH_CLEAN_PATH`, and `CH_TOKEN_INDEX_DIR` to explicit snapshot paths.
- Ensure `SNAPSHOT_ROOT` points to the snapshot tree if you rely on latest-snapshot resolution.

## Companies House Authentication (401/403)

If Transform Enrich fails with `401 Unauthorised` or `Invalid Authorization` (API source only):

- Confirm you created a **Companies House API Key** application (not OAuth).
- Set `CH_API_KEY` in `.env` or your environment.
- Transform Enrich uses HTTP Basic Auth with the API key as the username and a blank password.
- If failures persist, regenerate the key and retry.

## Rate Limits, Circuit Breaker, and Resume

Transform Enrich fails fast on authentication, rate‑limit exhaustion, circuit breaker open, or unexpected HTTP errors (API source only). This is intentional to protect the API and preserve data quality.

- Fix the underlying issue (wait for limits to reset, reduce batch size, or correct configuration).
- Re‑run with `--resume` to continue from the last checkpoint.
- Check `data/processed/companies_house_resume_report.json` for the exact resume command (or the run subdirectory if `--no-resume` was used).

## Lint Failures (TRY/BLE/DTZ/SLF001/T20)

If `uv run lint` fails after enabling the stricter rules:

- **TRY/BLE**: narrow exception handling and use `raise ... from ...` to preserve context.
- **DTZ**: use timezone‑aware datetimes (e.g. `datetime.now(UTC)`) and avoid naive clocks.
- **SLF001**: avoid accessing private members across modules; add a public wrapper instead.
- **T20**: replace non‑CLI `print` calls with structured logging (or move output to the CLI).
