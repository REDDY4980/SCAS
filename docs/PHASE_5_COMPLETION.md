# Phase 5 — Climate Intelligence Engine: Completion Record

Per AIB v1.0 Vol 17.3 "Phase 5 – Climate Engine":
> Integrate weather services, caching and feature generation.

## Deliverables

- [x] `app/weather/client.py` — `WeatherProviderClient` interface, `OpenMeteoClient` (primary, no key), `OpenWeatherMapClient` (fallback, Vol 8.3), `fetch_with_retry` (Vol 8.11 "retry once on timeout")
- [x] `app/weather/normalizer.py` — maps both providers' raw responses to a common `NormalizedWeather` DTO; derives `season` using the Indian Meteorological Department convention (documented assumption — see below)
- [x] `app/weather/cache.py` — 30-minute TTL freshness check (Vol 8.10), backed by the `weather_snapshots` table itself rather than a second cache store
- [x] `app/repositories/weather_repository.py` — CRUD + latest-snapshot lookup
- [x] `app/services/weather_service.py` — full Vol 8.4 pipeline: coordinate validation → cache check → primary fetch (with retry) → fallback → stale-cache-on-total-failure → normalize → persist
- [x] `GET /weather/current`, `POST /weather/refresh`, `GET /weather/history/{farm_id}` — all three Vol 8.7 endpoints
- [x] Farm ownership enforced on every endpoint (Vol 6.10, consistent with Phases 2/4)

## Design decisions worth flagging

- **Rainfall source**: Open-Meteo's `current.precipitation` is a 15-minute instantaneous reading (often 0 even during an active rainy day between showers). I use `daily.rain_sum` (today's accumulated rainfall) instead, since that's the more agronomically meaningful signal and closer in spirit to the "Rainfall" feature Vol 9.6 rates as "Very High" importance. Falls back to instant precipitation only if no daily block is present.
- **Season derivation**: not specified numerically anywhere in Vol 8, so I implemented the Indian Meteorological Department's four-season convention (Winter Dec-Feb, Summer Mar-May, Monsoon Jun-Sep, Post-Monsoon Oct-Nov) — appropriate given SCAS is explicitly India-focused (Vol 1.1, and the fertilizer/agronomic knowledge bases are India-specific). This is a judgment call, documented in code, and trivially swappable if the domain expert wants a different convention.
- **Cache = the persistence table**: rather than a separate Redis/in-memory cache layer, "cache" is just "is the most recent `weather_snapshots` row for this farm still within the TTL." One source of truth, no cache-invalidation-vs-database-drift class of bugs.

## Verification performed in this environment

1. **Pulled the actual Open-Meteo API documentation** (not from training-data memory) via web search/fetch to get the real endpoint contract, parameter names, and JSON response shape — this sandbox's network egress doesn't allow live calls to `api.open-meteo.com`, so I couldn't hit it directly, but the client and normalizer are built against the real documented schema, not a guess.
2. Unit-tested the normalizer against a realistic Open-Meteo payload (exact shape from the docs, plausible Karnataka-coordinate values) — confirmed correct field mapping, rainfall source preference, season derivation, and graceful handling of a missing `current` block.
3. Unit-tested `OpenMeteoClient` by monkeypatching `httpx.get` — confirmed timeout wrapping, provider-error wrapping, and successful-response parsing, all without real network access.
4. Unit-tested `fetch_with_retry` — confirmed it retries exactly once (not unlimited) and propagates the second failure.
5. Ran full integration tests through the actual FastAPI endpoints with **injectable fake `WeatherProviderClient` implementations** (dependency-override pattern, same as Phase 4's OCR engine) — verified: first call fetches+persists, second call within TTL hits cache without a second provider call, `/refresh` bypasses cache, primary-fails→fallback-succeeds, both-fail→stale-cache-served, both-fail+no-cache→503, farm-without-coordinates→400, cross-user ownership→404, history endpoint.
6. **Found and fixed a real test-fixture bug** (not a service bug) during this process: a hardcoded timestamp in the fake weather payload made the "fresh cache" test fail depending on how much wall-clock time had passed since the fixture was written — a classic time-bomb test. Fixed by generating the fixture's timestamp from real "now" at test-run time.
7. Fixed a flaky exact-boundary timing test (`is_fresh` at precisely 1800s) that could fail on slow CI runs due to the few milliseconds between constructing the timestamp and calling the function — replaced with just-inside/just-outside assertions.
8. Full suite: **87/87 tests passing** (35 new this phase: 24 unit + 10 integration + 1 cache fix).

**Not verified in this environment**: neither `OpenMeteoClient` nor `OpenWeatherMapClient` has made a real HTTP call to a live weather API — the sandbox's network egress doesn't permit it. The first real API call (a farm with real coordinates hitting the actual `/weather/current` endpoint against live Open-Meteo) should be the first thing checked after deployment. `OPENWEATHERMAP_API_KEY` also still needs to be supplied before the fallback path can do anything beyond raise a clear "not configured" error — this was flagged back in `DECISIONS.md` as "required before Phase 5" and remains an open input.

## Explicitly deferred to later phases (not gaps)

- Feature fusion of `soil_parameters` + `weather_snapshots` into the ML feature vector — Phase 6 (this phase's output, `WeatherSnapshotOut`, is exactly the Vol 9.7 "Validated Climate JSON" input the ML pipeline expects).
- Climate suitability scoring in the agronomic rule engine — Phase 7.

## AIB Compliance Notes

- Flutter never calls a weather API directly — everything routes through this FastAPI service (Vol 8.14).
- All values normalized before persistence; raw provider payloads are never stored (Vol 8.14).
- Weather retrieval failure never surfaces a raw exception to the client — it's either a clear 400 (bad coordinates), a stale-cache 200 (provider down but cache exists), or a clear 503 (provider down, no cache) (Vol 8.11, Vol 12.11).
