# Graph Report - coverwise  (2026-10-24)

## Corpus Check
- 72 files · ~81,606 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .example 1, .lock 1)

## Summary
- 1033 nodes · 3261 edges · 45 communities (42 shown, 3 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 475 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `72995927`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_conversation.py
- test_recommend.py
- insurer
- test_sandbox.py
- verification.md
- sandbox.py
- cards.py
- asyncio
- test_stress.py
- test_policy_rules.py
- coverwise
- policies.py
- recommendations.md
- model_validator
- Milestone 4 policy inspection
- transport.py
- stress.py
- recommend.py
- Conversation
- agents.py
- sandbox_ui.py
- PolicyError
- pytest
- Native ASI:One card journey
- Coordinator
- Minimal natural-language slice
- test_communication.py
- sandbox.md
- Milestone 2 verification record
- Fictional candidate recommendations
- Job-card inspection startup deadline repair
- ASI:One presentation polish — 2026-10-24
- .chat
- Generated application-command repair
- Deterministic policy-selection follow-up
- CoverWise: 3–5 minute ASI:One demonstration
- Submission review checklist
- CoverWise
- Rehearsal/submission preparation — 2026-10-24
- test_policy_pdf.py
- sandbox_contracts.py
- CoverWise rehearsal and recovery
- Current entry and screens
- Native callback routing and stage diagnostics
- Recommendation timing repair — 2026-10-24

## God Nodes (most connected - your core abstractions)
1. `Coordinator` - 91 edges
2. `insurer()` - 61 edges
3. `Contract` - 59 edges
4. `PolicyError` - 40 edges
5. `Cards` - 39 edges
6. `SandboxProvider` - 37 edges
7. `harness()` - 35 edges
8. `execute()` - 34 edges
9. `parse_input()` - 33 edges
10. `payload()` - 32 edges

## Surprising Connections (you probably didn't know these)
- `Startup and mailbox` --references--> `LiveSettings`  [INFERRED]
  docs/rehearsal.md → src/coverwise/live.py
- `Local measurements and verification` --references--> `load_policy()`  [INFERRED]
  docs/job-inspection-repair.md → src/coverwise/policies.py
- `Confirmed logging configuration defect` --references--> `internal_agent()`  [INFERRED]
  docs/verification.md → src/coverwise/runtime.py
- `Confirmed validation cause` --references--> `CallbackMetadata`  [INFERRED]
  docs/card-ux-repair.md → src/coverwise/cards.py
- `Date grammar and arithmetic` --references--> `Eligibility`  [INFERRED]
  docs/recommendations.md → src/coverwise/catalogue.py

## Import Cycles
- None detected.

## Communities (45 total, 3 thin omitted)

### Community 0 - "test_conversation.py"
Cohesion: 0.09
Nodes (52): paise(), resolve_date(), PolicyInspectionRequest, full_input(), Harness, send(), response(), intent() (+44 more)

### Community 1 - "test_recommend.py"
Cohesion: 0.13
Nodes (36): offline_recommend(), parse_input(), altered(), assess(), candidate(), rewrite(), test_actual_preset_evidence_and_three_distinctions(), test_age_boundaries_at_start() (+28 more)

### Community 2 - "insurer"
Cohesion: 0.07
Nodes (69): SandboxReply, test_bad_callbacks_offer_explicit_restart_without_home_or_payment(), run(), test_existing_cover_form_callback_preserves_selection_and_reaches_review(), run(), test_replayed_entry_command_does_not_reset_pending_form(), run(), application() (+61 more)

### Community 3 - "test_sandbox.py"
Cohesion: 0.07
Nodes (66): owner_scope(), parse_command(), real_workers(), test_quote_extraction_failure_is_persisted_without_a_quote(), run(), test_repeated_quotes_use_real_batch_workers(), run(), Clock (+58 more)

### Community 4 - "verification.md"
Cohesion: 0.22
Nodes (5): Actual Provider measurements after repair, Quote extraction startup deadline repair, Restart and live retest, Small repair, Current sandbox milestone

### Community 5 - "sandbox.py"
Cohesion: 0.08
Nodes (30): Safe reset support, checked_path(), lease(), main(), provider_lease(), reset(), ResetRefused, canonical() (+22 more)

### Community 6 - "cards.py"
Cohesion: 0.09
Nodes (39): Badge, Carousel, CTA, Detail, Form, FormField, Item, message() (+31 more)

### Community 7 - "asyncio"
Cohesion: 0.11
Nodes (14): configure_logging(), LiveSettings, main(), run(), internal_agent(), NoExternalResolver, receivers(), test_effective_timeout_is_logged_without_configuration_secrets() (+6 more)

### Community 8 - "test_stress.py"
Cohesion: 0.09
Nodes (50): Configuration and open questions, Eventual responsibilities, Foundation architecture, Layout and current boundaries, SDK baseline and official references, Live setup (manual, not run by Codex), Local-only transport limitation (important), Milestone 3: diagnostic communication slice (+42 more)

### Community 9 - "test_policy_rules.py"
Cohesion: 0.29
Nodes (11): PolicyInspectionResult, context(), sample_report(), test_explicit_none_and_normalization_are_distinct_from_missing(), test_policy_commands_use_delegation_and_readable_presentation(), exercise(), test_policy_correlation_and_type_do_not_accept_diagnostic_or_wrong_policy(), exercise() (+3 more)

### Community 11 - "policies.py"
Cohesion: 0.16
Nodes (19): Evidence and confirmed cause, Confirmed cause, Repair and operational logging, inspect(), ClauseEvidence, ExtractedTerm, PdfLocator, PolicyDocument (+11 more)

### Community 12 - "recommendations.md"
Cohesion: 0.12
Nodes (14): Profile and job transition, Synthetic fixture design and editable sources, Three candidate product documents, Two existing-policy documents, Actual offline examples, Candidate recommendation verification — 2026-10-24 local, Executed checks, Next user-run ASI:One checks (+6 more)

### Community 14 - "Milestone 4 policy inspection"
Cohesion: 0.33
Nodes (6): Agent path and presentation, Bounded extraction and evidence, Installation blocker and user verification, Milestone 4 policy inspection, References, Sources, IDs and generation

### Community 15 - "transport.py"
Cohesion: 0.09
Nodes (12): Agent and storage boundaries, install_provider(), catalogue(), work(), workflow(), work(), demonstrate(), main() (+4 more)

### Community 16 - "stress.py"
Cohesion: 0.25
Nodes (9): CoverageAssessment, JobChangeScenario, assess(), add(), Assessment, Comparison, Finding, main() (+1 more)

### Community 17 - "recommend.py"
Cohesion: 0.13
Nodes (21): Rule grammar and semantics, CatalogueSnapshot, Eligibility, display_money(), amount(), inr(), Candidate, candidate_facts() (+13 more)

### Community 18 - "Conversation"
Cohesion: 0.21
Nodes (5): candidates(), work(), Conversation, document_id(), Fragments

### Community 19 - "agents.py"
Cohesion: 0.24
Nodes (5): Draft, member_list(), policy_listing(), details_page(), Rules

### Community 20 - "sandbox_ui.py"
Cohesion: 0.44
Nodes (7): command_block(), detail_records(), details_json(), present(), present_details(), render_details_page(), utc()

### Community 21 - "PolicyError"
Cohesion: 0.23
Nodes (9): install_investigator(), stress_test(), PolicyError, main(), present(), reference(), present_comparison(), test_bounded_file_rejection_without_pdf_dependency() (+1 more)

### Community 22 - "pytest"
Cohesion: 0.39
Nodes (9): UserProfile, document(), test_budget_requires_nonnegative_integer_paise(), test_duplicate_members_rejected(), test_evidence_round_trip_preserves_document_reference(), test_invalid_document_hash(), test_invalid_evidence(), test_scenario_interval_and_member_references() (+1 more)

### Community 23 - "Native ASI:One card journey"
Cohesion: 0.33
Nodes (6): Card entry whitespace repair, Explicit form path and corrections, Native ASI:One card journey, One demo path, Verification and remaining live checks, Wire, authority and lifecycle

### Community 24 - "Coordinator"
Cohesion: 0.11
Nodes (34): Coordinator, CandidateAssessmentRequest, CandidateAssessmentResult, CatalogueRequest, CatalogueResult, test_delegation_logs_start_result_timeout_and_correlation(), exercise(), test_timeout_cleanup_late_response_and_no_false_success() (+26 more)

### Community 25 - "Minimal natural-language slice"
Cohesion: 0.25
Nodes (8): Boundaries and privacy, Example: personal question and a fixed synthetic clause, Fast labelled demo, Implementation and verification, Minimal natural-language slice, Next user-run live messages, Partial answers and deterministic normalization, Supported paths

### Community 26 - "test_communication.py"
Cohesion: 0.08
Nodes (15): Confirmed cause, ASIExplainer, Intent, DiagnosticResult, context(), test_acp_acknowledges_before_rejecting_input(), exercise(), test_cancellation_cleans_pending() (+7 more)

### Community 27 - "sandbox.md"
Cohesion: 0.13
Nodes (13): Displayed format, Sandbox details pagination repair, Verification, Fictional insurer sandbox workflow, Offline and next user-run live tests, Quotes and exact commands, Review, approval and transitions, State-specific presentation (+5 more)

### Community 28 - "Milestone 2 verification record"
Cohesion: 0.12
Nodes (16): Actual transport experiment and blocker, Confirmed logging configuration defect, Deterministic coverage-date slice (2026-10-23), Executed local checks, Final verification, Installation history and environment, Instructions, Git and limits, Live ACP input diagnostics (2026-10-23) (+8 more)

### Community 29 - "Fictional candidate recommendations"
Cohesion: 0.40
Nodes (5): Catalogue and documents, Date grammar and arithmetic, Fictional candidate recommendations, Filtering, ranking, failure handling and lifecycle, Inputs and exact commands

### Community 30 - "Job-card inspection startup deadline repair"
Cohesion: 0.40
Nodes (4): Exact live retest (manual; not performed here), Job-card inspection startup deadline repair, Local measurements and verification, Repair and boundaries

### Community 31 - "ASI:One presentation polish — 2026-10-24"
Cohesion: 0.33
Nodes (6): Actual temporary renders, ASI:One presentation polish — 2026-10-24, Default replies and complete details, Executed verification, Next user-run ASI:One checks, Observed live evidence — separate from these local tests

### Community 32 - ".chat"
Cohesion: 0.16
Nodes (18): privacy_notice(), investigate(), Pending, diagnose(), DiagnosticRequest, context(), exercise(), result() (+10 more)

### Community 33 - "Generated application-command repair"
Cohesion: 0.40
Nodes (4): Diagnosis, Generated application-command repair, Live retest (user execution only), Repair and checks

### Community 34 - "Deterministic policy-selection follow-up"
Cohesion: 0.40
Nodes (4): Deterministic policy-selection follow-up, Minimal change, Next user-run messages, Reproduction and verification

### Community 36 - "CoverWise: 3–5 minute ASI:One demonstration"
Cohesion: 0.25
Nodes (8): 0:00–0:25 — problem and synthetic household, 0:25–1:00 — source clause and immediate problem, 1:00–1:45 — three agents, three meaningful distinctions, 1:45–2:50 — computed quote, review and deliberate approval, 2:50–3:45 — completed sandbox action and persistence, Close — about 10 seconds, CoverWise: 3–5 minute ASI:One demonstration, Optional 3:45–4:35 — deliberate Provider failure and recovery

### Community 37 - "Submission review checklist"
Cohesion: 0.25
Nodes (8): Concise architecture explanation, Concise project description, Deliverables to fill and verify, Evidence and remaining checks, Official requirements: newly verified, Publication and package review, Submission review checklist, Technology claims to keep accurate

### Community 38 - "CoverWise"
Cohesion: 0.25
Nodes (8): ASI:One demonstration, CoverWise, Live communication and synthetic scope, Offline tests and demonstrations, Private local configuration and startup, Rehearsal data and limits, Review and submission links, Windows setup (Python 3.12)

### Community 39 - "Rehearsal/submission preparation — 2026-10-24"
Cohesion: 0.40
Nodes (5): Evidence separation, Official source, Packaging and publication inspection, Rehearsal/submission preparation — 2026-10-24, Verification notes

### Community 41 - "test_policy_pdf.py"
Cohesion: 0.07
Nodes (18): load_catalogue(), generate(), main(), test_job_unknown_pdf_terms_remain_visible(), DoctorFailureTests, batch_process(), generated(), test_batch_parent_keeps_deadline_and_reaps_timed_out_child() (+10 more)

### Community 46 - "CoverWise rehearsal and recovery"
Cohesion: 0.22
Nodes (9): Before startup, Choose the database intentionally, CoverWise rehearsal and recovery, Evidence log, Live checks, one message at a time, Safe demo reset, Startup and mailbox, Troubleshooting observed problems (+1 more)

### Community 48 - "Current entry and screens"
Cohesion: 0.29
Nodes (7): Compare health plans, Confirmed validation cause, Current entry and screens, Guided card UX and callback repair, I'm changing jobs, Try an example, Verification boundaries

### Community 52 - "Native callback routing and stage diagnostics"
Cohesion: 0.40
Nodes (5): Home-menu path audit and repair, Native callback routing and stage diagnostics, Privacy-safe logs, Reproduction and evidence boundary, User-run retest

### Community 53 - "Recommendation timing repair — 2026-10-24"
Cohesion: 0.40
Nodes (5): Actual timing measurements, Confirmed findings and unresolved live hypotheses, Recommendation timing repair — 2026-10-24, User action and exact live retest, Verification and scope

## Knowledge Gaps
- **1 isolated node(s):** `coverwise`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 240 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Coordinator` connect `Coordinator` to `.chat`, `test_conversation.py`, `insurer`, `test_recommend.py`, `cards.py`, `asyncio`, `test_stress.py`, `test_policy_rules.py`, `policies.py`, `transport.py`, `stress.py`, `recommend.py`, `Conversation`, `agents.py`, `PolicyError`, `test_communication.py`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Are the 48 inferred relationships involving `Coordinator` (e.g. with `ASIExplainer` and `Cards`) actually correct?**
  _`Coordinator` has 48 INFERRED edges - model-reasoned connections that need verification._
- **What connects `coverwise` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_conversation.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08649912331969609 - nodes in this community are weakly interconnected._
- **Why does `PolicyError` connect `PolicyError` to `sandbox.py`, `cards.py`, `test_policy_pdf.py`, `test_policy_rules.py`, `policies.py`, `sandbox_contracts.py`, `transport.py`, `stress.py`, `recommend.py`, `Conversation`, `agents.py`, `sandbox_ui.py`, `Coordinator`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Are the 51 inferred relationships involving `insurer()` (e.g. with `run()` and `run()`) actually correct?**
  _`insurer()` has 51 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_recommend.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12790697674418605 - nodes in this community are weakly interconnected._