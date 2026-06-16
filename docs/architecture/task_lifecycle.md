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
- Image files are only removed after successful completion or after final failure when retries are exhausted.
- `failure` is only set on final, unrecoverable errors (when no retries remain).
- Worker deletes the uploaded image file after successful processing or after final failure. If retries remain, file is kept so subsequent retries can re-process it.

## Retry behavior

- Celery task configured with a limited number of retries (e.g., 3).
- On intermediate failures, task raises retry — `status` is not set to `failure` until retries exhausted.

## Notes

- Result stored in `result_json` must include metadata: `source`, `models_tried`, `processing_time_sec`.
- Use caution removing files: only remove files under configured `UPLOAD_DIR` to avoid accidental deletions.
