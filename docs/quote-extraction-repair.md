# Quote extraction startup deadline repair

## Confirmed cause

User observed `/quote preset` rejected with `extraction_timeout`, operation
`op-a650baac2d7d48c3944a43e9aeeb1e4f`. No live database was opened to inspect it.

The current path is Coordinator typed `SandboxRequest` → Provider SDK handler →
`SandboxProvider.execute` → quote terms → `recommend.run` →
`policies.inspect_policies`. It already uses one batch interpreter for the
employer PDF and three candidate PDFs, not the older one-process-per-PDF path.
However, its first two-second PDF deadline started immediately after `Popen`,
before interpreter/Pydantic/pypdf startup had finished. The first PDF's extraction
budget therefore also paid for startup.

Local measurement with real PDFs observed parent-to-ready startup of **3.281 s**
(child imports **3.219 s**), then **16–47 ms** per PDF. Two subsequent startups
took **0.844 s / 0.891 s**. These are observed local samples, not a live latency
guarantee. Through the actual Provider SDK handler and temporary SQLite, a
controlled 2.1-second startup delay reproduced `rejected / extraction_timeout`
before repair: **1 failed, 3 deselected** in 17.93 s. The Provider operation itself
returned after **2.094 s**, before a quote existed.

## Small repair

The existing batch child imports pypdf and emits an exact versioned readiness
frame before accepting a PDF start signal. Its parent allows **five seconds for
startup**, including process creation and imports, independently of the unchanged
**two seconds per PDF**. Five seconds accommodates the observed 3.281-second cold
startup with bounded headroom; it does not increase coordinator deadlines or PDF
parsing deadlines. Startup, per-document extraction and timeout stages log only
operational timing/deadlines and allowlisted document IDs using monotonic time.

The bounded framing/queue, fresh parser per PDF, real-byte hash/evidence checks,
child kill/wait/pipe cleanup, and fail-closed behavior remain. No retries, cached
decisions, alternate extraction, database schema, authorization, pricing, quote
expiry or purchase-approval changes. Single-policy `/inspect` is unchanged.

## Actual Provider measurements after repair

Tests mock no extraction or assessment results. Only a test child bootstrap
redirects the fixed registry to temporary, freshly generated PDFs. The normal
Provider SDK handlers and actual assessor create quotes in temporary SQLite.

| Case | Three quote operations, ms | Worker startup, ms | Per-PDF extraction, ms |
| --- | --- | --- | --- |
| Normal repeated `/quote preset` | 1281, 1250, 1140 | 1063, 1062, 968 | 15–47 |
| Deliberate 2.1 s delay on first startup only | 3250, 1109, 1219 | 3032, 953, 1047 | 15–32 |

Each case persisted **three distinct quotes, zero payments**, with one batch
worker per quote and the expected computed **₹22,000 annual premium**. Quote
evidence hashes equal the actual generated PDF bytes. Delayed startup did not
consume the per-PDF deadline.

Malformed PDF and deliberately slow extraction each produced an authoritative,
persisted rejection. Status retrieved the same error, with **zero quotes and zero
payments**, and exactly one child launch: no silent retry or partial quote.
Separate protocol tests cover bounded startup timeout, bounded extraction timeout,
child cleanup, dependency failure, invalid readiness/report frames, order and IDs.

Verification executed locally:

- `.\.venv\Scripts\python.exe -m pytest -q -s tests/test_quote_workers.py tests/test_policy_pdf.py`:
  **26 passed in 23.49 s**.
- `.\.venv\Scripts\python.exe -m pytest -q`: **382 passed in 90.77 s**.
- `.\.venv\Scripts\python.exe -m ruff check .`: **passed**.
- `.\.venv\Scripts\python.exe -m ruff format --check .`: **passed** (final run: 57 files already formatted).
- `graphify update .`: AST-only rebuild, **867 nodes / 2,637 edges / 43 communities**.
  `graphify diagnose multigraph --max-examples 1` found no missing/dangling endpoints,
  duplicate edges or collapsed edges; one existing recursive self-call remains.

Git status retains the pre-existing untracked project paths; nothing was staged
or committed.

No live agents, network/model calls, live database access, dependency upgrades,
secret-file reads, resets, staging or commits were performed.

## Restart and live retest

Stop the old local process with **Ctrl+C**, then from PowerShell:

```powershell
Set-Location C:\Users\swapn\Desktop\coverwise
.\.venv\Scripts\python.exe -m coverwise.live
```

Keep existing configuration, seeds, identities and database. No reinstall, reset
or SDK change is needed. In the same ASI:One conversation, inspect the reported
operation's recorded outcome if needed:

```text
/sandbox-status op-a650baac2d7d48c3944a43e9aeeb1e4f
```

Its previous rejected result is preserved. Then request a **new** synthetic quote:

```text
/quote preset
```

Repeat `/quote preset` to check repeated requests. Expect active quotes and the
existing waiting-period limitation. Copy any subsequent apply command from the
fresh reply; review and explicit approval remain separate. Live retest is pending.
If startup exceeds five seconds or PDF parsing exceeds two seconds, extraction
still fails honestly; logs distinguish the stage. The existing outer delegation
deadline also still applies under load.
