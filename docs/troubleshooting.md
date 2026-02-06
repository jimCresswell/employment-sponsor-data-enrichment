# Troubleshooting

## Missing Snapshots (Cache-Only Runs)

If `run-all` fails because clean snapshots are missing:

- Run `refresh-sponsor` and `refresh-companies-house` (default `--only all`), or
  run `--only acquire` then `--only clean` for each command.
- For explicit sources, use `refresh-sponsor --url <csv-url>` and
  `refresh-companies-house --url <zip-url>`.
- Or set `SPONSOR_CLEAN_PATH`, `CH_CLEAN_PATH`, and `CH_TOKEN_INDEX_DIR` to explicit snapshot paths.
- Ensure `SNAPSHOT_ROOT` points to the snapshot tree if you rely on latest-snapshot resolution.

## Unsupported Runtime Source Mode

If `transform-enrich` or `run-all` fails with:

```text
<command> supports CH_SOURCE_TYPE=file only (got '<value>').
```

- Set `CH_SOURCE_TYPE=file` in `.env`.
- Run `refresh-sponsor` and `refresh-companies-house` to ensure clean snapshots exist.
- Re-run the command.

## Archived API Runtime Reference

Runtime CLI commands are file-only. Archived API runtime notes are captured in
`docs/archived-api-runtime-mode.md`.

## Lint Failures (TRY/BLE/DTZ/SLF001/T20)

If `uv run lint` fails after enabling the stricter rules:

- **TRY/BLE**: narrow exception handling and use `raise ... from ...` to preserve context.
- **DTZ**: use timezone‑aware datetimes (e.g. `datetime.now(UTC)`) and avoid naive clocks.
- **SLF001**: avoid accessing private members across modules; add a public wrapper instead.
- **T20**: replace non‑CLI `print` calls with structured logging (or move output to the CLI).
