# Hardcoded Configuration Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make deployment, runtime, queue, storage, scoring, frontend, and hardcoding-audit configuration authoritative and environment-safe without breaking public API contracts or legacy stored-file reads.

**Architecture:** Centralize backend runtime values in `Settings`, hydrate domain scoring from the typed policy snapshot, and keep production Compose free of insecure local defaults. Frontend build/runtime configuration remains frontend-owned, while storage repositories provide read-only compatibility for the legacy nested data location and write only to canonical paths.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic Settings, Redis/RQ, PostgreSQL, Docker Compose, Expo/React Native, TypeScript/Node static tests.

**Spec:** `docs/superpowers/specs/2026-08-20-hardcoded-configuration-remediation-design.md`

## Global Constraints

- Preserve public HTTP routes and successful response fields.
- Keep MSSQL strictly read-only.
- Keep CV processing single-slot; do not implement a new concurrency subsystem.
- Do not delete or move existing uploads or results.
- Keep local insecure defaults only in `docker-compose.local.yml` and `.env.example`.
- Keep stable protocol constants, HTTP status codes, MIME types, schema identifiers, and emergency-policy defaults as code constants.
- Append every completed change to `workstats.md`; never edit prior entries.
- Do not run tests, linters, builds, Docker commands, or release gates without explicit user authorization.

---

## File map

- `backend/app/core/config.py`: canonical runtime settings, path derivation, production validation, version compatibility property.
- `backend/app/core/cache.py`, `backend/app/core/background_tasks.py`, `backend/start_scheduler.py`, `backend/app/services/processing_queue.py`: settings-backed Redis client behavior.
- `backend/app/services/shadow_validation_service.py`: configured queue name and shadow-job retry policy.
- `backend/app/services/upload_service.py`, `backend/app/repositories/result.py`: canonical writes and legacy nested-path reads.
- `backend/app/core/rule_config_manager.py`, `backend/app/schemas/scoring_config.py`: zero-skills score-cap propagation.
- `docker-compose.yml`, `docker-compose.local.yml`, `docker-compose.profile-*.yml`: secure production/local separation and valid resource profiles.
- `frontend/src/constants/config.ts`, `frontend/src/hooks/useCvUpload.ts`, `frontend/src/hooks/useCvQueueUploads.ts`: production API URL validation and bounded polling.
- `backend/scripts/quality/hardcoding_audit.py`, `hardcoding-baseline.json`: exact baseline identities.
- `.vscode/settings.json`, `run.md`, `README.md`, `backend/.env.example`: sanitized and accurate operational configuration.

---

### Task 1: Canonical backend settings, security validation, paths, and metadata

**Files:**
- Modify: `backend/tests/unit/core/test_runtime_and_security_config.py`
- Modify: `backend/tests/unit/core/test_phase3_absolute_data_root.py`
- Modify: `backend/tests/unit/core/test_phase3_db_credentials_governance.py`
- Modify: `backend/tests/unit/core/test_version_and_repo_hygiene.py`
- Modify: `backend/tests/integration/test_phase4_acceptance_gate.py`
- Modify: `backend/app/core/config.py`

**Interfaces:**
- Produces: `Settings.VERSION: str` compatibility property returning `APP_VERSION`.
- Produces: `Settings.LEGACY_UPLOADS_DIR: Path` and `Settings.LEGACY_RESULTS_DIR: Path` read-only compatibility paths.
- Produces: settings `REDIS_SOCKET_TIMEOUT_SECONDS`, `REDIS_CONNECT_TIMEOUT_SECONDS`, `REDIS_HEALTH_CHECK_INTERVAL_SECONDS`, `REDIS_AVAILABILITY_PROBE_TIMEOUT_SECONDS`, `SHADOW_VALIDATION_MAX_RETRIES`, `SHADOW_VALIDATION_RETRY_INTERVAL_SECONDS`, and `SHADOW_VALIDATION_JOB_TIMEOUT_SECONDS`.
- Preserves: existing environment-variable names except removed no-op `MAX_CONCURRENT_LLM_WORKERS` and backend-only frontend polling fields.

- [ ] **Step 1: Write failing settings tests**

Add assertions equivalent to:

```python
def test_explicit_data_root_derives_canonical_paths(tmp_path: Path) -> None:
    configured = Settings(APP_DATA_ROOT=tmp_path)
    assert configured.UPLOADS_DIR == tmp_path.resolve()
    assert configured.RESULTS_DIR == (tmp_path / "results").resolve()
    assert configured.LOCK_DIR == (tmp_path / ".locks").resolve()
    assert configured.TRAINING_DATA_DIR == (tmp_path / "training_data").resolve()
    assert configured.LEGACY_UPLOADS_DIR == (tmp_path / "uploads").resolve()
    assert configured.LEGACY_RESULTS_DIR == (tmp_path / "uploads" / "results").resolve()


def test_production_requires_auth_keys_and_origins() -> None:
    with pytest.raises(ValueError, match="API key"):
        Settings(
            APP_ENVIRONMENT="production",
            AUTH_ENABLED=True,
            AUTH_SESSION_SIGNING_KEY="a-secure-signing-key-with-32-characters",
            RECRUITER_API_KEYS=[],
            ADMINISTRATOR_API_KEYS=[],
            ALLOWED_ORIGINS=["https://recruiting.example.com"],
            POSTGRES_APP_URL="postgresql://app:secure@db.internal/app",
            POSTGRES_SSL_MODE="require",
            REDIS_URL="rediss://redis.internal/0",
            MSSQL_READ_ONLY_URL="mssql+pyodbc://reader:secure@sql.internal/db",
            GIT_SHA="abc1234",
        )


def test_version_alias_and_unknown_development_sha() -> None:
    configured = Settings(APP_VERSION="4.2.1", GIT_SHA="")
    assert configured.VERSION == "4.2.1"
    assert configured.GIT_SHA == "unknown"
```

Update stale tests that assert `c6eb7f2` to assert injected values or `unknown` in development.

- [ ] **Step 2: Run the targeted tests and confirm they fail**

Run only after execution authorization:

```bash
cd backend
uv run pytest tests/unit/core/test_runtime_and_security_config.py tests/unit/core/test_phase3_absolute_data_root.py tests/unit/core/test_phase3_db_credentials_governance.py tests/unit/core/test_version_and_repo_hygiene.py tests/integration/test_phase4_acceptance_gate.py -q
```

Expected: failures for canonical path derivation, missing production key/origin validation, and stale version expectations.

- [ ] **Step 3: Implement canonical settings**

Use nullable dependent paths followed by one after-validator:

```python
APP_VERSION: str = "3.0.0"
GIT_SHA: str = ""
APP_DATA_ROOT: Path = Field(default_factory=lambda: (Path(__file__).resolve().parents[2] / "uploads").resolve())
UPLOADS_DIR: Path | None = None
RESULTS_DIR: Path | None = None
LOCK_DIR: Path | None = None
TRAINING_DATA_DIR: Path | None = None

@property
def VERSION(self) -> str:
    return self.APP_VERSION

@property
def LEGACY_UPLOADS_DIR(self) -> Path:
    return (self.APP_DATA_ROOT / "uploads").resolve()

@property
def LEGACY_RESULTS_DIR(self) -> Path:
    return (self.LEGACY_UPLOADS_DIR / "results").resolve()
```

At the start of `validate_production_requirements`, normalize `GIT_SHA` and derive paths:

```python
self.GIT_SHA = self.GIT_SHA.strip() or "unknown"
self.APP_DATA_ROOT = self.APP_DATA_ROOT.resolve()
self.UPLOADS_DIR = (self.UPLOADS_DIR or self.APP_DATA_ROOT).resolve()
self.RESULTS_DIR = (self.RESULTS_DIR or self.UPLOADS_DIR / "results").resolve()
self.LOCK_DIR = (self.LOCK_DIR or self.APP_DATA_ROOT / ".locks").resolve()
self.TRAINING_DATA_DIR = (self.TRAINING_DATA_DIR or self.APP_DATA_ROOT / "training_data").resolve()
```

Add production checks for nonempty trusted origins, at least one API key when auth is enabled, non-default database credentials independent of host, and non-`unknown` Git SHA. Remove duplicate `TRAINING_DATA_DIR`, `VERSION`, `MAX_CONCURRENT_LLM_WORKERS`, `FRONTEND_POLL_INTERVAL_MS`, and `FRONTEND_RETRY_AFTER_MS` fields. Remove the literal-only `RQ_QUEUE_NAME == "cv-processing"` validator while preserving `CV_PROCESSING_CONCURRENCY == 1`.

- [ ] **Step 4: Run the targeted tests and confirm they pass**

Run the Step 2 command after authorization. Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/app/core/config.py backend/tests/unit/core/test_runtime_and_security_config.py backend/tests/unit/core/test_phase3_absolute_data_root.py backend/tests/unit/core/test_phase3_db_credentials_governance.py backend/tests/unit/core/test_version_and_repo_hygiene.py backend/tests/integration/test_phase4_acceptance_gate.py
git commit -m "fix: centralize runtime configuration invariants"
```

---

### Task 2: Settings-backed Redis and queue behavior

**Files:**
- Modify: `backend/tests/unit/services/test_queue_and_batch_service.py`
- Modify: `backend/tests/unit/core/test_phase3_cache_tuning_and_diagnostics.py`
- Modify: `backend/app/core/cache.py`
- Modify: `backend/app/core/background_tasks.py`
- Modify: `backend/start_scheduler.py`
- Modify: `backend/app/services/processing_queue.py`
- Modify: `backend/app/services/shadow_validation_service.py`

**Interfaces:**
- Consumes: Redis and shadow settings introduced in Task 1.
- Produces: every shadow producer uses `settings.RQ_SHADOW_QUEUE_NAME`.

- [ ] **Step 1: Write failing Redis and queue tests**

Patch `Redis.from_url` and `Queue` to assert:

```python
def test_shadow_queue_uses_configured_name_and_retry_policy(monkeypatch) -> None:
    monkeypatch.setattr(settings, "RQ_SHADOW_QUEUE_NAME", "tenant-shadow")
    monkeypatch.setattr(settings, "SHADOW_VALIDATION_MAX_RETRIES", 4)
    monkeypatch.setattr(settings, "SHADOW_VALIDATION_RETRY_INTERVAL_SECONDS", 45)
    monkeypatch.setattr(settings, "SHADOW_VALIDATION_JOB_TIMEOUT_SECONDS", 720)
    connection = object()
    with (
        patch("redis.Redis.from_url", return_value=connection),
        patch("rq.Queue") as queue_type,
        patch("rq.Retry", return_value="retry-policy") as retry_type,
    ):
        assert ShadowValidationService.enqueue_shadow_validation(1, 2, {"score": 80}, "synthetic CV")
    queue_type.assert_called_once_with("tenant-shadow", connection=connection)
    retry_type.assert_called_once_with(max=4, interval=45)
    assert queue_type.return_value.enqueue.call_args.kwargs["retry"] == "retry-policy"
    assert queue_type.return_value.enqueue.call_args.kwargs["job_timeout"] == 720


def test_queue_probe_uses_named_timeout_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "REDIS_AVAILABILITY_PROBE_TIMEOUT_SECONDS", 2.5)
    connection = Mock()
    with patch("app.services.processing_queue.Redis.from_url", return_value=connection) as from_url:
        assert ProcessingQueueService._redis_connection() is connection
    from_url.assert_called_once_with(
        settings.REDIS_URL,
        socket_connect_timeout=2.5,
        socket_timeout=2.5,
    )
```

Add a test asserting shadow retry settings populate `Retry(max=...)`, `interval`, and `job_timeout`.

- [ ] **Step 2: Run the targeted tests and confirm they fail**

Run only after authorization:

```bash
cd backend
uv run pytest tests/unit/services/test_queue_and_batch_service.py tests/unit/core/test_phase3_cache_tuning_and_diagnostics.py -q
```

Expected: queue-name and Redis-timeout assertions fail against embedded literals.

- [ ] **Step 3: Replace embedded Redis and queue values**

Use settings at every call site:

```python
Queue(settings.RQ_SHADOW_QUEUE_NAME, connection=connection)
Retry(
    max=settings.SHADOW_VALIDATION_MAX_RETRIES,
    interval=settings.SHADOW_VALIDATION_RETRY_INTERVAL_SECONDS,
)
```

Use the named Redis timeout settings in cache, scheduler, background-task, and processing-queue clients. Replace `blocking_timeout=10` with `settings.REDIS_LOCK_BLOCKING_TIMEOUT_SECONDS`.

- [ ] **Step 4: Run the targeted tests and confirm they pass**

Run the Step 2 command after authorization. Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/app/core/cache.py backend/app/core/background_tasks.py backend/start_scheduler.py backend/app/services/processing_queue.py backend/app/services/shadow_validation_service.py backend/tests/unit/services/test_queue_and_batch_service.py backend/tests/unit/core/test_phase3_cache_tuning_and_diagnostics.py
git commit -m "fix: honor Redis and queue runtime settings"
```

---

### Task 3: Canonical storage writes with legacy nested reads

**Files:**
- Modify: `backend/tests/unit/repositories/test_processing_job_repo.py`
- Create: `backend/tests/unit/repositories/test_legacy_storage_compatibility.py`
- Modify: `backend/app/services/upload_service.py`
- Modify: `backend/app/repositories/result.py`

**Interfaces:**
- Consumes: `settings.UPLOADS_DIR`, `settings.RESULTS_DIR`, `settings.LEGACY_UPLOADS_DIR`, and `settings.LEGACY_RESULTS_DIR` from Task 1.
- Produces: `UploadService._read_storage_roots() -> tuple[Path, ...]` and `ResultRepository._disk_result_candidates(filename: str) -> tuple[Path, ...]`.

- [ ] **Step 1: Write failing legacy-read tests**

```python
def test_upload_lookup_reads_legacy_nested_root_but_writes_canonical(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(settings, "APP_DATA_ROOT", tmp_path)
    legacy = tmp_path / "uploads" / "candidate_hash.pdf"
    legacy.parent.mkdir()
    legacy.write_bytes(b"legacy-source")
    found = UploadService.find_reprocessable_upload(
        storage_filename=legacy.name,
        original_filename="candidate.pdf",
        cv_key="candidate",
    )
    assert found == legacy


def test_result_lookup_reads_legacy_nested_results(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(settings, "APP_DATA_ROOT", tmp_path)
    legacy = tmp_path / "uploads" / "results" / "candidate.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"id":"candidate"}', encoding="utf-8")
    with (
        patch.object(cv_result_cache_manager, "get", return_value=None),
        patch("app.repositories.result.PostgresAppSession", side_effect=RuntimeError("offline")),
    ):
        assert ResultRepository.read_result_by_filename("candidate.json")["id"] == "candidate"
```

Import `patch`, `settings`, `cv_result_cache_manager`, `ResultRepository`, and `UploadService` explicitly in the new test module. The mocks above force result lookup through disk fallback without contacting Redis or PostgreSQL.

- [ ] **Step 2: Run the new tests and confirm they fail**

Run only after authorization:

```bash
cd backend
uv run pytest tests/unit/repositories/test_legacy_storage_compatibility.py -q
```

Expected: legacy nested files are not found.

- [ ] **Step 3: Implement ordered read candidates**

Canonical writes remain unchanged. Reads check canonical first and legacy second:

```python
@classmethod
def _read_storage_roots(cls) -> tuple[Path, ...]:
    roots = (settings.UPLOADS_DIR.resolve(), settings.LEGACY_UPLOADS_DIR.resolve())
    return tuple(dict.fromkeys(roots))

@classmethod
def _disk_result_candidates(cls, filename: str) -> tuple[Path, ...]:
    result_name = filename if filename.endswith(".json") else f"{filename}.json"
    return tuple(dict.fromkeys((settings.RESULTS_DIR / result_name, settings.LEGACY_RESULTS_DIR / result_name)))
```

Contain each upload candidate within its selected root before reading. Cleanup and new persistence continue to target canonical storage only.

- [ ] **Step 4: Run the storage tests and confirm they pass**

Run the Step 2 command plus `tests/unit/repositories/test_processing_job_repo.py` after authorization.

- [ ] **Step 5: Commit Task 3**

```bash
git add backend/app/services/upload_service.py backend/app/repositories/result.py backend/tests/unit/repositories/test_legacy_storage_compatibility.py backend/tests/unit/repositories/test_processing_job_repo.py
git commit -m "fix: preserve legacy storage reads"
```

---

### Task 4: Propagate the active zero-skills scoring cap

**Files:**
- Modify: `backend/tests/unit/services/test_unified_scoring_architecture.py`
- Modify: `backend/app/core/rule_config_manager.py`
- Modify: `backend/app/schemas/scoring_config.py`

**Interfaces:**
- Produces: `ScoringPolicy.zero_skills_score_cap: float`.
- Consumes: `ScoringParameters.zero_skills_score_cap` from the active rule configuration.

- [ ] **Step 1: Write a failing policy-propagation test**

```python
def test_scoring_config_preserves_snapshot_zero_skills_cap() -> None:
    snapshot = PolicyRegistry.resolve_snapshot()
    configured = snapshot.model_copy(
        update={"scoring": snapshot.scoring.model_copy(update={"zero_skills_score_cap": 27.5})}
    )
    with patch.object(PolicyRegistry, "resolve_snapshot", return_value=configured):
        assert ScoringConfig.load().zero_skills_score_cap == 27.5
```

- [ ] **Step 2: Run the test and confirm it fails**

Run only after authorization:

```bash
cd backend
uv run pytest tests/unit/services/test_unified_scoring_architecture.py::test_scoring_config_preserves_snapshot_zero_skills_cap -q
```

Expected: `ScoringPolicy` lacks the field or `ScoringConfig` returns `40.0`.

- [ ] **Step 3: Hydrate the field through both policy paths**

Add:

```python
class ScoringPolicy(BaseModel):
    # existing fields...
    zero_skills_score_cap: float = Field(default=40.0, ge=0.0, le=100.0)
```

Set `zero_skills_score_cap=scoring_params.zero_skills_score_cap` in database snapshot hydration and ensure the emergency snapshot receives the factory value. In `ScoringConfig.load()`, replace `zero_skills_score_cap=40.0` with `zero_skills_score_cap=scoring.zero_skills_score_cap`.

- [ ] **Step 4: Run the targeted scoring tests and confirm they pass**

Run after authorization:

```bash
cd backend
uv run pytest tests/unit/services/test_unified_scoring_architecture.py tests/unit/services/test_scoring_engine.py -q
```

- [ ] **Step 5: Commit Task 4**

```bash
git add backend/app/core/rule_config_manager.py backend/app/schemas/scoring_config.py backend/tests/unit/services/test_unified_scoring_architecture.py
git commit -m "fix: honor configured zero-skills score cap"
```

---

### Task 5: Secure Compose boundaries and valid performance profiles

**Files:**
- Create: `backend/tests/unit/core/test_compose_configuration_contract.py`
- Modify: `docker-compose.yml`
- Modify: `docker-compose.local.yml`
- Modify: `docker-compose.profile-16gb.yml`
- Modify: `docker-compose.profile-32gb.yml`

**Interfaces:**
- Consumes: production validation from Task 1.
- Produces: base Compose without local credentials or database host ports; local override with loopback ports and disposable local URLs.

- [ ] **Step 1: Write a static failing Compose contract test**

Parse YAML text without adding a dependency:

```python
def test_base_compose_has_no_insecure_service_defaults_or_db_ports() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD:-postgres" not in compose
    assert "redis://redis:6379/0" not in compose
    assert '"5432:5432"' not in compose
    assert '"6380:6379"' not in compose
    assert "http://localhost:8081" not in compose


def test_supported_profiles_keep_single_slot_cv_processing() -> None:
    for profile in ("docker-compose.profile-16gb.yml", "docker-compose.profile-32gb.yml"):
        text = (REPO_ROOT / profile).read_text(encoding="utf-8")
        assert "CV_PROCESSING_CONCURRENCY: '2'" not in text
        assert "CV_PROCESSING_CONCURRENCY: '4'" not in text
```

- [ ] **Step 2: Run the static test and confirm it fails**

Run only after authorization:

```bash
cd backend
uv run pytest tests/unit/core/test_compose_configuration_contract.py -q
```

- [ ] **Step 3: Separate production and local configuration**

In base Compose, pass explicit environment values without insecure fallbacks:

```yaml
ALLOWED_ORIGINS: '${ALLOWED_ORIGINS:-[]}'
POSTGRES_APP_URL: '${POSTGRES_APP_URL:-}'
REDIS_URL: '${REDIS_URL:-}'
GIT_SHA: '${GIT_SHA:-unknown}'
```

Remove PostgreSQL and Redis host `ports` from the base. In the local override, set the internal PostgreSQL and Redis URLs and add loopback-only mappings:

```yaml
services:
  pgvector:
    ports:
      - '${POSTGRES_BIND_ADDRESS:-127.0.0.1}:${POSTGRES_HOST_PORT:-5432}:5432'
  redis:
    ports:
      - '${REDIS_BIND_ADDRESS:-127.0.0.1}:${REDIS_HOST_PORT:-6380}:6379'
```

Require local PostgreSQL password selection through `.env.example`, retaining `postgres` only as an explicitly documented local value. Set all profile `CV_PROCESSING_CONCURRENCY` values to `1` and remove `MAX_CONCURRENT_LLM_WORKERS` entries.

- [ ] **Step 4: Run static tests and render Compose configurations**

After authorization, run the Step 2 test and:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml config
docker compose -f docker-compose.yml -f docker-compose.local.yml -f docker-compose.profile-16gb.yml config
docker compose -f docker-compose.yml -f docker-compose.local.yml -f docker-compose.profile-32gb.yml config
```

Expected: all render successfully; database host ports bind only to loopback; all profiles set single-slot CV concurrency.

- [ ] **Step 5: Commit Task 5**

```bash
git add docker-compose.yml docker-compose.local.yml docker-compose.profile-16gb.yml docker-compose.profile-32gb.yml backend/tests/unit/core/test_compose_configuration_contract.py
git commit -m "fix: separate production and local deployment defaults"
```

---

### Task 6: Fail-safe frontend API configuration and bounded polling

**Files:**
- Create: `frontend/src/utils/runtimeConfig.ts`
- Create: `frontend/src/__tests__/runtimeConfig.test.mjs`
- Modify: `frontend/src/constants/config.ts`
- Modify: `frontend/src/hooks/useCvUpload.ts`
- Modify: `frontend/src/hooks/useCvQueueUploads.ts`

**Interfaces:**
- Produces: `nextPollingAttempt(attempt: number, maximum: number): number | null`.
- Produces: `resolveApiBaseUrl(explicitUrl: string | undefined, platform: string, development: boolean): string`.

- [ ] **Step 1: Write standalone failing frontend tests**

Create a Node-executable `.mjs` test that reads `runtimeConfig.ts`, transpiles it with the installed `typescript` package using the same `Module._compile` pattern as `candidateDetailGeneric.test.mjs`, and covers these contracts:

```javascript
assert.equal(nextPollingAttempt(0, 250), 1);
assert.equal(nextPollingAttempt(249, 250), 250);
assert.equal(nextPollingAttempt(250, 250), null);
assert.throws(() => resolveApiBaseUrl(undefined, 'web', false), /EXPO_PUBLIC_API_URL/);
assert.equal(resolveApiBaseUrl(undefined, 'android', true), 'http://10.0.2.2:8000');
assert.equal(resolveApiBaseUrl(undefined, 'web', true), 'http://localhost:8000');
assert.equal(resolveApiBaseUrl('https://api.example.com/', 'web', false), 'https://api.example.com');
```

- [ ] **Step 2: Run the standalone test and confirm it fails**

Run only after authorization:

```bash
node frontend/src/__tests__/runtimeConfig.test.mjs
```

Expected: imported functions do not exist.

- [ ] **Step 3: Implement pure configuration and polling helpers**

`resolveApiBaseUrl` trims a trailing slash, accepts only absolute HTTP(S) URLs, permits loopback fallback only when `development` is true, and throws an actionable error otherwise. `config.ts` calls it with `process.env.EXPO_PUBLIC_API_URL`, `Platform.OS`, and `__DEV__`.

Use a bounded attempt helper in both upload hooks:

```typescript
const nextAttempt = nextPollingAttempt(attempt, API_CONFIG.MAX_POLL_RETRIES);
if (nextAttempt === null) {
  stopPolling(clientId);
  updateItem(clientId, { state: 'FAILED', error: 'Processing is taking longer than expected.' });
  return;
}
schedulePoll(clientId, cvKey, enrichWithLlm, nextAttempt, nextErrorCount);
```

Set the maximum polling duration to match the default one-hour backend job timeout, for example `POLL_INTERVAL_MS: 3000` and `MAX_POLL_RETRIES: 1200`, while keeping both values overrideable through `EXPO_PUBLIC_POLL_INTERVAL_MS` and `EXPO_PUBLIC_MAX_POLL_RETRIES` with positive-integer validation.

- [ ] **Step 4: Run frontend tests and type checking**

After authorization:

```bash
node frontend/src/__tests__/runtimeConfig.test.mjs
cd frontend
npx tsc --noEmit
```

Expected: runtime configuration test passes and TypeScript reports no errors.

- [ ] **Step 5: Commit Task 6**

```bash
git add frontend/src/constants/config.ts frontend/src/utils/runtimeConfig.ts frontend/src/hooks/useCvUpload.ts frontend/src/hooks/useCvQueueUploads.ts frontend/src/__tests__/runtimeConfig.test.mjs
git commit -m "fix: require production API configuration"
```

---

### Task 7: Make hardcoding approvals exact

**Files:**
- Modify: `backend/tests/unit/core/test_hardcoding_regression_gate.py`
- Modify: `backend/scripts/quality/hardcoding_audit.py`
- Modify: `hardcoding-baseline.json`
- Regenerate after authorization: `hardcoding_findings.json`

**Interfaces:**
- Produces: `snippet_fingerprint(snippet: str) -> str` using normalized snippet SHA-256.
- Produces: `finding_identity(finding: dict[str, object]) -> tuple[str, int, str, str]`.
- Produces: `load_approved_identities(path: Path) -> set[tuple[str, int, str, str]]`, rejecting incomplete entries.

- [ ] **Step 1: Write failing exact-identity tests**

```python
def test_baseline_entry_without_line_and_fingerprint_is_rejected(tmp_path: Path) -> None:
    baseline = {"allowlisted_findings": [{"file": "app.py", "category": "MAGIC", "owner": "x", "justification": "x"}]}
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    with pytest.raises(ValueError, match="line.*fingerprint"):
        load_approved_identities(baseline_path)


def test_same_file_and_category_with_different_snippet_is_unapproved() -> None:
    approved = {("app.py", 10, "MAGIC", snippet_fingerprint("threshold = 7"))}
    finding = {"file": "app.py", "line": 10, "category": "MAGIC", "snippet": "threshold = 9"}
    assert finding_identity(finding) not in approved
```

- [ ] **Step 2: Run the hardcoding regression test and confirm it fails**

Run only after authorization:

```bash
cd backend
uv run pytest tests/unit/core/test_hardcoding_regression_gate.py -q
```

- [ ] **Step 3: Implement strict baseline loading**

Normalize whitespace in snippets and hash them:

```python
def snippet_fingerprint(snippet: str) -> str:
    normalized = " ".join(snippet.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

Require `file`, `line`, `category`, `fingerprint`, `owner`, and `justification` on every baseline entry. Remove file/category fallback matching. Update the baseline only for intentional remaining findings after Tasks 1–6.

- [ ] **Step 4: Run targeted tests and audit scripts**

After authorization:

```bash
cd backend
uv run pytest tests/unit/core/test_hardcoding_regression_gate.py -q
uv run python scripts/quality/check_no_hardcoding.py
uv run python scripts/quality/check_frontend_hardcoding.py
uv run python scripts/quality/hardcoding_audit.py --baseline ../hardcoding-baseline.json --fail-on=new-unapproved
```

Expected: targeted tests and all three audits pass with no broad baseline approvals.

- [ ] **Step 5: Commit Task 7**

```bash
git add backend/scripts/quality/hardcoding_audit.py backend/tests/unit/core/test_hardcoding_regression_gate.py hardcoding-baseline.json hardcoding_findings.json
git commit -m "fix: scope hardcoding approvals to exact findings"
```

---

### Task 8: Sanitize repository configuration and documentation

**Files:**
- Modify: `.vscode/settings.json`
- Modify: `backend/.env.example`
- Modify: `README.md`
- Modify: `run.md`
- Modify: `workstats.md` append-only

**Interfaces:**
- Documents: exact production-required variables and local-only defaults established in Tasks 1–7.

- [ ] **Step 1: Add a static hygiene assertion**

Extend `backend/tests/unit/core/test_version_and_repo_hygiene.py`:

```python
def test_tracked_configuration_has_no_machine_or_candidate_paths() -> None:
    vscode = (REPO_ROOT / ".vscode" / "settings.json").read_text(encoding="utf-8")
    run_doc = (REPO_ROOT / "run.md").read_text(encoding="utf-8")
    assert "/Users/" not in vscode
    assert "cv_13639" not in vscode
    assert "172.25.1.160" not in run_doc
    assert "mssql+pyodbc://sa:" not in run_doc
```

- [ ] **Step 2: Run the hygiene test and confirm it fails**

Run only after authorization:

```bash
cd backend
uv run pytest tests/unit/core/test_version_and_repo_hygiene.py -q
```

- [ ] **Step 3: Sanitize and align configuration documentation**

Replace `.vscode/settings.json` with an empty JSON object (`{}`), removing all repository-tracked command auto-approval history. Replace the `run.md` MSSQL URL with:

```ini
MSSQL_READ_ONLY_URL=mssql+pyodbc://<read_only_user>:<password>@<sql_host>:1433/<database>?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
```

Remove `RQ_DEVELOPMENT_FALLBACK_ENABLED` and `MAX_CONCURRENT_LLM_WORKERS` from examples and docs. Document required production `POSTGRES_APP_URL`, authenticated `REDIS_URL`, `ALLOWED_ORIGINS`, API keys, signing key, and `GIT_SHA`; document local loopback port overrides separately.

- [ ] **Step 4: Append the implementation log**

Append one new sequential `workstats.md` entry summarizing all completed tasks, exact modified files, compatibility behavior, and verification actually performed. Do not alter Entry #058 or any earlier entry.

- [ ] **Step 5: Run final targeted verification**

After authorization, run the tests and commands from Tasks 1–8. Do not run `verify_release_gate.py`; this task does not meet its execution conditions.

- [ ] **Step 6: Review the final diff and commit documentation/hygiene**

```bash
git diff --check
git status --short
git add .vscode/settings.json backend/.env.example README.md run.md backend/tests/unit/core/test_version_and_repo_hygiene.py workstats.md
git commit -m "docs: align secure runtime configuration"
```

Confirm only task-related hunks are staged because the repository began with substantial user-owned modifications.
