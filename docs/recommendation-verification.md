# Candidate recommendation verification — 2026-10-24 local

The user reports ASI:One confirmation of the existing stress preset, July 31
personal waiting exclusion, and December 30 document/scenario mismatch. Those
observations supersede the older pending stress-test record. They do not establish
live Provider cooperation or visual PDF review. Employer `/inspect` remains
separate from those stress observations and has not been independently confirmed.

## Executed checks

| Command | Actual observation |
| --- | --- |
| `uv lock --check --offline` | Exit 0; 69 packages resolved in 57ms; approved access to existing uv cache outside workspace |
| `.\.venv\Scripts\python.exe -m coverwise.doctor` | Exit 0; Python 3.12.0; uagents 0.25.5; core 0.4.12; ACP 0.3.0 |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0; **200 passed in 23.17s**, no skips |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; all checks passed |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; 34 files already formatted on final observed check |
| `.\.venv\Scripts\python.exe -m coverwise.generate_policies` | Exit 0; existing employer 3 pages, existing personal 4 pages, all three candidates 4 pages each; generated candidate hashes match versioned catalogue |

The previous 147 regression cases remain passing; 53 new cases cover budget/age
boundaries, dependants and disclosures, unknown terms, new waiting durations and
leap days, identical scenarios, changed requirements/dates/PDFs, source disagreement,
retention/no-option paths, snapshot/evidence binding, Provider failure and silence,
timeout/cancellation cleanup, ACP evidence access, output bounds and seed validation.
Consequential tests generate and extract actual PDFs in temporary directories.
No pytest case constructs a live SDK Agent or makes live network calls.

The existing invalid-timeout tests now supply the required Provider seed, so they
continue testing the timeout validator. No validation was weakened. One early
CLI experiment exposed duplicate `__main__`/canonical model identities; the CLI
now calls its canonical entry point. Final offline runs succeeded through actual
typed SDK handlers with lightweight contexts, not actual live-agent transport.

## Actual offline examples

All run through `python -m coverwise.recommend` with structured Catalogue and
CandidateAssessment requests/results, Provider tools, actual PDF extraction and
Investigator evaluation. The harness does not construct agents or start services.
Recorded stdout and command metadata are in `output/recommend-*`.

| Exact command suffix | Exit | Observed result | Stdout bytes |
| --- | ---: | --- | ---: |
| `preset` | 0 | Horizon prospective shortlist; Economy rejected; Query clarification; all immediate events excluded | 3182 |
| `preset-low` | 0 | No suitable option; budget 1,000,000 paise | 3308 |
| `preset-clarify` | 0 | Provider clarification required; Query within 2,000,000 budget but room unknown; Horizon over budget | 3164 |
| `preset-existing` | 0 | Existing personal retained; obtain missing terms; no new shortlist/duplicate recommendation | 3855 |
| `preset --provider-timeout` | 2 | Incomplete (`timeout`), no catalogue fallback, no fabricated recommendation | 93 |
| `preset --json` | 0 | Full inputs, catalogue snapshot, assessments and unchanged evidence | 91509 |

Normal budget is 3,000,000 paise; minimum family limit 100,000,000; room is uncapped
private single. Proposed start is January 1, 2027; final employment December 31,
2026; assumed new employer start February 1, 2027. Both synthetic adults declare
conditions absent. Immediate illness event is for member-02 on January 15; the
separate later event is February 10, applied to every policy and baseline.

The employer policy excludes both events after its December 31 ending. Its
January 1–31 employer-protection gap is unchanged. Economy's ₹5,00,000 family
limit and ₹3,000/day room cap fail stated requirements despite its ₹12,000 list
premium. Query's ₹18,000 price and ₹10,00,000 limit do not resolve its absent
room schedule. Horizon's ₹22,000 price, ₹10,00,000 shared family limit and uncapped
private room meet prospective requirements, subject to eligibility and exclusions.
Its fresh January 1–30 illness wait excludes January 15; January 31 is the first
post-wait day, and February 10 is conditional rather than guaranteed coverage.

The existing-cover path retains personal policy findings, including its expired
initial wait on the preset event, ₹2,00,000 shared family limit, ₹3,000/day room cap,
appendicitis-scoped terms and missing pre-existing-condition terms. Retained
₹6,000 annual premium makes Horizon's possible combined premium ₹28,000 within
the ₹30,000 budget, but the result does not automatically recommend buying it or
replacing existing cover. Existing premiums count toward budget; benefits do not
automatically stack. Adverse existing-cover dates remain adverse, as tested.

## Source evidence from observed preset

| Fact | Actual PDF evidence |
| --- | --- |
| Economy family limit | p1 ECO-01 `ev-3c1e50bbccddcf87dda4f4f6` |
| Economy daily room cap | p2 ECO-02 `ev-c2090ef943cae22baff969ef` |
| Query unknown room schedule | p2 QUE-02 `ev-4a48c7e398b7fca517abfccb` |
| Horizon family limit | p1 HOR-01 `ev-7ef1fdf6e465d30a4a17bab5` |
| Horizon uncapped private room | p2 HOR-02 `ev-6ef5401333913e0aa18a9447` |
| Horizon entry rules | p2 HOR-02 `ev-2d4a2e4b452f2f3f017fb057` |
| Horizon fresh 30-day waiting rule | p3 HOR-03 `ev-8f7b4e6a7a905539ebc9a470` |

Candidate byte hashes, version 1:

```text
candidate-economy 053062f335c750ac313fc9f608db484a60c6ea7dc0ab5e4f8f47cad68905a6f8
candidate-query 64636a7b09a12209f10aaeca64a4d6f3716abfed9d46e7c30d43bbf4c1a4a04a
candidate-horizon 1be9dd15f828d1c35733ce48ba111d712133656d282353678ba1d615829d0dd7
```

The existing employer hash remains
`e3510d1ab552e25a85d3fe9fbbb616d1082b65177d76b5dd5469569df13ada99`;
existing personal remains
`8ceeaf6224499d4eb8de4d62f3444a161608260505573abcee7353800c8f7760`.
Canonical integer paise and evidence excerpts were not rewritten for rupee display.

## Runtime, visual review, graph and pending work

Sequential extraction of the existing-cover case was measured at 6.243 seconds;
concurrent workers hit `extraction_timeout`. The final implementation stays
sequential, preserving each two-second PDF worker limit. The existing live timeout
setting now defaults to 15 seconds, range 0.05–30. Explicit settings are honored;
an old three-second setting can time out during this larger workflow. Offline
normal handlers use 15 seconds; deliberate silence uses a 0.05-second test bound.
Nothing in a configuration file was opened or changed.

PDF authoring marker ran successfully once for three new outputs. All documents
generated and extracted, but no renderer was available: `pdftoppm` and `mutool`
were absent from PATH, and `.venv` lacks `fitz`/PyMuPDF and `pypdfium2`. No extra
dependency was installed. **Visual review of all existing and candidate pages
remains unconfirmed**, not passed. Inspect them locally or supply rendering tooling
in a later verification step. Text extraction is not visual QA.

Required graph query/path/explain, code update and saved-graph diagnostics were
executed: **450 nodes, 1373 edges, 11 communities**. The saved-graph diagnostic
reported zero missing/dangling endpoints, self-loops, duplicates or collapsed
same-endpoint edges. Graphify's separate
environment warns that pypdf is unavailable; application extraction succeeds in
`.venv`. The graph update covers code relationships, not semantic PDF/doc indexing.
Hub-based community naming does not call an LLM. Saved-graph diagnostics do not
prove absence of earlier producer-side edge loss. Git remains an untracked,
unstaged source tree; nothing was staged or committed.

No `.env` access/modification, seed generation, identity changes, SDK pin changes,
live startup, registration or publication occurred. No dependencies were added.
Provider construction is implemented but was never executed here. Live three-agent
success remains **pending user observation**. The existing SDK constructor's
outbound behavior still prevents treating a real Agent constructor as offline.

## Next user-run ASI:One checks

Configure the existing names locally: `ASI1_API_KEY`,
`COVERWISE_PERSONAL_AGENT_SEED`, `COVERWISE_INVESTIGATOR_AGENT_SEED`,
`COVERWISE_PROVIDER_AGENT_SEED` (three distinct stable seeds), and
`COVERWISE_REQUEST_TIMEOUT_SECONDS=15`. Do not paste secrets into chat. The existing
`python -m coverwise.live` entry point includes the Provider receiver; it was not
started by Codex. Then send:

```text
/recommend
/recommend preset
/recommend preset-low
/recommend preset-clarify
/recommend preset-existing
/recommend-evidence candidate-horizon 3 preset
/recommend-evidence candidate-query 2 preset
/recommend-timeout preset
/policies
/inspect candidate-horizon
/stress-test preset
/diagnose CoverWise connectivity
```

Capture both delegation legs with expected senders, envelope session/request IDs,
Provider version/hash, Investigator source evidence, acknowledgements and replies.
Timeout mode must return incomplete rather than fabricate a recommendation. Review
pages 1–4 of each candidate and every existing-policy page separately. Commands,
all explicit fields and deterministic ranking are in [recommendations](recommendations.md).
