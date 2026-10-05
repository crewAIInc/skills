---
name: call-deployed-crew
description: "Calling a crew or flow deployed on CrewAI AMP over HTTP: the bearer token and deployment URL, GET /inputs, POST /kickoff with the {\"inputs\": {...}} body, which input keys are required ({placeholder} tokens), polling GET /status/{kickoff_id} with a deadline and backoff, terminal states and where the result lives, webhooks, POST /resume, slow first calls, and writing crews that stay correct when they are kicked off repeatedly or concurrently. Use when writing a client, script, backend or frontend that calls a deployed crew, when a kickoff returns 422 \"Missing required inputs\", when a status poll never ends or the result field is empty, when a run's prompt shows another run's data, or when the user pastes a kickoff_id, a /kickoff curl, or 'Template variable ... not found in inputs dictionary'."
---

# Call a Deployed Crew

How to call a crew or flow that runs on CrewAI AMP from your own code, and how to write the crew so those calls stay correct.

Verified against crewai 1.15.22 and 1.15.23 on 2026-10-01.
Run `crewai version` first; if the major/minor differs, re-check the version-sensitive rows with the `ask-docs` skill.

---

## 1. The contract on one screen

Every deployment has its own base URL and bearer token, both shown on the deployment's page in the AMP dashboard (Status tab). All calls send `Authorization: Bearer <token>`.

| Call | Body | Success response | Docs |
|---|---|---|---|
| `GET /` | - | `Healthy` (plain text) | [Kickoff Crew guide](https://docs-platform.crewai.com/platform/en/guides/kickoff-crew) |
| `GET /inputs` | - | `{"inputs": ["topic", "audience"]}` | [GET /inputs](https://docs.crewai.com/en/api-reference/inputs) |
| `POST /kickoff` | `{"inputs": {"topic": "...", ...}}` plus optional siblings (section 4) | `{"kickoff_id": "<uuid>"}` | [POST /kickoff](https://docs.crewai.com/en/api-reference/kickoff) |
| `GET /status/{kickoff_id}` | - | run state, progress, result (section 5) | [GET /status](https://docs.crewai.com/en/api-reference/status) |
| `POST /resume` | `{"execution_id", "task_id", "human_feedback", "is_approve"}` | `{"status": "resumed" \| "retrying" \| "completed"}` | [POST /resume](https://docs.crewai.com/en/api-reference/resume) |

Documented error codes: `400` bad body, `401` bad token, `404` unknown kickoff id, `422` missing required inputs (with `details.missing_inputs`), `500` server error ([API introduction](https://docs.crewai.com/en/api-reference/introduction)).

```bash
export CREWAI_DEPLOYMENT_URL="https://<your-deployment>.crewai.com"
export CREWAI_DEPLOYMENT_TOKEN="<your-bearer-token>"

curl -s -H "Authorization: Bearer $CREWAI_DEPLOYMENT_TOKEN" "$CREWAI_DEPLOYMENT_URL/inputs"

curl -s -X POST "$CREWAI_DEPLOYMENT_URL/kickoff" \
  -H "Authorization: Bearer $CREWAI_DEPLOYMENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"topic": "AI agents", "audience": "engineers"}}'

curl -s -H "Authorization: Bearer $CREWAI_DEPLOYMENT_TOKEN" \
  "$CREWAI_DEPLOYMENT_URL/status/<kickoff_id>"
```

Rules:
- Keep the URL and token in environment variables or a secret store. Never hard-code the token, commit it, log the `Authorization` header, or ship it to a browser - call the deployment from your backend.
- The dashboard shows an organization-level **Bearer Token** and a **User Bearer Token** with narrower permissions. Use the narrowest one that works for the integration.

---

## 2. Required inputs come from `{placeholder}` tokens

The keys a crew needs are the `{name}` tokens in its task `description` / `expected_output` and its agent `role` / `goal` / `backstory`. `GET /inputs` lists them for the deployed version. Read the keys from `/inputs` (or from your code) - never guess them.

Locally, `Crew.fetch_inputs()` is crewai's own scan of the same fields:

```python
from crewai import Agent, Crew, Task

agent = Agent(role="{topic} researcher", goal="Explain {topic}", backstory="Writes for {audience}.")
task = Task(description="Research {topic} for {audience}.", expected_output="A summary of {topic}.", agent=agent)
print(sorted(Crew(agents=[agent], tasks=[task]).fetch_inputs()))  # ['audience', 'topic']
```

What crewai does with the inputs it receives (verified locally on 1.15.22-1.15.23):

| You send | What happens |
|---|---|
| Every placeholder key | Values are substituted into agent and task text before the first LLM call |
| A placeholder key missing | `ValueError: Missing required template variable 'Template variable 'audience' not found in inputs dictionary' in description` - raised before any LLM call |
| An extra key with no placeholder | Silently ignored; it never reaches a prompt |
| No inputs, or `inputs={}` | **No error.** Interpolation is skipped and the literal text `{topic}` reaches the model |
| int / float / bool / list / dict values | Accepted locally and stringified with `str()`. The deployed API documents every input value as a string - send strings |

Consequences:
- Validate the request against `/inputs` in your client before calling `/kickoff`, and send every key. Do not rely on an empty-inputs run failing loudly.
- A literal JSON example inside a prompt (`Reply like {"title": "..."}`) is not interpolated, but `fetch_inputs()` reports `"title": "..."` as an input name. Any input list derived from braces will ask for it. Put output structure in `output_pydantic` / `response_model` instead of a JSON sample in the text.
- Send dates as ISO 8601 strings and structured values as JSON strings, and parse them inside the crew.

---

## 3. The kickoff body: `inputs` is a wrapper

| Bad | Good |
|---|---|
| `{"topic": "AI agents", "audience": "engineers"}` | `{"inputs": {"topic": "AI agents", "audience": "engineers"}}` |
| `{"inputs": {"topic": "...", "meta": {...}}}` | `{"inputs": {"topic": "..."}, "meta": {...}}` |
| `{"inputs": {"id": "<previous-state-id>", "topic": "..."}}` (flows, deprecated) | `{"inputs": {"topic": "..."}, "restoreFromStateId": "<previous-state-id>"}` |
| Retrying `POST /kickoff` after a read timeout | Treat it as "maybe started"; look for the run before sending another kickoff |

`inputs` is the only required field. A bare body has no `inputs` object, so it fails validation - the docs list `400` (invalid body or missing inputs) and `422` (missing required inputs) for this.

---

## 4. Optional fields beside `inputs`

All of these sit at the top level of the kickoff body, never inside `inputs`:

| Field | Purpose | Docs |
|---|---|---|
| `meta` | Free-form metadata (`{"requestId": "..."}`) | [POST /kickoff](https://docs.crewai.com/en/api-reference/kickoff) |
| `taskWebhookUrl` | Called after each task completes | same |
| `stepWebhookUrl` | Called after each agent thought/action | same |
| `crewWebhookUrl` | Called when the execution completes | same |
| `webhooks` | Event streaming: `{"events": [...], "url": "...", "realtime": false, "authentication": {"strategy": "bearer", "token": "<your-webhook-secret>"}}` | [Webhook Streaming](https://docs-platform.crewai.com/platform/en/features/webhook-streaming) |
| `restoreFromStateId` | Flows with `@persist`: hydrate state from a previous run, record a new run | [inputs.id deprecation](https://docs.crewai.com/en/guides/flows/inputs-id-deprecation) |

Webhook streaming delivers `{"events": [{id, execution_id, timestamp, type, data}]}`. Order is not guaranteed - sort by `timestamp`. With `realtime: false` events are batched; `realtime: true` sends each event immediately at some cost to run performance. Your receiver must check the bearer secret you set in `authentication`.

Store the `kickoff_id` with your own request id as soon as `/kickoff` returns. It is the only handle you have on that run.

---

## 5. Polling `/status/{kickoff_id}`

The two public sources show two response shapes. Handle both:

| Source | State field | Values | Result |
|---|---|---|---|
| [Kickoff Crew guide](https://docs-platform.crewai.com/platform/en/guides/kickoff-crew) | `state` (`status` is a human message) | `PENDING`, `STARTED`, `RUNNING`, `SUCCESS`, `FAILED`, `PAUSED`, `REVOKED` | `result` (string, empty until the run stops), `result_json` (when the output is a JSON object) |
| [API reference](https://docs.crewai.com/en/api-reference/status) | `status` | `running`, `completed`, `error` | `result.output`, error text in `error` |

Rules:
1. Read `state`; fall back to `status` only when `state` is absent. Compare lower-cased.
2. Terminal: success = `success` / `completed`; failure = `failed` / `error` / `revoked`; `paused` = waiting for human feedback (`POST /resume`). Anything else means keep polling.
3. Read `result_json`, then `result` (string, or `result.output` in the reference shape).
4. Poll with backoff (start around 2 s, grow to about 15 s, add jitter) under an **overall deadline** you choose from the crew's normal run time. Never poll in an unbounded `while True`.
5. A deadline is not a failure of the run. Report it with the `kickoff_id`, keep the id, and check again later - do not kick off a duplicate.
6. For flows, `progress.total` and `progress.remaining` are `null`; show `progress.completed` as a step count, not a percentage.
7. A `404` means the id is unknown to that deployment. Check you are polling the same deployment URL that issued it; tolerate a few 404s immediately after kickoff, then fail.

Prefer webhooks (section 4) over tight polling when many runs are in flight.

---

## 6. The first call after a quiet period

Do not assume the first request after a quiet period answers as fast as the rest, or that it answers `200` on the first try. Design for it:

- Give the first request a generous timeout (minutes, not seconds) and retry `502` / `503` / `504` with backoff, honoring `Retry-After`.
- Make that first request `GET /inputs`: it is read-only, so retrying it is always safe, and you need its key list anyway.
- Retry `POST /kickoff` only when the request provably never reached the server (connection refused / DNS) or got a `502` / `503` / `504`. A read timeout may mean the run started.

---

## 7. A small Python client

The full client (httpx, about 200 lines) is in [references/python-client.md](references/python-client.md). It does sections 2-6: validates inputs against `/inputs`, wraps them in `{"inputs": ...}`, stringifies values, retries only what is safe, polls with backoff under a deadline, and raises `RunFailed` / `RunPaused` / `RunTimeout` carrying the `kickoff_id`.

```python
import os
from deployed_crew_client import DeployedCrew, RunTimeout

crew = DeployedCrew(os.environ["CREWAI_DEPLOYMENT_URL"], os.environ["CREWAI_DEPLOYMENT_TOKEN"])
try:
    result = crew.run({"topic": "AI agents", "audience": "engineers"}, deadline_s=900)
except RunTimeout as e:
    print("still running, check later:", e.kickoff_id)
finally:
    crew.close()
```

A curl polling loop with a deadline is in the same reference.

---

## 8. Write the crew so repeated and concurrent calls stay correct

Your deployment serves many kickoffs. Do not assume each one gets fresh Python objects: module globals, class attributes, tool instances and anything cached at import time can outlive a run and be visible to the next run, or to one running at the same time. The first three rows were reproduced locally on 1.15.22-1.15.23 (see [references/concurrency-safe-crews.md](references/concurrency-safe-crews.md)).

| Do not | Why | Do instead |
|---|---|---|
| Write to `task.description` (or agent `role`/`goal`/`backstory`) at runtime, e.g. in `@before_kickoff` | crewai keeps the first-seen text as the template and re-interpolates from it. Two runs on one crew object: run 2's prompt carried run 1's customer and not its own | Put per-run values in `{placeholders}` and pass them as inputs; `@before_kickoff` may add or normalise **inputs** and return them |
| Keep per-run data on a tool instance (`self.seen`, `self.customer`) | `crew.copy()` (used by `kickoff_for_each`) reuses the same tool objects, so run 2 saw run 1's data | Keep tools stateless; pass per-run values as tool arguments, or read them from a `contextvars.ContextVar` set in `@before_kickoff` |
| Run two kickoffs at once on one `Crew` object | Overlapping `akickoff()` calls: the second raised `RuntimeError: Executor is already running. Cannot invoke the same executor instance concurrently.` Overlapping `kickoff_async()` calls raised it in some runs and not others In a few runs the run that survived had picked up the other run's inputs in a later task's prompt. | When you host crews yourself, build a fresh crew per request: `ResearchCrew().crew().kickoff(inputs=...)` |
| Store results, quotas, or "already processed" flags in memory or on local disk | They vanish on restart and are not shared between workers | Use storage you own (database, object store) and pass ids in inputs |
| Call `input()` in a deployed crew | Nobody is at a terminal to answer it, so the run cannot finish | Use `human_input=True` + `POST /resume`, or a Flow with `@human_feedback` |

Memory-heavy work (large files, big dataframes, local models, large knowledge bases) belongs in its own deployment, so it never competes with unrelated automations for memory. Stream or chunk large inputs instead of loading them whole, measure peak memory locally before deploying, and treat a run that stops with no error as a possible out-of-memory case to raise with CrewAI support.

Shared external limits still apply across concurrent runs: enforce per-minute API limits by waiting, and claim any daily quota in shared storage under a lock.

---

## 9. Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| `400` / `422` "Missing required inputs" on every call | Body is `{"topic": ...}` without the `inputs` wrapper | Send `{"inputs": {...}}` |
| `422` listing one key | A `{placeholder}` in agent or task text has no matching input | Send every key from `GET /inputs`; check for typos and stray braces |
| Locally: `Missing required template variable '...' in description` | Same as above, raised by crewai before any LLM call | Same |
| Output talks about `{topic}` literally | Kicked off with no / empty inputs - interpolation was skipped, no error | Validate inputs client-side; never send `{}` to a crew with placeholders |
| `/inputs` lists a key like `"title": "..."` | A JSON sample in a prompt is read as a placeholder | Remove JSON samples from prompts; use `output_pydantic` / `response_model` |
| `401` | Wrong token, or a token from another deployment | Copy the token from this deployment's Status tab |
| Poll loop never ends | Waiting for one exact string (`"completed"`) while the API returns `SUCCESS`, or no deadline | Lower-case, accept both vocabularies, add a deadline |
| Result is empty / `None` | Reading `result` before the state is terminal, or ignoring `result_json` | Read the result only after a success state; check `result_json` first |
| Duplicate runs | `POST /kickoff` retried after a read timeout | Retry only connection failures and `502`/`503`/`504` |
| First call times out, the next one works | Client timeout too short for a slow first response | Long first-call timeout, retries with `Retry-After`, start with `GET /inputs` |
| A run's prompt shows another run's customer or topic | Per-run data written into task text, tool instances, or globals | Section 8 |
| Webhook events arrive out of order | HTTP delivery is not ordered | Sort by `timestamp` |
| Resumed run stops sending webhooks | Webhook URLs are not carried over to `/resume` | Send the same `taskWebhookUrl` / `stepWebhookUrl` / `crewWebhookUrl` again in `/resume` |

---

## 10. Checklist

- [ ] Base URL and token come from env vars / a secret store; the token never reaches logs or a browser
- [ ] Client calls `GET /inputs` first and refuses to kick off with a missing key
- [ ] Kickoff body is `{"inputs": {...}}` with string values; `meta`, webhook fields and `restoreFromStateId` sit beside `inputs`
- [ ] `kickoff_id` is stored with your request id immediately
- [ ] Polling reads `state` then `status`, lower-cased, handles success / failure / paused, uses backoff and an overall deadline
- [ ] A deadline is reported with the `kickoff_id`, not retried as a new kickoff
- [ ] First request has a long timeout and retries `502`/`503`/`504` honoring `Retry-After`
- [ ] No runtime writes to task or agent text; per-run data flows through inputs
- [ ] Tools and module globals hold no per-run state
- [ ] Memory-heavy automations run in their own deployment

---

## References

- [Python client](references/python-client.md) - the full httpx client, usage, and a curl polling loop with a deadline
- [API contract](references/api-contract.md) - every endpoint, field, state and error with its public doc link
- [Concurrency-safe crews](references/concurrency-safe-crews.md) - the shared-state failures reproduced locally and the patterns that avoid them

For related skills:

- **deploy-to-amp** - getting the project onto AMP in the first place
- **build-flow** - `@persist`, `restore_from_state_id`, `@human_feedback`
- **design-task** - writing task text with `{placeholders}`
- **test-crewai-project** - running crews offline with a stub LLM to test inputs and prompts
- **ask-docs** - query the live docs when a field here looks out of date
