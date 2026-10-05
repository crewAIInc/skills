# Deployed Crew API Contract

Every endpoint, field, state and error a client of a deployed crew or flow needs, each with the public page it comes from. Re-check the linked pages when something here disagrees with what you see.

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
| Health check | `GET /` returns `Healthy` | platform guide |

---

## 2. `GET /inputs`

Response `200`: `{"inputs": ["budget", "interests", "duration", "age"]}` - the names of the inputs the crew requires. Errors: `401`, `404`, `500`.
Source: https://docs.crewai.com/en/api-reference/inputs

Locally, the same names come from the `{placeholder}` tokens in task `description` / `expected_output` and agent `role` / `goal` / `backstory`; `Crew.fetch_inputs()` returns them as a set.

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
| `webhooks` | no | object | event streaming, section 6 (webhook streaming page) |
| `restoreFromStateId` | no | UUID string | flows with `@persist`: hydrate from that state, record a new execution (inputs-id-deprecation page) |

Response `200`: `{"kickoff_id": "<uuid>"}`.

Errors:
- `400`: invalid request body or missing required inputs.
- `401`: bad token.
- `422`: `{"error": "Validation Error", "message": "Missing required inputs", "details": {"missing_inputs": ["budget", "interests"]}}`.
- `500`: server error.

Flows: the deprecated way to continue a `@persist` flow was `{"inputs": {"id": "<uuid>", ...}}`. On AMP, reusing an `inputs.id` resolves to the existing execution record, so status, traces and the executions list of the old run get overwritten or merged. Send `restoreFromStateId` beside `inputs` instead; each kickoff then stays its own execution.

---

## 4. `GET /status/{kickoff_id}`

Two documented shapes. A client should accept both.

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

- Each delivery is `{"events": [{"id", "execution_id", "timestamp", "type", "data"}]}`; `data` depends on the event type.
- Delivery order is not guaranteed; order by `timestamp`.
- `realtime: true` sends each event immediately, at some cost to run performance; otherwise events are batched.
- Event names match crewai's event bus: flow (`flow_started`, `flow_finished`, `method_execution_*`), crew (`crew_kickoff_started` / `_completed` / `_failed`), task (`task_started`, `task_completed`, `task_failed`), agent, tool, LLM, memory, knowledge and reasoning events. See the page for the full list.
- Your endpoint should reject requests without the bearer secret you configured, and be idempotent on event `id`.

---

## 7. Error codes summary

| Code | Meaning | Client action |
|---|---|---|
| `200` | success | - |
| `400` | invalid body (for example no `inputs` object) | fix the request; do not retry |
| `401` | invalid bearer token | fix the token; do not retry |
| `404` | unknown kickoff id / resource | check the deployment URL; brief grace right after kickoff, then fail |
| `422` | missing required inputs (`details.missing_inputs`) | add the keys; do not retry |
| `500` | server error | surface it; for read-only calls a delayed retry is safe |
| `502` / `503` / `504` | not in the API reference; standard gateway / unavailable codes | treat as transient: retry read-only calls with backoff, honoring `Retry-After`; retry `POST /kickoff` only on `503`, since after a `502` / `504` the run may have started |
