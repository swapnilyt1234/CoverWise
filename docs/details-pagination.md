# Sandbox details pagination repair

The user observed page 1/4 ending at an `excerpt` field. The previous presenter
sliced serialized JSON every 6,000 characters, so pages only parsed after being
concatenated. The previous test verified that concatenation rather than parsing
each displayed page separately.

The repair changes only `src/coverwise/sandbox_ui.py`, its tests in
`tests/test_sandbox.py`, documentation and required generated graph artifacts.
Provider access checks, read-only dispatch, transaction code, schema, authorization
and existing records are unchanged. Tests use temporary databases; the live
database was not opened. No `.env` access, agent startup, model/network calls,
dependencies or commits.

## Displayed format

Every details page contains one complete JSON object with:

- `reference`: the scoped quote/application/operation result reference.
- `page` and `total`: one-based page and page count.
- `records`: complete structured records identified by their `path` and `kind`.

Paths are arrays of object field names and integer array indices, relative to the
persisted snapshot (`state`, `quote`, `application`, `payment`). Empty path means
the snapshot root. Record kinds are:

| Kind | Meaning |
| --- | --- |
| `value` | A complete JSON value/subtree at `path`, in `value`. |
| `object` | Initialize an object at `path`; `length` counts its fields. Child records supply the fields. |
| `array` | Initialize an array at `path` of the stated `length`. Child records supply its indices. |
| `string_segment` | Part of a string at `path`: `value`, zero-based `offset` and `total_characters`. |

To reconstruct, initialize containers and assign complete values at their paths.
For each segmented string, order its records by offset and concatenate `value`;
offsets must cover zero through `total_characters` without gaps or overlaps.
Offsets count Python/Unicode string characters, not UTF-8 bytes. Original strings,
including excerpt whitespace, quotes, backslashes and Unicode, are preserved
exactly after JSON decoding. No evidence is silently omitted.

Complete records are packed into pages. Oversized objects/arrays are represented
by containers plus their children; oversized strings are split only into explicit
string-segment records. The presenter measures serialized JSON and the entire
rendered reply, including the sandbox label, metadata, JSON/text fences, both
navigation commands and status command. The existing 12,000-character limit is
also enforced as 12,000 UTF-8 bytes. It reserves navigation for two-digit page
numbers before packing, respecting the existing 64-page input bound. Unrepresentable
results fail explicitly as `result_too_large` rather than dropping records.

Each page includes the actual previous/next commands when applicable and the
existing scoped status command. An invalid page has an independently parseable
JSON error envelope with an empty records list, `page_out_of_range`, actual total
and a recovery command for page one. Page counts may differ from the old slicing;
start at page one and copy the returned navigation commands.

The explicit snapshot whitelist excludes plaintext approval challenges and
approval commands. Historical approval expiry remains labelled as metadata.
Details never reconciles an unknown payment or resumes an approved operation;
those existing semantics remain confined to the status command.

## Verification

The updated real-Provider test parses every displayed pending-application page
with `json.loads`, reconstructs and compares the complete application/payment
record (including all original evidence), checks navigation and size bounds, and
confirms the pending payment stays unchanged until explicit status reconciliation.
Existing sender/session isolation tests remain intact for quote, application and
operation references.

New cases exercise oversized excerpts containing Unicode, quotes, backslashes,
newlines, tabs and Markdown fences; every page parses and reconstructs the exact
original quote/excerpt. A small single-page snapshot and out-of-range JSON recovery
are also checked. Input data is not mutated by presentation.

| Exact command | Actual result |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest -q tests/test_sandbox.py -k details` | Exit 0; 16 passed, 55 deselected, in 16.67s. |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0; **290 passed in 72.96s**, no skips. |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; all checks passed. |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; 45 files already formatted. |
| `graphify update .` | Exit 0; 678 nodes, 2,119 edges, 36 communities; AST-only, no model calls. |
| `graphify diagnose multigraph --max-examples 1` | Exit 0; no missing/dangling endpoints, duplicate edges or same-endpoint collapses; one recursive self-call edge. |

Required graph query/path/explain operations were used; the presenter calls the
structured-record builder directly. Semantic docs/PDFs were not rebuilt. Graph
community names use hub fallbacks without an LLM. Git remains the existing
untracked project tree; nothing staged or committed. No dependency blocker.

Live corrected pagination remains pending user observation; no live agent was
started here. Existing user-observed completion/restart recovery remains recorded
separately; live duplicate-purchase verification and PDF visual review remain
unconfirmed.
