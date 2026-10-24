# CoverWise: 3–5 minute ASI:One demonstration

Target: about 4 minutes, up to 5 with the optional failure/recovery. Complete the
[rehearsal checks](rehearsal.md) first. Keep the backend running and use one ASI:One
conversation. Show synthetic information only; keep terminal secrets and private
configuration off-screen. Use a separate rehearsal database for fresh purchases.

Commands below are literal implemented commands. Generated application/approval/
status/details commands must be copied from actual replies, one at a time. Their
references and challenge are not fixed in this script. Narration is a description
of expected behavior; only call a live step successful after observing it.

## 0:00–0:25 — problem and synthetic household

Say: “When employment ends, a family needs dates and evidence, not a generic
recommendation. CoverWise identifies employer protection ending, compares existing
and prospective protection, and takes a reviewed next step in a fictional insurer
sandbox. No real policy is issued and no real money moves.”

```text
/start
```

State the **demo assumptions**: self born 1992-04-10 and spouse born 1994-08-15;
both declare no pre-existing conditions. Annual budget ₹30,000, minimum shared
family limit ₹10,00,000, uncapped private room. Employment ends December 31, 2026;
new-employer insurance is merely assumed to start February 1, 2027. Illustrative
hospitalization is for the spouse (`member-02`) on January 15.

## 0:25–1:00 — source clause and immediate problem

```text
/inspect existing-employer
```

Point to **p2 / EMP-02** and the extracted evidence ID, not an invented summary:
protection for both members ends on the stated final employment date,
2026-12-31 inclusive, or policy expiry if earlier; no conversion/continuity benefit.

```text
/stress-test member-02 2026-12-31 2027-02-01 2027-01-15 illness_hospitalization
```

Say: “January 1–31 is a 31-day gap in employer protection. This is not a claim
that all protection is absent. The same illustration separately assesses the
existing personal policy; its dates may pass, but unknown terms remain.”
The stress comparison is explanatory; the candidate workflow next explicitly
chooses the employer-only path, rather than silently removing existing cover.

## 1:00–1:45 — three agents, three meaningful distinctions

```text
/recommend preset
```

Say: “The Coordinator requested the Provider's catalogue and delegated evidence
assessment to the Investigator through typed SDK messages.”

- Economy: ₹12,000/year, ₹5,00,000 family limit and ₹3,000/day room cap; fails
  this household's hard limit/room requirements despite being cheapest.
- Query: ₹18,000/year, ₹10,00,000 family limit, unresolved room schedule; a
  material unknown cannot pass a hard room requirement. Ask for clarification.
- Horizon: ₹22,000/year, ₹10,00,000 shared family limit and uncapped private room;
  meets the supported longer-term requirements within budget. Fresh waiting and
  other scoped restrictions remain. It is a prospective shortlist, not guaranteed
  acceptance or a claim promise.

```text
/recommend-evidence candidate-horizon 3 preset
```

Point to **p3 / HOR-03**: a new 30-day illness wait, no continuity credit/waiver.
January 1–30 is waiting; January 31 is first post-wait day. Say explicitly:
“Buying Horizon does not solve the January 15 illness event. February 10 is a
separate later illustration applied identically across candidates.”

## 1:45–2:50 — computed quote, review and deliberate approval

```text
/quote preset
```

Explain: “This is now a tool-generated, validated and persisted quote, distinct
from an indicative list premium, even when the price is the same.” Show ₹22,000,
the actual quote ID, UTC expiry, members, January 1–December 31 proposed term,
January 1–30 wait and the excluded immediate event.

Copy the **actual application command** returned by this quote. Do not use a
reference from an old conversation or from documentation. The normal command
selects the explicit `confirm-demo success` mode.

Review the actual application: member details/disclosures, shared-family and room
restrictions, exclusions, quote expiry, application revision and approval expiry.
Show that cancellation is available before execution. Full reviewed terms remain
available through its generated details command. Do not scroll through every
evidence page in the short video.

Say: “Advice did not purchase anything. This separate command authorizes exactly
this review in the observed sender/session scope. It does not verify my identity
or constitute real insurance consent.” Then copy and send the **actual generated
approval command** for the current revision/challenge. If it expired, obtain a
fresh review rather than editing the challenge or overriding the check.

## 2:50–3:45 — completed sandbox action and persistence

Show the **actual** completed application, payment ID, transaction and stable
confirmation. Say: “The Provider executed mock payment code and persisted the
result. Sandbox/demo — no real policy issued; no real money moved. Waiting periods
and exclusions remain; future claims are not guaranteed.”

Save the exact returned status command. Stop and restart the local backend with
the **same database and stable seeds**, keeping the ASI:One conversation open.
Use the existing documented startup command (keep private configuration off-screen).
After mailbox readiness, paste that saved status command and compare all four
application/payment/transaction/confirmation references. Do not substitute a new
chat, new database or a fresh purchase for this check.

If restart takes longer, narrate the already user-observed restart recovery and
label what is being shown accurately; do not edit a timeout into a success.

## Optional 3:45–4:35 — deliberate Provider failure and recovery

Only include after successfully rehearsing it and if there is time:

```text
/recommend-timeout preset
```

Say: “This command intentionally suppresses the Provider catalogue response; it
is not a normal recommendation failure.” Wait for the actual bounded incomplete
result (default deadline 15 seconds), then:

```text
/recommend preset
```

Show the actual recovery if it occurs. This sequence remains unconfirmed until
observed; do not claim that the older restart result proves timeout recovery.
An unknown **payment** would instead use its returned status command, never a
blind payment retry. Recommending again here creates no purchase.

## Close — about 10 seconds

Say: “CoverWise turns PDF evidence and explicit assumptions into a deterministic
comparison and a reviewed sandbox action. The local backend, authored parser and
fictional insurer are deliberate limits. Existing personal cover can be retained
instead of automatically buying another policy.”

Avoid claims of generic discovery, live duplicate approval, corrected pagination,
full timeout recovery or PDF visual quality unless those specific rehearsal checks
have actually passed and been recorded. See the [submission checklist](submission-checklist.md).
