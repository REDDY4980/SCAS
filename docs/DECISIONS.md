# SCAS — B.3 Decisions and Handoff Defaults

The original Claude kickoff package asks for six decisions. The following are the recommended working defaults for the AI developer. Change only if the project owner decides otherwise.

1. Platform: ANDROID + iOS
   Reason: Flutter already provides the shared codebase. Android remains the primary demonstration target.

2. Public placeholder dataset: YES
   Use Requirement 1 as the initial XGBoost training dataset.
   Label it as a public starter dataset. Keep the pipeline replaceable.

3. Weather fallback: OPENWEATHERMAP
   Primary remains Open-Meteo (no key). OpenWeatherMap is the explicit fallback.
   API key must be supplied through environment variables only.

4. Deployment target: LOCAL DOCKER FIRST
   Cloud deployment is deferred until the application is stable.
   Do not buy a domain or cloud server for the initial development phases.

5. Flutter state management: RIVERPOD
   This matches the AIB v1.0 preference.

6. Git workflow: REVIEW-THEN-COMMIT
   AI developer should make phase-complete changes, run tests, show the diff/status, and provide a concise completion report. Do not push to a remote repository unless repository access is explicitly supplied.

## Credentials still required later

- OpenWeatherMap API key: required before Phase 5.
- Production PostgreSQL credentials: only for remote deployment.
- Cloud provider account: only for Phase 10 cloud deployment.
- Domain/DNS: only for production HTTPS.
- Docker Hub/GHCR/ECR: optional unless remote image publishing is needed.
- GitHub repo URL/push access: recommended, but not mandatory.
- Google Play Console: not required for v1.0 development; only needed for actual store publication.

## Security

Never put real API keys, passwords, JWT secrets, cloud credentials, or private GitHub tokens into the ZIP.
The AI developer must use environment variables / secret stores.
