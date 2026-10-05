# Deployed Crew API Contract

Every endpoint, field, state and error a client of a deployed crew or flow needs, each with the public page it comes from, and - where a live deployment on CrewAI AMP answered differently on 2026-10-01 - what it actually returned. Re-check the linked pages when something here disagrees with what you see.

Sources:
- API reference (OpenAPI): https://docs.crewai.com/en/api-reference/introduction and its endpoint pages
- Platform guide: https://docs-platform.crewai.com/platform/en/guides/kickoff-crew
- Webhook streaming: https://docs-platform.crewai.com/platform/en/features/webhook-streaming
- Flow state restore: https://docs.crewai.com/en/guides/flows/inputs-id-deprecation

---

## 1. Base URL and authentication

| Item | Value | Source |
|---|---|---|
| Base URL | One per deployment, `https://<your-deployment>.crewai.com`, copied from the dashboard | API introduction |
| Auth header | `Authorization: Bearer <token>` on every call | API introduction |
| Where the token is | The deployment's detail page, Status tab | API introduction, platform guide |
| Token types | **Bearer Token** (organization-level, full crew operations) and **User Bearer Token** (user-scoped, limited permissions) | API introduction |
| Health check | The guide shows `GET /` returning `Healthy`. Live: `404 {"detail":"Not Found"}` on a crew and a flow. Use `GET /inputs` | platform guide; live |
| Bad / missing token | Live: `401 {"detail":"Invalid or missing authentication credentials"}` / `401 {"detail":"Not authenticated"}` | live |

---

## 2. `GET /inputs`

Response `200`: `{"inputs": ["budget", "interests", "duration", "age"]}` - the names of the inputs the crew requires. Errors: `401`, `404`, `500`.
Source: https://docs.crewai.com/en/api-reference/inputs

Locally, the same names come from the `{placeholder}` tokens in task `description` / `expected_output` and agent `role` / `goal` / `backstory`; `Crew.fetch_inputs()` returns them as a set.

Flows (live): `/inputs` returned the fields the state model declares - `{"inputs": ["topic", "count", "id", "history"]}` for a model that declared `id`; another flow whose model did not declare `id` listed only its own fields. None is required; do not send `id`.

---

## 3. `POST /kickoff`

Source: https://docs.crewai.com/en/api-reference/kickoff

| Field | Required | Type | Notes |
|---|---|---|---|
| `inputs` | yes | object, values typed as strings | every required input key |
| `meta` | no | object | free-form metadata |
| `taskWebhookUrl` | no | URI | called after each task completes |
| `stepWebhookUrl` | no | URI | called after each agent thought/action |
| `crewWebhookUrl` | no | URI | called when the execution completes |
| `humanInputWebhookUrl` | no | URI | called when a `human_input=True` task waits for review (HITL Workflows guide; section 5) |
| `webhooks` | no | object | event streaming, section 6 (webhook streaming page) |
| `restoreFromStateId` | no | UUID string | flows with `@persist`: hydrate from that state, record a new execution (inputs-id-deprecation page) |

Response `200`: `{"kickoff_id": "<uuid>"}`.

Errors as documented, and as returned live:

| Case | Documented | Live (2026-10-01) |
|---|---|---|
| Crew, required key missing / `{"inputs": {}}` / `{}` / bare body without `inputs` | `400` or `422 {"error": "Validation Error", "message": "Missing required inputs", "details": {"missing_inputs": [...]}}` | `422 {"detail":"Missing inputs: audience, topic"}` |
| Flow, empty or bare body | same | `200`, run on default state; top-level keys ignored |
| Body not valid JSON | `400` | `500 Internal Server Error` (plain text) |
| Bad token | `401` | `401 {"detail":"Invalid or missing authentication credentials"}` |
| Non-string input value (`"audience": 3`) | values typed as strings | accepted, stringified (`AUDIENCE=3`) |

Flows: the deprecated way to continue a `@persist` flow was `{"inputs": {"id": "<uuid>", ...}}`. The docs say that on AMP reusing an `inputs.id` resolves to the existing execution record, so status, traces and the executions list of the old run get overwritten or merged. Send `restoreFromStateId` beside `inputs` instead; each kickoff then stays its own execution.

Live (`@persist` flow, no LLM): a run's `state.id` equals its `kickoff_id`. `restoreFromStateId: <kickoff_id of run 1>` gave `count=2` under a new state id (= the new kickoff_id); chaining from run 2 gave `count=3`; an unknown id ran from defaults without error. `inputs.id = <run 1 kickoff_id>` also restored, but the run wrote its state back under run 1's id.

---

## 4. `GET /status/{kickoff_id}`

Two documented shapes. Live deployments returned the platform guide shape; a client should still accept both.

Live observations (crew and flow, 2026-10-01):
- States seen: `PENDING`, `STARTED`, `RUNNING`, `SUCCESS`, `FAILED`, and `NOT FOUND` (with a space). `PAUSED` / `REVOKED` were not seen.
- An unknown or malformed id returns HTTP `200` with `{"state": "NOT FOUND", "status": "Task not found or Invalid kickoff id", ...}` - not `404`.
- `status` is a message: `"Task is pending"`, `"Task is Running"`, the exception text on `FAILED` (`"ValueError: ..."`), `null` on `SUCCESS`.
- `result` is the final output string; `result_json` was `null` for a plain-text result; `usage_metrics` carried token counts; `execution_origin` was `api`; `last_executed_task` held the last task's name, interpolated description, output, `kickoff_id` and `meta`.
- Crew progress: `{"unit": "task", "completed": 1, "total": 2, "remaining": 1, "current": "summary_task", ...}`. Flow progress: `{"unit": "step", "total": null, "remaining": null, ...}`.
- A failed run: `state: FAILED`, `result: null`, `progress: null`.

**Platform guide shape** (https://docs-platform.crewai.com/platform/en/guides/kickoff-crew):

| Field | Meaning |
|---|---|
| `state` | `PENDING`, `STARTED`, `RUNNING`, `SUCCESS`, `FAILED`, `PAUSED`, `REVOKED` |
| `status` | short human-readable message about the state |
| `result` | final output; empty until the execution stops |
| `result_json` | final output as JSON, when the output is a JSON object |
| `usage_metrics` | token counts |
| `progress` | `unit` (`task` for crews, `step` for flows), `completed`, `total`, `remaining`, `current`, `current_agent`, `started_at`, `updated_at`, `duration_seconds` |
| `last_event`, `events`, `events_count`, `events_by_type` | event summaries (no prompts or outputs) |
| `triggered_by` | `{type: user \| service_account \| unknown, id}` |
| `execution_origin` | `ui`, `schedule`, `trigger`, `chat`, `hitl-resume`, `replay`, `api` |
| `last_step`, `last_executed_task` | crews only |
| `flow_id` | a flow waiting for human feedback |
| `source` | `memory` or `application` |

Notes from the same page:
- For a flow, `progress.total` and `progress.remaining` are always `null`. Show `completed` as a count, not a percentage.
- A queued execution has `state` `PENDING`.
- Progress and event data are `null` for deployments on crewai 1.15.21 or earlier, and when `source` is `application`.
- Deployment env vars `CREWAI_STATUS_EVENTS`, `CREWAI_STATUS_MAX_EVENTS`, `CREWAI_STATUS_EVENT_FLUSH_SECONDS` tune the event log.

**API reference shape** (https://docs.crewai.com/en/api-reference/status):

```json
{"status": "running", "current_task": "research_task", "progress": {"completed_tasks": 1, "total_tasks": 3}}
{"status": "completed", "result": {"output": "...", "tasks": [{"task_id": "...", "output": "...", "agent": "...", "execution_time": 45.2}]}, "execution_time": 108.5}
{"status": "error", "error": "Task execution failed: ...", "execution_time": 23.1}
```

`404`: `{"error": "Execution not found", "message": "No execution found with ID: ..."}`.

Client rules that cover both:

| Read | Rule |
|---|---|
| state | `state` if present, else `status`; lower-case it |
| success | `success`, `completed` |
| failure | `failed`, `error`, `revoked` (and treat `failure` the same) |
| unknown id | `not found` (HTTP 200) or HTTP `404` - short grace, then fail |
| repeated `5xx` | stop after a few, check the deployment logs - the run itself may have failed |
| waiting for a human | `paused` |
| anything else | still in progress - keep polling until your deadline |
| result | `result_json`, else `result` (a string, or `result.output`) |

---

## 5. `POST /resume`

Source: https://docs.crewai.com/en/api-reference/resume

For crews where a task has `human_input=True`: the execution pauses after that task and waits for feedback.

| Field | Required | Notes |
|---|---|---|
| `execution_id` | yes | the kickoff id |
| `task_id` | yes | the task waiting for feedback |
| `human_feedback` | yes | text added as context for what follows |
| `is_approve` | yes | `true` continue, `false` retry the task with the feedback |
| `taskWebhookUrl`, `stepWebhookUrl`, `crewWebhookUrl` | no | must be sent again - webhook settings are **not** carried over from the kickoff |

Response `200`: `{"status": "resumed" | "retrying" | "completed", "message": "..."}`. `400` when the execution is not waiting for human input; `404` for an unknown execution or task id.

The [HITL Workflows guide](https://docs-platform.crewai.com/platform/en/guides/human-in-the-loop) adds a kickoff field, `humanInputWebhookUrl`, called when the task waits for review.

Live test on 2026-10-01 (crew with a static `human_input=True` task):

| Step | Observed |
|---|---|
| Kickoff with `humanInputWebhookUrl` | Webhook body `{"kickoff_id", "execution_id", "task_id", "task_output", "meta"}`; `task_id` is a UUID, not the method name |
| `/status` while waiting | `NOT FOUND`, never `PAUSED` |
| `/resume` with the documented snake_case fields | `422`: `executionId` and `taskId` "Field required" |
| `/resume` with `executionId`, `taskId` (and either snake or camel feedback fields) | `200 {"kickoff_id": "<new id>"}` - also for an unknown execution |
| That new kickoff id | `FAILED`, `'NoneType' object is not subscriptable` |

No variant tried resumed the crew to completion. Prove the full cycle on your own deployment before depending on it.

For flows, human review uses `@human_feedback`; see https://docs.crewai.com/en/learn/human-feedback-in-flows.

---

## 6. Webhook streaming

Source: https://docs-platform.crewai.com/platform/en/features/webhook-streaming

```json
{
  "inputs": {"topic": "AI agents"},
  "webhooks": {
    "events": ["crew_kickoff_started", "task_completed", "crew_kickoff_completed", "crew_kickoff_failed"],
    "url": "https://your-server.example.com/crewai-events",
    "realtime": false,
    "authentication": {"strategy": "bearer", "token": "<your-webhook-secret>"}
  }
}
```

- Each delivery is `{"events": [{"id", "execution_id", "timestamp", "type", "data"}]}`; `data` depends on the event type. Live: `data.emission_sequence` is present on every event.
- Delivery order is not guaranteed; order by `timestamp`. Live with `realtime: true`, a `task_started` arrived before the previous `task_completed`.
- `realtime: true` sends each event immediately, at some cost to run performance; otherwise events are batched. Live: `realtime: false` sent 4 events in one POST; `realtime: true` sent one POST per event.
- Live: the streaming POST carried `Authorization: Bearer <your-webhook-secret>`. The `taskWebhookUrl` / `crewWebhookUrl` / `humanInputWebhookUrl` POSTs carried no `Authorization` header - confirm them by `kickoff_id` with `GET /status`.
- Event names match crewai's event bus: flow (`flow_started`, `flow_finished`, `method_execution_*`), crew (`crew_kickoff_started` / `_completed` / `_failed`), task (`task_started`, `task_completed`, `task_failed`), agent, tool, LLM, memory, knowledge and reasoning events. See the page for the full list.
- Your endpoint should reject requests without the bearer secret you configured, and be idempotent on event `id`.

---

## 7. Error codes summary

| Code | Meaning | Client action |
|---|---|---|
| `200` | success | - |
| `400` | invalid body (documented; live, a crew answered `422` and invalid JSON `500`) | fix the request; do not retry |
| `401` | invalid bearer token | fix the token; do not retry |
| `404` | unknown resource (documented for unknown kickoff ids; live, `/status` answers `200` + `NOT FOUND` instead, and `GET /` answers `404`) | check the deployment URL; brief grace right after kickoff, then fail |
| `422` | missing required inputs (documented `details.missing_inputs`; live `{"detail": "Missing inputs: a, b"}`) | add the keys; do not retry |
| `500` | server error (live: also invalid JSON in the kickoff body) | surface it; for read-only calls a delayed retry is safe; a `/status` that keeps returning `500` can mean the run failed - check the logs |
| `502` / `503` / `504` | not in the API reference; standard gateway / unavailable codes | treat as transient: retry read-only calls with backoff, honoring `Retry-After`; retry `POST /kickoff` only on `503`, since after a `502` / `504` the run may have started |
