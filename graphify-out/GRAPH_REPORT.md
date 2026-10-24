# Graph Report - coverwise  (2026-10-24)

## Corpus Check
- 70 files · ~79,518 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .example 1, .lock 1)

## Summary
- 1011 nodes · 3184 edges · 57 communities (51 shown, 6 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 460 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- insurer
- test_recommend.py
- harness
- test_sandbox.py
- verification.md
- sandbox.py
- cards.py
- live.py
- test_stress.py
- test_policy_rules.py
- coverwise
- policies.py
- Candidate recommendation verification — 2026-10-24 local
- PolicyInspection
- Milestone 4 policy inspection
- inspect_policies
- test_conversation.py
- recommend.py
- Conversation
- agents.py
- sandbox_ui.py
- test_cards.py
- test_doctor.py
- Native ASI:One card journey
- Coordinator
- Minimal natural-language slice
- test_communication.py
- Fictional insurer sandbox workflow
- Milestone 2 verification record
- Fictional candidate recommendations
- .chat
- ASI:One presentation polish — 2026-10-24
- DiagnosticRequest
- Generated application-command repair
- Sandbox verification — 2026-10-24 (local date)
- Deterministic dated stress testing
- CoverWise: 3–5 minute ASI:One demonstration
- Submission review checklist
- CoverWise
- preparation-verification.md
- Foundation architecture
- pytest
- Sandbox details pagination repair
- sandbox_contracts.py
- runtime.py
- asyncio
- CoverWise rehearsal and recovery
- .delegate
- Current entry and screens
- test_card_routing.py
- RecommendationInput
- Synthetic fixture design and editable sources
- Native callback routing and stage diagnostics
- Recommendation timing repair — 2026-10-24
- Quote extraction startup deadline repair
- run
- Clock

## God Nodes (most connected - your core abstractions)
1. `Coordinator` - 91 edges
2. `Contract` - 59 edges
3. `insurer()` - 56 edges
4. `PolicyError` - 41 edges
5. `Cards` - 39 edges
6. `SandboxProvider` - 37 edges
7. `execute()` - 34 edges
8. `parse_input()` - 33 edges
9. `SandboxReply` - 31 edges
10. `install_investigator()` - 30 edges

## Surprising Connections (you probably didn't know these)
- `Startup and mailbox` --references--> `LiveSettings`  [INFERRED]
  docs/rehearsal.md → src/coverwise/live.py
- `Confirmed logging configuration defect` --references--> `internal_agent()`  [INFERRED]
  docs/verification.md → src/coverwise/runtime.py
- `Confirmed validation cause` --references--> `CallbackMetadata`  [INFERRED]
  docs/card-ux-repair.md → src/coverwise/cards.py
- `Date grammar and arithmetic` --references--> `Eligibility`  [INFERRED]
  docs/recommendations.md → src/coverwise/catalogue.py
- `Layout and current boundaries` --references--> `StressTestScenario`  [INFERRED]
  docs/architecture.md → src/coverwise/contracts.py

## Import Cycles
- None detected.

## Communities (57 total, 6 thin omitted)

### Community 0 - "insurer"
Cohesion: 0.22
Nodes (27): full_input(), Harness, send(), response(), intent(), run(), run(), run() (+19 more)

### Community 1 - "test_recommend.py"
Cohesion: 0.13
Nodes (36): offline_recommend(), parse_input(), altered(), assess(), candidate(), rewrite(), test_actual_preset_evidence_and_three_distinctions(), test_age_boundaries_at_start() (+28 more)

### Community 2 - "harness"
Cohesion: 0.21
Nodes (28): run(), test_replayed_entry_command_does_not_reset_pending_form(), run(), application(), click(), demo(), harness(), open_form() (+20 more)

### Community 3 - "test_sandbox.py"
Cohesion: 0.07
Nodes (64): owner_scope(), parse_command(), real_workers(), test_quote_extraction_failure_is_persisted_without_a_quote(), run(), test_repeated_quotes_use_real_batch_workers(), run(), commands() (+56 more)

### Community 5 - "sandbox.py"
Cohesion: 0.05
Nodes (44): Safe reset support, Agent and storage boundaries, load_catalogue(), checked_path(), lease(), main(), provider_lease(), reset() (+36 more)

### Community 6 - "cards.py"
Cohesion: 0.08
Nodes (41): Badge, Carousel, CTA, Detail, Form, FormField, Item, message() (+33 more)

### Community 7 - "live.py"
Cohesion: 0.23
Nodes (7): configure_logging(), LiveSettings, main(), run(), test_effective_timeout_is_logged_without_configuration_secrets(), test_live_info_logging_restored_after_sdk_warning_configuration(), test_three_seed_settings_valid()

### Community 8 - "test_stress.py"
Cohesion: 0.10
Nodes (46): Layout and current boundaries, Live setup (manual, not run by Codex), Local-only transport limitation (important), Milestone 3: diagnostic communication slice, Modules and command, Official references and evidence separation, Routing, sessions and limits, compare() (+38 more)

### Community 9 - "test_policy_rules.py"
Cohesion: 0.21
Nodes (11): PolicyInspectionRequest, context(), sample_report(), test_explicit_none_and_normalization_are_distinct_from_missing(), test_investigator_failures_are_errors_without_findings(), exercise(), test_policy_commands_use_delegation_and_readable_presentation(), exercise() (+3 more)

### Community 11 - "policies.py"
Cohesion: 0.15
Nodes (14): ClauseEvidence, ExtractedTerm, PdfLocator, PolicyDocument, load_policy(), main(), normalize(), parse_pages() (+6 more)

### Community 12 - "Candidate recommendation verification — 2026-10-24 local"
Cohesion: 0.29
Nodes (6): Actual offline examples, Candidate recommendation verification — 2026-10-24 local, Executed checks, Next user-run ASI:One checks, Runtime, visual review, graph and pending work, Source evidence from observed preset

### Community 13 - "PolicyInspection"
Cohesion: 0.20
Nodes (4): Rule grammar and semantics, PolicyInspection, StressTestScenario, TextLocator

### Community 14 - "Milestone 4 policy inspection"
Cohesion: 0.33
Nodes (6): Agent path and presentation, Bounded extraction and evidence, Installation blocker and user verification, Milestone 4 policy inspection, References, Sources, IDs and generation

### Community 15 - "inspect_policies"
Cohesion: 0.33
Nodes (4): Confirmed cause, Repair and operational logging, inspect_policies(), run()

### Community 16 - "test_conversation.py"
Cohesion: 0.12
Nodes (24): paise(), resolve_date(), SandboxReply, test_ambiguous_dates_rejected(), test_exact_rupee_normalization(), test_generated_apply_round_trip(), test_injection_and_yes_never_execute_purchase(), test_invalid_model_actions_cannot_execute() (+16 more)

### Community 17 - "recommend.py"
Cohesion: 0.22
Nodes (15): Eligibility, Candidate, candidate_facts(), eligibility(), Dimension, evaluate(), events(), matched_integer() (+7 more)

### Community 18 - "Conversation"
Cohesion: 0.09
Nodes (12): Confirmed cause, Deterministic policy-selection follow-up, Minimal change, Next user-run messages, Reproduction and verification, candidates(), work(), ASIExplainer (+4 more)

### Community 19 - "agents.py"
Cohesion: 0.14
Nodes (19): install_investigator(), inspect(), stress_test(), CatalogueSnapshot, JobChangeScenario, Draft, member_list(), inspect_policy() (+11 more)

### Community 20 - "sandbox_ui.py"
Cohesion: 0.23
Nodes (11): display_money(), present(), input_text(), command_block(), detail_records(), details_json(), present(), present_details() (+3 more)

### Community 21 - "test_cards.py"
Cohesion: 0.09
Nodes (23): test_card_approval_scope_and_tampering_rejected(), test_card_approval_stale_revision_rejected_by_provider(), test_card_capacity_and_duplicate_json_fields_rejected(), run(), test_card_entry_whitespace_through_coordinator(), run(), test_card_evidence_and_scoped_persisted_details(), test_card_journey_actual_handlers_and_concurrent_duplicate_approval() (+15 more)

### Community 23 - "Native ASI:One card journey"
Cohesion: 0.33
Nodes (6): Card entry whitespace repair, Explicit form path and corrections, Native ASI:One card journey, One demo path, Verification and remaining live checks, Wire, authority and lifecycle

### Community 24 - "Coordinator"
Cohesion: 0.12
Nodes (31): Coordinator, CandidateAssessmentRequest, CandidateAssessmentResult, CatalogueRequest, CatalogueResult, test_demo_only_explicit_and_announced_before_tools(), test_recommendations_use_identical_confirmed_inputs_and_unknown_disclosures(), ctx() (+23 more)

### Community 25 - "Minimal natural-language slice"
Cohesion: 0.25
Nodes (8): Boundaries and privacy, Example: personal question and a fixed synthetic clause, Fast labelled demo, Implementation and verification, Minimal natural-language slice, Next user-run live messages, Partial answers and deterministic normalization, Supported paths

### Community 26 - "test_communication.py"
Cohesion: 0.15
Nodes (4): test_coordinator_name_satisfies_installed_registration_constraint(), test_invalid_live_timeout(), test_model_failure_with_mock_http_and_zero_retries(), test_process_environment_wins_and_timeout_is_forwarded_without_reading_dotenv()

### Community 27 - "Fictional insurer sandbox workflow"
Cohesion: 0.33
Nodes (6): Fictional insurer sandbox workflow, Offline and next user-run live tests, Quotes and exact commands, Review, approval and transitions, State-specific presentation, Unknown outcomes, timeouts and restart

### Community 28 - "Milestone 2 verification record"
Cohesion: 0.12
Nodes (16): Actual transport experiment and blocker, Confirmed logging configuration defect, Deterministic coverage-date slice (2026-10-23), Executed local checks, Final verification, Installation history and environment, Instructions, Git and limits, Live ACP input diagnostics (2026-10-23) (+8 more)

### Community 29 - "Fictional candidate recommendations"
Cohesion: 0.40
Nodes (5): Catalogue and documents, Date grammar and arithmetic, Fictional candidate recommendations, Filtering, ranking, failure handling and lifecycle, Inputs and exact commands

### Community 30 - ".chat"
Cohesion: 0.31
Nodes (3): privacy_notice(), test_acp_acknowledges_before_rejecting_input(), exercise()

### Community 31 - "ASI:One presentation polish — 2026-10-24"
Cohesion: 0.33
Nodes (6): Actual temporary renders, ASI:One presentation polish — 2026-10-24, Default replies and complete details, Executed verification, Next user-run ASI:One checks, Observed live evidence — separate from these local tests

### Community 32 - "DiagnosticRequest"
Cohesion: 0.14
Nodes (16): investigate(), diagnose(), DiagnosticRequest, DiagnosticResult, PolicyInspectionResult, ToolResult, test_acp_success_preserves_tool_result_and_does_not_end_session(), exercise() (+8 more)

### Community 33 - "Generated application-command repair"
Cohesion: 0.50
Nodes (4): Diagnosis, Generated application-command repair, Live retest (user execution only), Repair and checks

### Community 34 - "Sandbox verification — 2026-10-24 (local date)"
Cohesion: 0.50
Nodes (4): Checks, Observed offline flow, Pending user observations and limits, Sandbox verification — 2026-10-24 (local date)

### Community 35 - "Deterministic dated stress testing"
Cohesion: 0.50
Nodes (4): Commands and exact synthetic preset, Deterministic dated stress testing, Observed offline result (2026-10-23), Verification and pending live work

### Community 36 - "CoverWise: 3–5 minute ASI:One demonstration"
Cohesion: 0.25
Nodes (8): 0:00–0:25 — problem and synthetic household, 0:25–1:00 — source clause and immediate problem, 1:00–1:45 — three agents, three meaningful distinctions, 1:45–2:50 — computed quote, review and deliberate approval, 2:50–3:45 — completed sandbox action and persistence, Close — about 10 seconds, CoverWise: 3–5 minute ASI:One demonstration, Optional 3:45–4:35 — deliberate Provider failure and recovery

### Community 37 - "Submission review checklist"
Cohesion: 0.25
Nodes (8): Concise architecture explanation, Concise project description, Deliverables to fill and verify, Evidence and remaining checks, Official requirements: newly verified, Publication and package review, Submission review checklist, Technology claims to keep accurate

### Community 38 - "CoverWise"
Cohesion: 0.25
Nodes (8): ASI:One demonstration, CoverWise, Live communication and synthetic scope, Offline tests and demonstrations, Private local configuration and startup, Rehearsal data and limits, Review and submission links, Windows setup (Python 3.12)

### Community 39 - "preparation-verification.md"
Cohesion: 0.31
Nodes (5): Evidence separation, Official source, Packaging and publication inspection, Rehearsal/submission preparation — 2026-10-24, Verification notes

### Community 40 - "Foundation architecture"
Cohesion: 0.50
Nodes (4): Configuration and open questions, Eventual responsibilities, Foundation architecture, SDK baseline and official references

### Community 41 - "pytest"
Cohesion: 0.09
Nodes (22): UserProfile, generate(), document(), test_budget_requires_nonnegative_integer_paise(), test_duplicate_members_rejected(), test_evidence_round_trip_preserves_document_reference(), test_invalid_document_hash(), test_invalid_evidence() (+14 more)

### Community 42 - "Sandbox details pagination repair"
Cohesion: 0.67
Nodes (3): Displayed format, Sandbox details pagination repair, Verification

### Community 43 - "sandbox_contracts.py"
Cohesion: 0.19
Nodes (3): Catalogue, Product, CoverageAssessment

### Community 44 - "runtime.py"
Cohesion: 0.24
Nodes (3): internal_agent(), NoExternalResolver, receivers()

### Community 45 - "asyncio"
Cohesion: 0.24
Nodes (11): context(), test_delegation_logs_start_result_timeout_and_correlation(), exercise(), test_exact_self_mention_parsing_limits_and_private_logs(), exercise(), result(), test_parser_logging_and_privacy_preserve_behavior(), exercise() (+3 more)

### Community 46 - "CoverWise rehearsal and recovery"
Cohesion: 0.22
Nodes (9): Before startup, Choose the database intentionally, CoverWise rehearsal and recovery, Evidence log, Live checks, one message at a time, Safe demo reset, Startup and mailbox, Troubleshooting observed problems (+1 more)

### Community 47 - ".delegate"
Cohesion: 0.29
Nodes (8): Pending, context(), test_cancellation_cleans_pending(), exercise(), test_capacity_and_failed_delivery(), exercise(), test_timeout_cleanup_late_response_and_no_false_success(), exercise()

### Community 48 - "Current entry and screens"
Cohesion: 0.29
Nodes (7): Compare health plans, Confirmed validation cause, Current entry and screens, Guided card UX and callback repair, I'm changing jobs, Try an example, Verification boundaries

### Community 49 - "test_card_routing.py"
Cohesion: 0.33
Nodes (3): test_bad_callbacks_offer_explicit_restart_without_home_or_payment(), test_existing_cover_form_callback_preserves_selection_and_reaches_review(), run()

### Community 51 - "Synthetic fixture design and editable sources"
Cohesion: 0.50
Nodes (4): Profile and job transition, Synthetic fixture design and editable sources, Three candidate product documents, Two existing-policy documents

### Community 52 - "Native callback routing and stage diagnostics"
Cohesion: 0.40
Nodes (5): Home-menu path audit and repair, Native callback routing and stage diagnostics, Privacy-safe logs, Reproduction and evidence boundary, User-run retest

### Community 53 - "Recommendation timing repair — 2026-10-24"
Cohesion: 0.40
Nodes (5): Actual timing measurements, Confirmed findings and unresolved live hypotheses, Recommendation timing repair — 2026-10-24, User action and exact live retest, Verification and scope

### Community 54 - "Quote extraction startup deadline repair"
Cohesion: 0.50
Nodes (4): Actual Provider measurements after repair, Quote extraction startup deadline repair, Restart and live retest, Small repair

## Knowledge Gaps
- **1 isolated node(s):** `coverwise`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 235 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Coordinator` connect `Coordinator` to `DiagnosticRequest`, `test_recommend.py`, `sandbox.py`, `cards.py`, `live.py`, `test_stress.py`, `test_policy_rules.py`, `policies.py`, `PolicyInspection`, `asyncio`, `.delegate`, `test_conversation.py`, `Conversation`, `agents.py`, `.chat`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Are the 48 inferred relationships involving `Coordinator` (e.g. with `ASIExplainer` and `Cards`) actually correct?**
  _`Coordinator` has 48 INFERRED edges - model-reasoned connections that need verification._
- **What connects `coverwise` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_recommend.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12790697674418605 - nodes in this community are weakly interconnected._
- **Why does `SandboxProvider` connect `sandbox.py` to `insurer`, `test_sandbox.py`, `cards.py`, `policies.py`, `test_conversation.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 47 inferred relationships involving `insurer()` (e.g. with `run()` and `run()`) actually correct?**
  _`insurer()` has 47 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_sandbox.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07259407259407259 - nodes in this community are weakly interconnected._