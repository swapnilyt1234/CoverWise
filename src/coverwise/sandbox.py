"""Transactional fictional insurer. All payments and confirmations are sandbox only."""

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from coverwise.catalogue import load_catalogue
from coverwise.demo_reset import provider_lease
from coverwise.policies import ROOT, PolicyError
from coverwise.recommend import run as assess_candidates
from coverwise.sandbox_contracts import (
    ApplicationFields,
    ApplicationView,
    PaymentView,
    QuoteTerms,
    SandboxQuote,
    SandboxReply,
)

LOGGER = logging.getLogger("coverwise")
PROVIDER_VERSION = "sandbox-provider-1"
PRICING_RULE = "eligible-family-list-v1"
QUOTE_TTL = timedelta(minutes=15)
CHALLENGE_TTL = timedelta(minutes=5)
LABEL = "Sandbox/demo — no real policy issued. No real money moved."

SCHEMA = (
    """CREATE TABLE quotes (id TEXT PRIMARY KEY, scope TEXT NOT NULL,
        body TEXT NOT NULL, digest TEXT NOT NULL)""",
    """CREATE TABLE applications (id TEXT PRIMARY KEY, scope TEXT NOT NULL,
        quote_id TEXT NOT NULL UNIQUE REFERENCES quotes(id),
        revision INTEGER NOT NULL CHECK(revision>0), state TEXT NOT NULL CHECK(state
        IN ('review','approved','payment_pending','completed','failed','cancelled',
        'needs_review')), updated_at TEXT NOT NULL)""",
    """CREATE TABLE revisions (app_id TEXT NOT NULL REFERENCES applications(id),
        revision INTEGER NOT NULL, quote_id TEXT NOT NULL REFERENCES quotes(id),
        fields TEXT NOT NULL, digest TEXT NOT NULL, challenge_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(app_id,revision))""",
    """CREATE TABLE approvals (id TEXT PRIMARY KEY,
        app_id TEXT NOT NULL REFERENCES applications(id), revision INTEGER NOT NULL,
        scope TEXT NOT NULL, quote_id TEXT NOT NULL, digest TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('approved','consumed','invalidated')),
        approved_at TEXT NOT NULL, UNIQUE(app_id,revision))""",
    """CREATE TABLE payments (id TEXT PRIMARY KEY,
        app_id TEXT NOT NULL UNIQUE REFERENCES applications(id),
        approval_id TEXT NOT NULL UNIQUE REFERENCES approvals(id),
        idempotency_key TEXT NOT NULL UNIQUE,
        amount_paise INTEGER NOT NULL CHECK(amount_paise>=0),
        currency TEXT NOT NULL CHECK(currency='INR'), state TEXT NOT NULL
        CHECK(state IN ('succeeded','failed','unknown')), confirmation TEXT UNIQUE,
        transaction_ref TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL)""",
    """CREATE TABLE payment_ledger (payment_id TEXT PRIMARY KEY REFERENCES payments(id),
        transaction_ref TEXT NOT NULL UNIQUE, authoritative_state TEXT NOT NULL
        CHECK(authoritative_state IN ('succeeded','failed')),
        amount_paise INTEGER NOT NULL CHECK(amount_paise>=0),
        recorded_at TEXT NOT NULL)""",
    """CREATE TABLE operations (id TEXT PRIMARY KEY, scope TEXT NOT NULL,
        action TEXT NOT NULL, command_digest TEXT NOT NULL, reference TEXT,
        state TEXT NOT NULL CHECK(state IN ('pending','done','rejected')),
        error_code TEXT, created_at TEXT NOT NULL)""",
)


class SandboxError(Exception):
    """Safe code only; never include profiles, challenges or database exceptions."""


def canonical(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def owner_scope(sender, session):
    return digest({"observed_sender": sender, "envelope_session": str(session)})


def utc_now():
    return datetime.now(timezone.utc)


def reference(prefix):
    return prefix + "-" + uuid4().hex


def quote_price(product, members):
    """Flat annual family tariff, after the separate eligibility/fit checks."""
    if not 1 <= len(members) <= product.eligibility.max_members:
        raise SandboxError("ineligible_members")
    return product.annual_premium_paise


class SandboxProvider:
    def __init__(
        self,
        path=None,
        *,
        clock=utc_now,
        catalogue=load_catalogue,
        assessor=assess_candidates,
    ):
        self.path = Path(
            path
            or os.environ.get(
                "COVERWISE_SANDBOX_DB", ROOT / "runtime" / "provider.sqlite3"
            )
        )
        if self.path.suffix.lower() not in (".db", ".sqlite", ".sqlite3"):
            raise SandboxError("database_extension_required")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock, self.catalogue, self.assessor = clock, catalogue, assessor
        self.work_lock = Lock()
        self.demo_lease = provider_lease(self.path)
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                for statement in SCHEMA:
                    db.execute(statement)
                db.execute("PRAGMA user_version=1")
            elif version != 1:
                raise SandboxError("unsupported_schema")

    @contextmanager
    def transaction(self):
        if self.demo_lease is not None and self.demo_lease.closed:
            raise SandboxError("provider_closed")
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def close(self):
        """Release the rehearsal safety lease after stopping this Provider."""
        with self.work_lock:
            if self.demo_lease is not None:
                self.demo_lease.close()

    def now(self):
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise SandboxError("aware_clock_required")
        return value.astimezone(timezone.utc)

    def terms(self, inputs, product_id):
        if inputs.path != "employer-only":
            raise SandboxError("existing_cover_review_required")
        snapshot = self.catalogue()
        report = self.assessor(inputs, snapshot)
        product = next(
            (p for p in snapshot.catalogue.products if p.product_id == product_id), None
        )
        candidate = next(
            (c for c in report.candidates if c.product_id == product_id), None
        )
        if product is None or candidate is None:
            raise SandboxError("unknown_product")
        if report.outcome == "correct_scenario":
            raise SandboxError("scenario_correction_required")
        if (
            any(
                d.status != "pass"
                for d in (
                    candidate.eligibility,
                    candidate.budget,
                    candidate.requirements,
                )
            )
            or candidate.material_unknowns
        ):
            raise SandboxError("eligibility_budget_or_terms_unresolved")
        if candidate.disposition != "qualifies":
            raise SandboxError("later_scenario_not_suitable")
        evidence = next(
            p
            for p in report.inspections
            if p.document.document_id == product.document.document_id
        )
        start = inputs.proposed_start
        return QuoteTerms(
            provider_version=PROVIDER_VERSION,
            pricing_rule_version=PRICING_RULE,
            catalogue_version=snapshot.catalogue.catalogue_version,
            catalogue_sha256=snapshot.source_sha256,
            product=product,
            inputs=inputs,
            premium_paise=quote_price(product, inputs.members),
            premium_basis="Computed flat annual family tariff for validated eligible "
            "members; no adjustments, taxes or fees in this fictional demo.",
            cover_start=start,
            cover_end=start + timedelta(days=product.policy_days - 1),
            wait_start=start,
            wait_end=start + timedelta(days=product.initial_wait_days - 1),
            first_post_wait_day=start + timedelta(days=product.initial_wait_days),
            immediate_status=candidate.immediate.status,
            restrictions=(candidate.immediate.restrictions or [])
            + [
                t.name + ": " + t.value
                for t in evidence.terms
                if t.name in ("Eligibility", "Exclusions") and t.value
            ],
            required_disclosures=[
                "Explicit absence of pre-existing conditions for each proposed member.",
                "Confirm the supplied details are synthetic demo data.",
            ],
            evidence=evidence,
        )

    def read_quote(self, db, scope, quote_id):
        row = db.execute(
            "SELECT * FROM quotes WHERE id=? AND scope=?", (quote_id, scope)
        ).fetchone()
        if row is None:
            raise SandboxError("not_found_or_not_authorized")
        try:
            quote = SandboxQuote.model_validate_json(row["body"])
        except ValueError:
            raise SandboxError("quote_integrity_failure") from None
        if quote.quote_id != quote_id or not hmac.compare_digest(
            digest(quote), row["digest"]
        ):
            raise SandboxError("quote_integrity_failure")
        return quote

    def read_app(self, db, scope, application_id):
        row = db.execute(
            "SELECT * FROM applications WHERE id=? AND scope=?", (application_id, scope)
        ).fetchone()
        if row is None:
            raise SandboxError("not_found_or_not_authorized")
        return row

    def binding(self, scope, app_id, revision, quote, fields, expires, challenge_hash):
        return digest(
            dict(
                scope=scope,
                application_id=app_id,
                revision=revision,
                quote=quote.model_dump(mode="json"),
                fields=fields.model_dump(),
                expires_at=expires,
                challenge_hash=challenge_hash,
            )
        )

    def current_quote(self, scope, quote_id):
        with self.transaction() as db:
            quote = self.read_quote(db, scope, quote_id)
        if self.now() >= quote.expires_at:
            raise SandboxError("quote_expired")
        current = self.terms(quote.inputs, quote.product.product_id)
        old = QuoteTerms.model_validate(
            quote.model_dump(exclude={"quote_id", "created_at", "expires_at"})
        )
        if current != old:
            raise SandboxError("quote_terms_changed")
        return quote

    def invalidate(self, scope, app_id):
        with self.transaction() as db:
            app = self.read_app(db, scope, app_id)
            if app["state"] in ("review", "approved", "needs_review"):
                db.execute(
                    "UPDATE applications SET state='needs_review',updated_at=? "
                    "WHERE id=?",
                    (self.now().isoformat(), app_id),
                )
                db.execute(
                    "UPDATE approvals SET state='invalidated' "
                    "WHERE app_id=? AND state='approved'",
                    (app_id,),
                )

    def make_quote(self, scope, command, operation_id):
        terms = self.terms(command.inputs, command.product_id)
        now = self.now()
        quote = SandboxQuote(
            **terms.model_dump(),
            quote_id=reference("q"),
            created_at=now,
            expires_at=now + QUOTE_TTL,
        )
        with self.transaction() as db:
            db.execute(
                "INSERT INTO quotes VALUES (?,?,?,?)",
                (quote.quote_id, scope, canonical(quote), digest(quote)),
            )
            db.execute(
                "UPDATE operations SET reference=?,state='done' WHERE id=?",
                (quote.quote_id, operation_id),
            )
        return quote.quote_id, None

    def review(self, scope, command, operation_id):
        new = command.action == "apply"
        if new:
            quote_id, fields = command.reference, command.application
            with self.transaction() as db:
                self.read_quote(db, scope, quote_id)
                existing = db.execute(
                    "SELECT app_id AS id FROM revisions WHERE quote_id=? LIMIT 1",
                    (quote_id,),
                ).fetchone()
            if existing:
                with self.transaction() as db:
                    app = self.read_app(db, scope, existing["id"])
                    if app["quote_id"] != quote_id:
                        raise SandboxError("quote_already_used")
                    prior = db.execute(
                        "SELECT fields FROM revisions WHERE app_id=? AND revision=?",
                        (app["id"], app["revision"]),
                    ).fetchone()
                    if ApplicationFields.model_validate_json(prior["fields"]) != fields:
                        raise SandboxError("application_exists_use_review")
                    db.execute(
                        "UPDATE operations SET reference=?,state='done' WHERE id=?",
                        (app["id"], operation_id),
                    )
                return existing["id"], None
            app_id = reference("a")
        else:
            app_id = command.reference
            with self.transaction() as db:
                app = self.read_app(db, scope, app_id)
                if (
                    app["state"] not in ("review", "approved", "needs_review")
                    or db.execute(
                        "SELECT 1 FROM payments WHERE app_id=?", (app_id,)
                    ).fetchone()
                ):
                    raise SandboxError("application_not_mutable")
                old = db.execute(
                    "SELECT * FROM revisions WHERE app_id=? AND revision=?",
                    (app_id, app["revision"]),
                ).fetchone()
                quote_id = command.replacement_quote or app["quote_id"]
                fields = command.application or ApplicationFields.model_validate_json(
                    old["fields"]
                )
        try:
            quote = self.current_quote(scope, quote_id)
        except (SandboxError, PolicyError):
            if not new:
                self.invalidate(scope, app_id)
            raise
        challenge = secrets.token_urlsafe(18)
        hashed = hashlib.sha256(challenge.encode()).hexdigest()
        now = self.now()
        expires = min(now + CHALLENGE_TTL, quote.expires_at).isoformat()
        with self.transaction() as db:
            if self.now() >= quote.expires_at:
                raise SandboxError("quote_expired")
            if new:
                existing = db.execute(
                    "SELECT app_id AS id FROM revisions WHERE quote_id=? LIMIT 1",
                    (quote_id,),
                ).fetchone()
                if existing:
                    app = self.read_app(db, scope, existing["id"])
                    if app["quote_id"] != quote_id:
                        raise SandboxError("quote_already_used")
                    prior = db.execute(
                        "SELECT fields FROM revisions WHERE app_id=? AND revision=?",
                        (app["id"], app["revision"]),
                    ).fetchone()
                    if ApplicationFields.model_validate_json(prior["fields"]) != fields:
                        raise SandboxError("application_exists_use_review")
                    db.execute(
                        "UPDATE operations SET reference=?,state='done' WHERE id=?",
                        (app["id"], operation_id),
                    )
                    return existing["id"], None
                revision = 1
                db.execute(
                    "INSERT INTO applications VALUES (?,?,?,?,?,?)",
                    (app_id, scope, quote_id, revision, "review", now.isoformat()),
                )
            else:
                app = self.read_app(db, scope, app_id)
                claim = db.execute(
                    "SELECT app_id FROM revisions WHERE quote_id=? LIMIT 1", (quote_id,)
                ).fetchone()
                if claim and claim["app_id"] != app_id:
                    raise SandboxError("quote_already_used")
                if (
                    app["state"] not in ("review", "approved", "needs_review")
                    or db.execute(
                        "SELECT 1 FROM payments WHERE app_id=?", (app_id,)
                    ).fetchone()
                ):
                    raise SandboxError("application_not_mutable")
                revision = app["revision"] + 1
                db.execute(
                    "UPDATE approvals SET state='invalidated' "
                    "WHERE app_id=? AND state='approved'",
                    (app_id,),
                )
                db.execute(
                    "UPDATE applications SET quote_id=?,revision=?,state='review',"
                    "updated_at=? WHERE id=?",
                    (quote_id, revision, now.isoformat(), app_id),
                )
            bound = self.binding(
                scope, app_id, revision, quote, fields, expires, hashed
            )
            db.execute(
                "INSERT INTO revisions VALUES (?,?,?,?,?,?,?,?)",
                (
                    app_id,
                    revision,
                    quote_id,
                    canonical(fields),
                    bound,
                    hashed,
                    expires,
                    now.isoformat(),
                ),
            )
            db.execute(
                "UPDATE operations SET reference=?,state='done' WHERE id=?",
                (app_id, operation_id),
            )
        return app_id, challenge

    def authorize(self, scope, command):
        with self.transaction() as db:
            app = self.read_app(db, scope, command.reference)
            revision = db.execute(
                "SELECT * FROM revisions WHERE app_id=? AND revision=?",
                (app["id"], app["revision"]),
            ).fetchone()
            if app["revision"] != command.revision or not hmac.compare_digest(
                revision["challenge_hash"],
                hashlib.sha256(command.challenge.encode()).hexdigest(),
            ):
                raise SandboxError("invalid_review_or_challenge")
            if app["state"] in ("completed", "payment_pending", "failed"):
                return app["id"]
            if app["state"] not in ("review", "approved"):
                raise SandboxError("new_review_required")
        try:
            quote = self.current_quote(scope, app["quote_id"])
        except (SandboxError, PolicyError):
            self.invalidate(scope, app["id"])
            raise
        with self.transaction() as db:
            app = self.read_app(db, scope, command.reference)
            revision = db.execute(
                "SELECT * FROM revisions WHERE app_id=? AND revision=?",
                (app["id"], app["revision"]),
            ).fetchone()
            if app["revision"] != command.revision or not hmac.compare_digest(
                revision["challenge_hash"],
                hashlib.sha256(command.challenge.encode()).hexdigest(),
            ):
                raise SandboxError("invalid_review_or_challenge")
            if app["state"] in ("completed", "payment_pending", "failed"):
                return app["id"]
            if app["state"] not in ("review", "approved"):
                raise SandboxError("new_review_required")
            now = self.now()
            if now >= quote.expires_at or now >= datetime.fromisoformat(
                revision["expires_at"]
            ):
                raise SandboxError("review_or_quote_expired")
            stored_quote = self.read_quote(db, scope, app["quote_id"])
            fields = ApplicationFields.model_validate_json(revision["fields"])
            expected = self.binding(
                scope,
                app["id"],
                app["revision"],
                stored_quote,
                fields,
                revision["expires_at"],
                revision["challenge_hash"],
            )
            if stored_quote != quote or not hmac.compare_digest(
                expected, revision["digest"]
            ):
                raise SandboxError("review_integrity_failure")
            prior = db.execute(
                "SELECT * FROM approvals WHERE app_id=? AND revision=?",
                (app["id"], app["revision"]),
            ).fetchone()
            if prior and prior["state"] != "approved":
                raise SandboxError("new_review_required")
            if prior is None:
                db.execute(
                    "INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?)",
                    (
                        reference("approval"),
                        app["id"],
                        app["revision"],
                        scope,
                        quote.quote_id,
                        expected,
                        "approved",
                        now.isoformat(),
                    ),
                )
            db.execute(
                "UPDATE applications SET state='approved',updated_at=? WHERE id=?",
                (now.isoformat(), app["id"]),
            )
        return app["id"]

    def purchase(self, scope, app_id):
        with self.transaction() as db:
            app = self.read_app(db, scope, app_id)
            if db.execute(
                "SELECT 1 FROM payments WHERE app_id=?", (app_id,)
            ).fetchone():
                return
            if app["state"] != "approved":
                raise SandboxError("approval_required")
        try:
            quote = self.current_quote(scope, app["quote_id"])
        except (SandboxError, PolicyError):
            self.invalidate(scope, app_id)
            raise
        with self.transaction() as db:
            app = self.read_app(db, scope, app_id)
            if db.execute(
                "SELECT 1 FROM payments WHERE app_id=?", (app_id,)
            ).fetchone():
                return
            revision = db.execute(
                "SELECT * FROM revisions WHERE app_id=? AND revision=?",
                (app_id, app["revision"]),
            ).fetchone()
            approval = db.execute(
                "SELECT * FROM approvals WHERE app_id=? AND revision=? AND scope=? "
                "AND state='approved'",
                (app_id, app["revision"], scope),
            ).fetchone()
            fields = ApplicationFields.model_validate_json(revision["fields"])
            stored_quote = self.read_quote(db, scope, app["quote_id"])
            expected = self.binding(
                scope,
                app_id,
                app["revision"],
                stored_quote,
                fields,
                revision["expires_at"],
                revision["challenge_hash"],
            )
            if (
                app["state"] != "approved"
                or approval is None
                or stored_quote != quote
                or approval["quote_id"] != quote.quote_id
                or approval["digest"] != expected
                or revision["digest"] != expected
            ):
                raise SandboxError("approval_binding_changed")
            now = self.now()
            if now >= quote.expires_at or now >= datetime.fromisoformat(
                revision["expires_at"]
            ):
                raise SandboxError("approval_expired")
            payment_id, transaction_ref = reference("pay"), reference("txn")
            mode = fields.payment_outcome
            payment_state = {
                "success": "succeeded",
                "failure": "failed",
                "unknown": "unknown",
            }[mode]
            confirmation = reference("demo") if mode == "success" else None
            db.execute(
                "INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    payment_id,
                    app_id,
                    approval["id"],
                    "payment:" + app_id,
                    quote.premium_paise,
                    "INR",
                    payment_state,
                    confirmation,
                    transaction_ref,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            # Actual deterministic sandbox gateway effect, atomically recorded once.
            db.execute(
                "INSERT INTO payment_ledger VALUES (?,?,?,?,?)",
                (
                    payment_id,
                    transaction_ref,
                    "failed" if mode == "failure" else "succeeded",
                    0 if mode == "failure" else quote.premium_paise,
                    now.isoformat(),
                ),
            )
            state = {
                "success": "completed",
                "failure": "failed",
                "unknown": "payment_pending",
            }[mode]
            db.execute(
                "UPDATE applications SET state=?,updated_at=? WHERE id=?",
                (state, now.isoformat(), app_id),
            )
            db.execute(
                "UPDATE approvals SET state='consumed' WHERE id=?", (approval["id"],)
            )

    def reconcile(self, scope, app_id):
        with self.transaction() as db:
            app = self.read_app(db, scope, app_id)
        if app["state"] == "approved":
            self.purchase(scope, app_id)
        with self.transaction() as db:
            app = self.read_app(db, scope, app_id)
            payment = db.execute(
                "SELECT * FROM payments WHERE app_id=?", (app_id,)
            ).fetchone()
            if payment and payment["state"] == "unknown":
                effect = db.execute(
                    "SELECT * FROM payment_ledger WHERE payment_id=?", (payment["id"],)
                ).fetchone()
                if effect:
                    success = effect["authoritative_state"] == "succeeded"
                    if (
                        effect["amount_paise"]
                        != (payment["amount_paise"] if success else 0)
                        or effect["transaction_ref"] != payment["transaction_ref"]
                    ):
                        raise SandboxError("payment_reconciliation_conflict")
                    now = self.now().isoformat()
                    db.execute(
                        "UPDATE payments SET state=?,confirmation=?,updated_at=? "
                        "WHERE id=?",
                        (
                            effect["authoritative_state"],
                            reference("demo") if success else None,
                            now,
                            payment["id"],
                        ),
                    )
                    db.execute(
                        "UPDATE applications SET state=?,updated_at=? WHERE id=?",
                        ("completed" if success else "failed", now, app_id),
                    )

    def cancel(self, scope, app_id):
        with self.transaction() as db:
            app = self.read_app(db, scope, app_id)
            if app["state"] == "cancelled":
                return
            if (
                app["state"] not in ("review", "approved", "needs_review")
                or db.execute(
                    "SELECT 1 FROM payments WHERE app_id=?", (app_id,)
                ).fetchone()
            ):
                raise SandboxError("cancellation_not_allowed")
            db.execute(
                "UPDATE applications SET state='cancelled',updated_at=? WHERE id=?",
                (self.now().isoformat(), app_id),
            )
            db.execute(
                "UPDATE approvals SET state='invalidated' "
                "WHERE app_id=? AND state='approved'",
                (app_id,),
            )

    def view(self, scope, ref, *, reconcile=False):
        from coverwise.sandbox_ui import quote_command

        if ref.startswith("op-"):
            with self.transaction() as db:
                op = db.execute(
                    "SELECT * FROM operations WHERE id=?", (ref,)
                ).fetchone()
                if op is None:
                    return dict(
                        state="operation_pending",
                        reference=ref,
                        error_code="operation_unknown_do_not_repeat",
                        next_commands=["/sandbox-status " + ref],
                    )
                if op["scope"] != scope:
                    raise SandboxError("not_found_or_not_authorized")
                if op["state"] == "rejected":
                    return dict(
                        state="rejected",
                        reference=ref,
                        error_code=op["error_code"],
                        next_commands=["/sandbox-status " + ref],
                    )
                if op["reference"] is None or (
                    op["state"] == "pending" and not op["reference"].startswith("a-")
                ):
                    return dict(
                        state="operation_pending",
                        reference=ref,
                        next_commands=["/sandbox-status " + ref],
                    )
                ref = op["reference"]
        if ref.startswith("a-") and reconcile:
            self.reconcile(scope, ref)
        with self.transaction() as db:
            if ref.startswith("q-"):
                quote = self.read_quote(db, scope, ref)
                active = self.now() < quote.expires_at
                used = db.execute(
                    "SELECT app_id FROM revisions WHERE quote_id=? LIMIT 1", (ref,)
                ).fetchone()
                return dict(
                    state="quote_active" if active else "quote_expired",
                    reference=ref,
                    quote=quote,
                    next_commands=["/sandbox-status " + used["app_id"]]
                    if used
                    else [f"/apply {ref} confirm-demo success"]
                    if active
                    else [quote_command(quote), "/sandbox-status " + ref],
                )
            app = self.read_app(db, scope, ref)
            revision = db.execute(
                "SELECT * FROM revisions WHERE app_id=? AND revision=?",
                (ref, app["revision"]),
            ).fetchone()
            quote = self.read_quote(db, scope, app["quote_id"])
            fields = ApplicationFields.model_validate_json(revision["fields"])
            application = ApplicationView(
                application_id=ref,
                revision=app["revision"],
                state=app["state"],
                quote=quote,
                fields=fields,
                review_digest=revision["digest"],
                challenge_expires_at=revision["expires_at"],
            )
            row = db.execute("SELECT * FROM payments WHERE app_id=?", (ref,)).fetchone()
            payment = (
                PaymentView(
                    payment_id=row["id"],
                    state=row["state"],
                    amount_paise=row["amount_paise"],
                    currency=row["currency"],
                    confirmation=row["confirmation"],
                    transaction_reference=row["transaction_ref"],
                )
                if row
                else None
            )
            commands = ["/sandbox-status " + ref]
            if app["state"] in ("review", "needs_review"):
                commands.append(
                    quote_command(quote)
                    if self.now() >= quote.expires_at or app["state"] == "needs_review"
                    else "/review " + ref
                )
            if app["state"] in ("review", "approved", "needs_review"):
                commands.append("/cancel " + ref)
            return dict(
                state=app["state"],
                reference=ref,
                application=application,
                payment=payment,
                next_commands=commands,
            )

    def execute(self, sender, session, operation_uuid, command):
        """Persist before expensive work; serialize local work, not SDK sends."""
        scope = owner_scope(sender, session)
        operation_id = "op-" + operation_uuid.hex
        with self.work_lock:
            with self.transaction() as db:
                prior = db.execute(
                    "SELECT * FROM operations WHERE id=?", (operation_id,)
                ).fetchone()
                if prior:
                    if prior["scope"] != scope or prior["command_digest"] != digest(
                        command
                    ):
                        raise SandboxError("operation_conflict")
                else:
                    db.execute(
                        "INSERT INTO operations VALUES (?,?,?,?,?,?,?,?)",
                        (
                            operation_id,
                            scope,
                            command.action,
                            digest(command),
                            command.reference,
                            "pending",
                            None,
                            self.now().isoformat(),
                        ),
                    )
            challenge = None
            try:
                if prior:
                    view = self.view(scope, operation_id)
                else:
                    if command.action == "quote":
                        ref, challenge = self.make_quote(scope, command, operation_id)
                    elif command.action in ("apply", "review"):
                        ref, challenge = self.review(scope, command, operation_id)
                    elif command.action == "approve":
                        ref = self.authorize(scope, command)
                        self.purchase(scope, ref)
                    elif command.action == "cancel":
                        ref = command.reference
                        self.cancel(scope, ref)
                    else:
                        ref = command.reference
                    view = self.view(scope, ref, reconcile=command.action == "status")
                    with self.transaction() as db:
                        db.execute(
                            "UPDATE operations SET reference=?,state='done' WHERE id=?",
                            (ref, operation_id),
                        )
                if challenge:
                    view["challenge"] = challenge
                    view["next_commands"] = [
                        f"/approve {view['reference']} "
                        f"{view['application'].revision} {challenge}",
                        "/cancel " + view["reference"],
                    ]
                reply = SandboxReply(
                    operation_id=operation_id,
                    action=command.action,
                    scope=scope,
                    **view,
                )
            except (SandboxError, PolicyError) as exc:
                code = str(exc)
                if (
                    command.reference
                    and command.reference.startswith("a-")
                    and code
                    in {
                        "quote_expired",
                        "quote_terms_changed",
                        "quote_integrity_failure",
                        "review_integrity_failure",
                        "approval_binding_changed",
                        "approval_expired",
                        "review_or_quote_expired",
                    }
                ):
                    self.invalidate(scope, command.reference)
                with self.transaction() as db:
                    db.execute(
                        "UPDATE operations SET state='rejected',error_code=? "
                        "WHERE id=?",
                        (code, operation_id),
                    )
                reply = SandboxReply(
                    operation_id=operation_id,
                    action=command.action,
                    scope=scope,
                    state="rejected",
                    reference=command.reference or operation_id,
                    error_code=code,
                    next_commands=[
                        "/sandbox-status " + (command.reference or operation_id),
                        "/sandbox",
                    ],
                )
            LOGGER.info(
                "role=provider event=sandbox_transition request_id=%s "
                "stage=provider_sandbox action=%s state=%s outcome=%s",
                operation_uuid,
                command.action,
                reply.state,
                reply.error_code or "success",
            )
            return reply

    def counts(self):
        with self.transaction() as db:
            return {
                name: db.execute("SELECT count(*) FROM " + name).fetchone()[0]
                for name in (
                    "quotes",
                    "applications",
                    "revisions",
                    "approvals",
                    "payments",
                    "payment_ledger",
                    "operations",
                )
            }
