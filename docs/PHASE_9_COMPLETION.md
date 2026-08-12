# Phase 9 — History & Profile: Completion Record

Per AIB v1.0 Vol 17.3 "Phase 9 – History & Profile":
> Persist recommendations, history and profile management.

## Deliverables

- [x] `GET /history` — lists every completed analysis across all of a user's farms, newest first, optional `farm_id` filter, `limit` param (Vol 3 SCR-010: "List/search/filter")
- [x] `GET /history/{id}` — full detail view combining the recommendation, its soil parameters snapshot, weather snapshot, and every fertilizer recommendation tied to it, in one response
- [x] `app/repositories/recommendation_repository.py` extended with `list_for_user` (joins `Farm` for ownership scoping) and `get_with_details` (eager-loads all related tables for the detail view)
- [x] `app/services/history_service.py` — pure assembly/formatting service; **persists nothing new**, since every completed analysis was already correctly persisted by Phases 4/5/7/8
- [x] Profile enhanced: `GET /users/profile` and `PUT /users/profile` now return the full Vol 6.9 profile shape (name/email/phone/created_at **plus** language/theme/notifications from `user_settings`) — previously (Phase 2) these endpoints only returned identity fields, silently dropping the settings half of Vol 6.9's own profile field list

## Why this phase was mostly assembly, not new persistence

By the time Phase 9 started, every piece of data a "history entry" needs was already being correctly written to the database: `soil_parameters` (Phase 4), `weather_snapshots` (Phase 5), `recommendations` (Phase 7), `fertilizer_recommendations` (Phase 8). Vol 2.5 BR-05 ("Every completed analysis is stored in history") was, in effect, already satisfied by the time this phase began — what was missing was a way for a farmer to actually browse that history. This phase is deliberately thin on new write paths and focused on correct, efficient reads (eager-loading relationships in one query rather than N+1 queries per history entry).

## A real bug found and fixed

**Non-deterministic history ordering**: the first version of `test_history_spans_multiple_farms_ordered_newest_first` failed — two recommendations created back-to-back in the same test came back in the wrong order. Root cause: `recommendations.created_at` relied solely on `server_default=func.now()`, and SQLite's `CURRENT_TIMESTAMP` only has 1-second resolution. Two `Recommendation` rows created within the same second (routine for automated tests, and plausible for a farmer running back-to-back analyses) got identical timestamps, making "most recent first" ordering arbitrary rather than deterministic.

Fixed by adding a Python-side `default=lambda: datetime.now(timezone.utc)` alongside the existing `server_default` on the model — this gives microsecond precision regardless of which database is running underneath, while leaving the column's DDL (and therefore the Alembic migration) completely unchanged, since `default` is evaluated by SQLAlchemy before the INSERT rather than being a database-level column constraint. PostgreSQL's own `now()` already has microsecond precision, so this fix is invisible in production and only matters for the SQLite-backed test suite — but it's a correctness fix either way, not a test-only workaround.

## Verification performed in this environment

1. Built two full real analyses (through the actual soil correction, real weather, real trained-model recommendation, real fertilizer pipeline) across two different farms for the same user, and confirmed `GET /history` returns both, correctly ordered newest-first, with the right farm names attached.
2. Verified `farm_id` filtering returns only that farm's entries, and rejects a `farm_id` the user doesn't own with 404 rather than an empty list.
3. Verified `GET /history/{id}` detail view correctly assembles real soil pH/N/P/K values, real weather temperature, and the real fertilizer recommendations generated in Phase 8 — all in one response, matching what was actually persisted.
4. Verified cross-user isolation: a second user sees an empty history list and gets 404 on the first user's history detail, not an error that reveals the entry exists.
5. Verified the profile enhancement didn't break any of Phase 2's existing auth/profile tests (13/13 still passing) while adding settings to the response shape.
6. Ran the full combined suite: 156/156 tests passing (135 backend + 21 ML), zero regressions — including the ordering bug fix being covered by a permanent regression test.

## Explicitly deferred to later phases (not gaps)

- Flutter history screen (SCR-010) consuming this API — Phase 3, now that the API surface for it is complete and stable.
- Pagination beyond a simple limit param (cursor-based paging, total counts) — not specified by the AIB beyond "List/search/filter"; the current limit-capped, farm-filterable list satisfies the stated acceptance criteria. Can be extended without a breaking change if a farmer's history grows large enough to need it.

## AIB Compliance Notes

- History is read-only from the farmer's perspective — there is no delete/edit endpoint for history entries, consistent with Vol 5.8's "soft delete preferred for user-owned records" philosophy (nothing here hard-deletes anything).
- Every history detail response includes the full explanation/reasoning text (Vol 2.5 BR-04: "Every recommendation must include an explanation") — never just the crop name and a number.
