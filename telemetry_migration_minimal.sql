-- Adds the non-sensitive fields used by the minimal telemetry payload.
-- Existing query, URL, resource, and error-message columns may remain in the
-- table for compatibility; the server no longer sends values to them.

alter table public.telemetry_events
  add column if not exists error_code text,
  add column if not exists server_version text,
  add column if not exists dataset_ids text[];
