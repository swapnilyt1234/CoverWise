# Recommendation timing repair — 2026-10-24

## Confirmed findings and unresolved live hypotheses

The user observed normal requests acknowledged, Provider successful, Investigator
delivery successful, then either success or timeout followed by ignored_response.
One failed Investigator request was `f7ec16a1-0b65-4e4a-9e3e-5444531d5b05`.
Reported whole-chat durations were approximately 4.9–6.5 seconds. Deliberate
Provider `test_silence` requests are separate failures and are tagged separately.

Confirmed locally:

- Recommendation work launched four or five fresh Python interpreters in sequence.
  Repeated startup dominated these small PDF extractions, with no assessment cache.
- Before repair, actual-PDF engine work took 3.156 seconds (four processes) for the
  preset and 3.422 seconds (five processes) with existing personal cover.
- A controlled local A/B run restored only the former per-document launch path
  while keeping the same coordinator, SDK handlers, session and three-second
  deadline. Existing-cover work timed out at 3.016553 seconds, finished and sent its
  rejected late response by 3.307286 seconds. Switching to the repaired batch path
  succeeded at 0.644590 seconds with the same deadline and rules.
- The old late-result cleanup was correct to reject a response after timeout;
  generic ignored_response logs concealed the exact reason. Explicit deadline
  checks also now prevent a late result from winning a delayed timer race.
- Core assessment/PDF work was already offloaded with asyncio.to_thread. There is
  no evidence that synchronous PDF parsing on the event loop caused these failures.
  Result packaging/presentation is now included in that offloaded work too.
- The installed SDK queue schedules concurrent handlers when configured; both the
  coordinator and internal-agent runtime already set that option. No SDK lifecycle
  or routing rewrite was needed.

The exact effective deadline for the reported live failed UUID is **unconfirmed**.
We did not inspect `.env`, credentials or the running live process. LiveSettings
defaults to 15 seconds and explicitly passes it into Coordinator; Coordinator's
legacy standalone default is 3 seconds, and the offline CLI default is 15. The
same self.timeout drives both recommendation delegation stages. `load_dotenv` uses
override=False, so an inherited process value wins over a file/default; stale
configuration or an old process remains a plausible live contributor, not a proven
cause. SDK dispatch/transit delay and live load are also not measured here.

**No timeout defaults or configured values were increased by this repair.**

## Repair and operational logging

Later [quote extraction repair](quote-extraction-repair.md) separates batch-worker
startup from PDF deadlines with a bounded readiness handshake. The two-second
per-document parsing budget and outer delegation deadlines remain unchanged.

`policies.inspect_policies` launches one bounded child interpreter for up to five
allowlisted policy IDs. It sends a one-byte start signal for each PDF only after
arming that PDF's existing two-second parent deadline. Each `load_policy` creates
a fresh PdfReader and verifies real bytes, hash, pages and clause evidence. No PDF
parser object is shared across workers, no decision/term is cached, and no plan
name controls the assessment. The pipe reader uses a bounded queue and bounded
frames. Oversize/invalid/incorrect-document/error/timeout results fail closed; no
partial list is returned. On failure the child is killed/reaped and its pipes and
reader are closed. Existing single-policy inspection is unchanged.

The Investigator admits one recommendation job at a time, with at most 16 queued
recommendation handlers. Other async work remains responsive. Assessment,
serialization, presentation validation and byte limits run off the event loop.
A running job is shielded from SDK-handler cancellation, retained strongly, and
releases its lane only when its work actually finishes. A cancelled handler does
not send a result. Coordinator timeout does not pretend to cancel a remote worker:
that worker may finish later and its response remains rejected. A process/loop
shutdown can still wait for bounded subprocess work to drain; threads cannot be
forcibly killed safely.

Coordinator logs use monotonic durations and include stage, request/session IDs,
configured deadline, elapsed timeout time, injection flag and pending cleanup.
Replies are checked against their deadline before and after existing sender,
session, request type, inputs, catalogue and evidence validation. Nothing accepts
expired responses. A bounded history of the last 128 closed IDs records stage and
reason only. Ignored-response reasons include expired, unknown_id, sender_mismatch,
session_mismatch, duplicate, cancelled, and validation-specific mismatch reasons.
IDs older than that history are honestly classified unknown_id.

Operational events to capture:

| Event | Useful fields |
| --- | --- |
| configuration | request_timeout_seconds, timeout_source=LiveSettings, dotenv_override=False |
| delegation_start | stage, request_id, session, deadline_s, started_monotonic, injection |
| handler_received | stage, request_id, session, received_monotonic, injection |
| assessment_admitted | queue_scope=assessment_lane, queue_wait_ms |
| assessment_started | executor_wait_ms |
| assessment_finished / catalogue_finished | assessment_duration_ms |
| response_send | response_send_ms |
| delegation_timeout | deadline_s, elapsed_ms, injection |
| pending_cleanup | outcome, pending_removed, future_cancelled, injection |
| ignored_response | reason and stage, including for recently expired IDs |
| worker_cleanup | lane_released, handler_cancelled, worker_cancelled, error_type |

The measured queue wait is the application recommendation lane, not an invented
SDK enqueue measurement. Same-process coordinator/handler monotonic markers help
locate dispatch/transit delay. Executor wait is separate. Logs never include
profiles, disclosures, document text, full payloads, credentials or seeds.

## Actual timing measurements

Artifacts: `output/timing-before.json`, `output/timing-after.json`,
`output/timing-ab.json`, and operational-only `output/timing-ab.log`.

| Work | Before | After: three runs | PDF processes per request |
| --- | ---: | --- | --- |
| Preset engine | 3.156 s | 0.667677, 0.641832, 0.652121 s | 4 → 1 |
| Existing-cover engine | 3.422 s | 0.701532, 0.650537, 0.648404 s | 5 → 1 |

A real-PDF SDK-handler harness retained one coordinator and one session with a
three-second deadline through this sequence:

| Request | Observed result | Elapsed |
| --- | --- | ---: |
| Normal preset | success | 0.615715 s |
| Intentional Provider silence | timeout; zero PDF processes | 3.008669 s |
| Normal existing-cover preset | success | 0.675623 s |
| Normal preset again | success | 0.624927 s |

Pending state was empty after every request. All successful requests used actual
fresh PDF extraction and retained the expected recommendation outcomes. These are
local engine/handler times, not ASI:One network or whole-chat latency, and the
harness does not construct SDK agents or establish live transport reliability.

## Verification and scope

| Exact command | Executed result |
| --- | --- |
| `uv lock --check --offline` | Exit 0; resolved 69 packages in 2ms using the approved existing cache |
| `.\.venv\Scripts\python.exe -m coverwise.doctor` | Exit 0; Python 3.12.0, uagents 0.25.5, core 0.4.12, ACP 0.3.0 |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0; **219 passed in 25.27s**, no skips |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; all checks passed |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; 34 files already formatted |
| `graphify update .` | Exit 0; **504 nodes, 1494 edges, 11 communities** |
| `graphify diagnose multigraph --max-examples 1` | Exit 0; no missing/dangling endpoints, self-loops, duplicates or collapsed same-endpoint edges in saved graph |

The original 200 cases remain passing, with 19 focused new regression cases.
Regression tests cover both effective deadlines; process-over-dotenv precedence
without reading a file; startup numeric logging; async responsiveness during slow
packaging; running-worker cancellation/lane safety; timeout cleanup; late-reply
reasons and timer races; repeated concurrent inputs/sessions; normal recovery after
deliberate silence; bounded request history; real PDF batch extraction; framing,
identity, byte limits, errors, child termination and pipe cleanup. Oversized test
frames use bounded pytest IDs to avoid Windows filename limits; their validation
data and limits were not weakened. Graph query/path/explain and the required AST
refresh were executed. No optional semantic PDF indexing or SDK network startup
was performed. The saved-graph diagnostic cannot prove absence of earlier
producer-side edge loss. Git status remains an untracked, unstaged source tree;
nothing was staged or committed.

Changed runtime files: policies.py (bounded extraction), recommend.py (batch
selection), agents.py (admission, lifecycle, logging), provider.py (timing/injection
logging), live.py (effective startup timeout logging). Runtime receiver setup,
identities, seeds, SDK pins, policy sources, PDFs and recommendation rules are
unchanged. No dependencies were added. No `.env` access/modification, live startup,
network calls, publication, staging, commit or purchase work occurred. PDF visual
review remains unconfirmed and was not part of this timing repair.

## User action and exact live retest

Restart the existing live process yourself to load the repaired code. Check
`event=configuration request_timeout_seconds=...` against the value you intend.
An existing shell setting overrides dotenv because override=False; do not share
the file or seed/key values. There is no blanket timeout-increase instruction:
the local repaired sequence succeeded with three seconds, while production keeps
its existing configuration and 15-second default.

In the same ASI:One conversation, send:

```text
/recommend preset
/recommend-timeout preset
/recommend preset
/recommend preset-existing
/recommend preset
/recommend-evidence candidate-horizon 3 preset
```

Normal requests should log injection=False and complete both stages. Only the
intentional test should log Provider test_silence with injection=True and then
timeout. Capture configuration plus the stage/worker/cleanup events above for any
remaining normal failure. Do not infer current success from old requests or accept
late replies as current. Live reliability after this repair remains pending.
