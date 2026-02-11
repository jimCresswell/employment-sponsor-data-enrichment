> Archived Plan Notice (2026-02-11): this file is historical reference only.
> Do not execute this plan directly.
> Active execution queue: `.agent/plans/linear-delivery-plan.md`.
> Durable contracts and operational guidance live in `README.md`, `docs/`, and `docs/architectural-decision-records/`.

# Stage 2 Batching + Incremental Output + Resume (Implementation Plan)

## Goal
Make Stage 2 resilient for long runs by batching, writing incremental outputs, and resuming reliably.

## Plan
1. **Add append‑write support**
   - Extend `FileSystem` with `append_csv`.
   - Implement in `LocalFileSystem` and `InMemoryFileSystem`.
2. **Batch processing**
   - Add `ch_batch_size` to config (env: `CH_BATCH_SIZE`).
   - Process organisations in batches and flush outputs each batch.
3. **Incremental outputs**
   - Append to `stage2_enriched_companies_house.csv`, `stage2_unmatched.csv`, `stage2_candidates_top3.csv`.
   - Validate and coerce columns before each append.
4. **Checkpoint + resume**
   - Maintain `stage2_checkpoint.csv` with processed org names.
   - On resume, build processed set from checkpoint + existing outputs.
5. **Finalisation**
   - After completion, read outputs, de‑duplicate, sort, and rewrite clean files.
6. **Tests**
   - Unit test `append_csv` (local + in‑memory).
   - Stage 2 resume test using in‑memory FS and batch size = 1.
7. **Docs**
   - Update `.env.example` and README config section with `CH_BATCH_SIZE`.

## Success Criteria
- Stage 2 can be interrupted and resumed without reprocessing completed orgs.
- Outputs are written incrementally and final files are clean, sorted, and de‑duplicated.
