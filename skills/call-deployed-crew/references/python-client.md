# Python Client for a Deployed Crew

A small, dependency-light client (httpx) for the public AMP deployment API, plus the same flow in curl. Save the Python block as `deployed_crew_client.py`.

What it does, and why:

| Behaviour | Prevents |
|---|---|
| `run()` calls `GET /inputs` first and refuses to kick off with a missing key | `422` round trips, and silent runs where `{placeholder}` text reaches the model |
| Wraps values in `{"inputs": {...}}` and sends non-strings as JSON strings | the bare-body `400` / `422`; type surprises (the API documents input values as strings) |
| Long timeout on the first request, then the normal timeout | failing on a slow first response |
| Retries `502` / `503` / `504` honoring `Retry-After`, and connection errors | giving up on a transient gateway error |
| Never retries `POST /kickoff` after a read timeout, `502` or `504` | duplicate runs |
| Reads `state`, then `status`, lower-cased; accepts both documented vocabularies | poll loops that never see `"completed"` |
| Reads `result_json`, then `result` / `result.output` | empty results |
| Backoff with jitter under an overall deadline | unbounded polling |
| Raises `RunFailed` / `RunPaused` / `RunTimeout` with `.kickoff_id` and `.payload` | losing the only handle to a run |
| Never puts the token in an error message | leaking credentials into logs |

---

## 1. The client

```python
"""Minimal client for a crew or flow deployed on CrewAI AMP.

pip install httpx
export CREWAI_DEPLOYMENT_URL="https://<your-deployment>.crewai.com"
export CREWAI_DEPLOYMENT_TOKEN="<your-bearer-token>"
"""
from __future__ import annotations

import json
import os
import random
import time
from typing import Any

import httpx

SUCCESS = {"success", "completed"}
FAILURE = {"failed", "failure", "error", "revoked"}
PAUSED = {"paused"}
RETRYABLE_STATUS = {502, 503, 504}


class DeployedCrewError(Exception):
    """Base class. Every subclass carries the kickoff_id when there is one."""

    def __init__(self, message: str, kickoff_id: str | None = None, payload: Any = None):
        super().__init__(message)
        self.kickoff_id = kickoff_id
        self.payload = payload


class MissingInputsError(DeployedCrewError): ...
class RunFailed(DeployedCrewError): ...
class RunPaused(DeployedCrewError): ...       # waiting for human feedback (POST /resume)
class RunTimeout(DeployedCrewError): ...      # deadline passed; the run may still be going


class DeployedCrew:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        request_timeout: float = 30.0,     # normal calls
        first_call_timeout: float = 180.0,  # the first response can be slow; allow for it
        retries: int = 4,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.first_call_timeout = first_call_timeout
        self.retries = retries
        self._warm = False
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {token}"},  # never log this header
            timeout=httpx.Timeout(request_timeout, connect=10.0),
        )

    # -- low level -------------------------------------------------------
    def _request(self, method: str, path: str, *, retry_on_timeout: bool, **kw) -> httpx.Response:
        timeout = self.request_timeout if self._warm else self.first_call_timeout
        for attempt in range(self.retries + 1):
            try:
                resp = self._http.request(method, self.base_url + path, timeout=timeout, **kw)
            except httpx.ConnectError:
                # The request never reached the server, so a retry cannot duplicate work.
                if attempt == self.retries:
                    raise
                time.sleep(min(2 ** attempt, 30))
                continue
            except httpx.TimeoutException:
                # A POST /kickoff that timed out may still have started a run:
                # do not resend it blindly.
                if not retry_on_timeout or attempt == self.retries:
                    raise
                time.sleep(min(2 ** attempt, 30))
                continue
            # POST /kickoff (retry_on_timeout=False): after a 502 or 504 the run may have
            # started, so only a 503 is resent.
            if resp.status_code in RETRYABLE_STATUS and attempt < self.retries and (
                retry_on_timeout or resp.status_code == 503
            ):
                retry_after = resp.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else min(2 ** attempt, 30)
                time.sleep(delay)
                continue
            self._warm = True
            return resp
        raise AssertionError("unreachable")

    @staticmethod
    def _json_or_raise(resp: httpx.Response, what: str, kickoff_id: str | None = None) -> Any:
        if resp.status_code == 401:
            raise DeployedCrewError(f"{what}: 401 - check the bearer token", kickoff_id)
        if resp.status_code >= 400:
            raise DeployedCrewError(
                f"{what}: HTTP {resp.status_code}: {resp.text[:500]}", kickoff_id, resp.text
            )
        return resp.json()

    # -- API -------------------------------------------------------------
    def get_inputs(self) -> list[str]:
        """GET /inputs -> {"inputs": [...]}. Read-only, so safe to retry."""
        resp = self._request("GET", "/inputs", retry_on_timeout=True)
        return list(self._json_or_raise(resp, "GET /inputs").get("inputs", []))

    def kickoff(self, inputs: dict[str, Any], *, required: list[str] | None = None, **top_level: Any) -> str:
        """POST /kickoff with {"inputs": {...}}. Returns the kickoff_id.

        top_level: optional documented siblings of "inputs", e.g. meta=...,
        crewWebhookUrl=..., restoreFromStateId=... (flows).
        """
        if required is not None:
            missing = [k for k in required if k not in inputs]
            if missing:
                raise MissingInputsError(f"missing required inputs: {missing}")
        # The documented schema types every input value as a string.
        body = {
            "inputs": {
                k: v if isinstance(v, str) else json.dumps(v) for k, v in inputs.items()
            },
            **top_level,
        }
        resp = self._request("POST", "/kickoff", json=body, retry_on_timeout=False)
        data = self._json_or_raise(resp, "POST /kickoff")
        return data["kickoff_id"]

    def status(self, kickoff_id: str) -> dict[str, Any]:
        resp = self._request("GET", f"/status/{kickoff_id}", retry_on_timeout=True)
        if resp.status_code == 404:
            return {"state": "not_found"}
        return self._json_or_raise(resp, "GET /status", kickoff_id)

    @staticmethod
    def state_of(payload: dict[str, Any]) -> str:
        # Platform guide: "state" (PENDING/RUNNING/SUCCESS/FAILED/PAUSED/...) and
        # "status" is a message. API reference: "status" is running/completed/error.
        return str(payload.get("state") or payload.get("status") or "").strip().lower()

    @staticmethod
    def result_of(payload: dict[str, Any]) -> Any:
        if payload.get("result_json") is not None:
            return payload["result_json"]
        result = payload.get("result")
        if isinstance(result, dict) and "output" in result:  # API-reference shape
            return result["output"]
        return result

    def wait(
        self,
        kickoff_id: str,
        *,
        deadline_s: float = 900.0,
        first_interval: float = 2.0,
        max_interval: float = 15.0,
        not_found_grace: int = 3,
    ) -> dict[str, Any]:
        """Poll GET /status/{kickoff_id} until a terminal state or the deadline."""
        deadline = time.monotonic() + deadline_s
        interval = first_interval
        not_found = 0
        while True:
            payload = self.status(kickoff_id)
            state = self.state_of(payload)
            if state in SUCCESS:
                return payload
            if state in FAILURE:
                err = payload.get("error") or payload.get("status") or payload.get("result")
                raise RunFailed(f"run {kickoff_id} ended {state}: {err}", kickoff_id, payload)
            if state in PAUSED:
                raise RunPaused(f"run {kickoff_id} is waiting for human feedback", kickoff_id, payload)
            if state == "not_found":
                not_found += 1
                if not_found > not_found_grace:
                    raise DeployedCrewError(f"kickoff_id {kickoff_id} not found", kickoff_id)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RunTimeout(
                    f"run {kickoff_id} not finished after {deadline_s}s (last state {state!r})",
                    kickoff_id, payload,
                )
            time.sleep(min(interval * random.uniform(0.8, 1.2), remaining))
            interval = min(interval * 1.5, max_interval)

    def run(self, inputs: dict[str, Any], **wait_kw: Any) -> Any:
        """Validate against /inputs, kick off, wait, return the result."""
        required = self.get_inputs()  # also absorbs a slow first response, safely
        kickoff_id = self.kickoff(inputs, required=required)
        return self.result_of(self.wait(kickoff_id, **wait_kw))

    def close(self) -> None:
        self._http.close()


if __name__ == "__main__":
    crew = DeployedCrew(os.environ["CREWAI_DEPLOYMENT_URL"], os.environ["CREWAI_DEPLOYMENT_TOKEN"])
    try:
        print(crew.run({"topic": "AI agents", "audience": "engineers"}))
    except RunTimeout as e:
        print(f"timed out; check later with GET /status/{e.kickoff_id}")
        raise
    finally:
        crew.close()
```

---

## 2. Usage

```python
import os
from deployed_crew_client import DeployedCrew, RunFailed, RunPaused, RunTimeout

crew = DeployedCrew(os.environ["CREWAI_DEPLOYMENT_URL"], os.environ["CREWAI_DEPLOYMENT_TOKEN"])
try:
    required = crew.get_inputs()                       # e.g. ["topic", "audience"]
    kickoff_id = crew.kickoff(
        {"topic": "AI agents", "audience": "engineers"},
        required=required,
        meta={"requestId": "req-123"},                 # sits beside "inputs"
    )
    save_kickoff_id("req-123", kickoff_id)             # your storage: do this before polling
    payload = crew.wait(kickoff_id, deadline_s=900)
    print(DeployedCrew.result_of(payload))
except RunFailed as e:
    print("failed:", e, e.payload)
except RunPaused as e:
    print("needs human feedback via POST /resume:", e.kickoff_id)
except RunTimeout as e:
    print("still running; poll GET /status later:", e.kickoff_id)
finally:
    crew.close()
```

Pick `deadline_s` from how long the crew normally takes plus headroom; the default is 15 minutes. A `RunTimeout` means your client stopped waiting, not that the run failed.

---

## 3. curl with a deadline

Needs `curl` and `jq`. Pass the inputs as a JSON object in the first argument.

```bash
#!/usr/bin/env bash
# Kick off a deployed crew and poll until it finishes or a deadline passes.
# Needs: curl, jq. Never echo $CREWAI_DEPLOYMENT_TOKEN.
set -euo pipefail
: "${CREWAI_DEPLOYMENT_URL:?set CREWAI_DEPLOYMENT_URL}" "${CREWAI_DEPLOYMENT_TOKEN:?set CREWAI_DEPLOYMENT_TOKEN}"
AUTH="Authorization: Bearer $CREWAI_DEPLOYMENT_TOKEN"
DEADLINE_S="${DEADLINE_S:-900}"
DEFAULT_INPUTS='{"topic": "AI agents", "audience": "engineers"}'
INPUTS_JSON="${1:-$DEFAULT_INPUTS}"

# 1. Required keys (read-only: safe to retry, long timeout for a slow first call)
required=$(curl -sS --fail --max-time 180 --retry 4 --retry-connrefused \
  -H "$AUTH" "$CREWAI_DEPLOYMENT_URL/inputs" | jq -c '.inputs')
missing=$(jq -nc --argjson req "$required" --argjson got "$INPUTS_JSON" '$req - ($got | keys)')
[ "$missing" = "[]" ] || { echo "missing inputs: $missing" >&2; exit 2; }

# 2. Kickoff: wrap in {"inputs": ...}; no retry on timeout (it may have started)
kickoff_id=$(jq -nc --argjson i "$INPUTS_JSON" '{inputs: ($i | map_values(tostring))}' |
  curl -sS --fail-with-body --max-time 60 -X POST "$CREWAI_DEPLOYMENT_URL/kickoff" \
    -H "$AUTH" -H "Content-Type: application/json" --data @- | jq -r '.kickoff_id')
echo "kickoff_id=$kickoff_id" >&2

# 3. Poll with backoff under an overall deadline
end=$(( $(date +%s) + DEADLINE_S )); sleep_s=2
while :; do
  body=$(curl -sS --max-time 30 --retry 3 -H "$AUTH" "$CREWAI_DEPLOYMENT_URL/status/$kickoff_id")
  state=$(jq -r '(.state // .status // "") | ascii_downcase' <<<"$body")
  case "$state" in
    success|completed) jq -r '.result_json // (.result | if type == "object" then .output else . end)' <<<"$body"; exit 0 ;;
    failed|failure|error|revoked) echo "run $kickoff_id ended $state: $(jq -c '.error // .status' <<<"$body")" >&2; exit 1 ;;
    paused) echo "run $kickoff_id is waiting for human feedback (POST /resume)" >&2; exit 3 ;;
  esac
  [ "$(date +%s)" -lt "$end" ] || { echo "deadline passed; run $kickoff_id may still be going (last: $state)" >&2; exit 4; }
  sleep "$sleep_s"; sleep_s=$(( sleep_s < 15 ? sleep_s * 3 / 2 + 1 : 15 ))
done
```

Exit codes: `0` success (result on stdout), `1` run failed, `2` missing inputs, `3` paused for human feedback, `4` deadline passed (the run may still be going), anything else is a curl error such as `22` for an HTTP error status.

`curl --retry` retries timeouts and `408` / `429` / `500` / `502` / `503` / `504` and honors `Retry-After`; it is used only on the read-only calls. The kickoff call has no `--retry`.
