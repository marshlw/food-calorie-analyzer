# Task Lifecycle

## Statuses

- `pending` — Task created, waiting for worker.
- `processing` — Worker started processing the task.
- `success` — Task completed with a valid result (including fallback).
- `failure` — Task failed due to unrecoverable error (corrupted image, unhandled exception).

## Rules

- When API receives an analyze request it creates a `Task` row with `status = pending`.
- Celery worker sets `status = processing` when it begins.
- If an ML model returns a valid result (including the safe `fallback`), the worker sets `status = success` and stores `result_json`.
- `fallback` is treated as a valid completion path, not a terminal error state.
- `failure` is only set on final, unrecoverable errors (when no retries remain).
- **File retention:** by default (`DELETE_UPLOAD_AFTER_ANALYSIS=False`) the uploaded image is
  **kept** after successful analysis — it's needed for the "Analysis result" screen and for
  attaching the photo to a feedback submission. Set `DELETE_UPLOAD_AFTER_ANALYSIS=true` to have
  the worker delete the file right after a successful analysis (only files under `UPLOAD_DIR` are
  ever deleted, as a safety check). On final failure (`POST /api/v1/analyze` enqueue error) the
  file is always removed since there is no task result to show for it.

## Retry behavior

- `analyze_image_task` (`app/tasks.py`) is configured with `max_retries=3` and exponential
  `retry_backoff` (capped at 600s); any exception auto-retries.
- On intermediate failures, task raises retry — `status` is not set to `failure` until retries exhausted.
- There is a second task, `retrain_model_task`, used by the (currently non-functional, see
  [code audit](code_audit.md)) model-retraining pipeline — unrelated to the analyze lifecycle
  above.

## Notes

- Result stored in `result_json` must include metadata: `source`, `models_tried`, `processing_time_sec`.
- Use caution removing files: only remove files under configured `UPLOAD_DIR` to avoid accidental deletions.
