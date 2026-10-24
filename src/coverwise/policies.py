"""Allowlisted synthetic PDF inspection; no arbitrary paths, URLs or OCR."""

import argparse
import hashlib
import io
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from time import monotonic

from coverwise.contracts import (
    ClauseEvidence,
    ExtractedTerm,
    PdfLocator,
    PolicyDocument,
    PolicyInspection,
)

BUNDLED_ASSETS = Path(__file__).resolve().parent / "data"
ROOT = Path.cwd() if BUNDLED_ASSETS.is_dir() else Path(__file__).resolve().parents[2]
ASSET_ROOT = BUNDLED_ASSETS if BUNDLED_ASSETS.is_dir() else ROOT
PDF_DIR = ASSET_ROOT / "output" / "pdf"
MAX_BYTES = 512 * 1024
MAX_PAGES = 6
MAX_PAGE_TEXT = 20_000
MAX_TOTAL_TEXT = 60_000
MAX_REPORT = 65_536
MAX_REPLY = 12_000
WORKER_SECONDS = 2
WORKER_STARTUP_SECONDS = 5
WORKER_READY = b"coverwise-pdf-ready-v1\n"
LOGGER = logging.getLogger("coverwise")
LABELS = (
    "Policy dates",
    "Covered members",
    "Sum insured",
    "Deductible",
    "Co-payment",
    "Room rent",
    "Waiting period",
    "Pre-existing condition wait",
    "Exclusions",
    "Employment termination",
    "Renewal date",
    "Annual premium",
    "Event sublimits",
    "Room deduction rule",
    "Eligibility",
    "Premium basis",
    "Identity",
)
CLAUSE = re.compile(r"\b([A-Z]{2,5}-\d{2}) \| ([A-Za-z -]{1,40}): (.*?) \[END \1\]")


@dataclass(frozen=True)
class PreloadedPolicy:
    title: str
    filename: str
    version: str = "1"


REGISTRY = {
    "existing-employer": PreloadedPolicy(
        "Harbor Employer Health", "existing-employer.pdf"
    ),
    "existing-personal": PreloadedPolicy(
        "Pebble Personal Health", "existing-personal.pdf"
    ),
}
CANDIDATES = {
    "candidate-economy": PreloadedPolicy("Lantern Economy", "candidate-economy.pdf"),
    "candidate-query": PreloadedPolicy("Lantern Query", "candidate-query.pdf"),
    "candidate-horizon": PreloadedPolicy("Lantern Horizon", "candidate-horizon.pdf"),
}


class PolicyError(Exception):
    """Safe machine-readable code only; never embed document text or paths."""


def normalize(text: str) -> str:
    return " ".join(text.split())


def policy_listing() -> str:
    lines = ["Configured fictional policies:"]
    for policy_id, spec in (REGISTRY | CANDIDATES).items():
        status = (
            "PDF present" if (PDF_DIR / spec.filename).is_file() else "PDF unavailable"
        )
        lines.append(f"- {policy_id}: {spec.title} ({status})")
    return (
        "\n".join(lines)
        + "\nUse /inspect <policy-id>, /stress-test preset, or /recommend (help). "
        "Use /sandbox for sandbox quote/application help. Synthetic demo only."
    )


def parse_pages(document: PolicyDocument, pages: list[str]) -> PolicyInspection:
    if not 1 <= len(pages) <= MAX_PAGES:
        raise PolicyError("excessive_pages")
    document = document.model_copy(update={"page_count": len(pages)})
    found: dict[str, list[tuple[str, ClauseEvidence]]] = {name: [] for name in LABELS}
    for page_number, page in enumerate(pages, 1):
        page = normalize(page)
        for match in CLAUSE.finditer(page):
            clause_id, label, value = match.groups()
            if label not in found:
                continue
            excerpt = match.group(0)
            if not value or len(value) > 280 or len(excerpt) > 400:
                raise PolicyError("term_too_large")
            key = (
                f"{document.sha256}|{document.document_version}|{page_number}|{excerpt}"
            )
            evidence = ClauseEvidence(
                evidence_id="ev-"
                + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24],
                document=document,
                clause_id=clause_id,
                locator=PdfLocator(page=page_number),
                excerpt=excerpt,
            )
            if normalize(evidence.excerpt) not in page:
                raise PolicyError("evidence_mismatch")
            found[label].append((value, evidence))
            if len(found[label]) > 4:
                raise PolicyError("too_many_sources")
    if not any(found.values()):
        raise PolicyError("unsupported_document")
    terms = []
    for label, sources in found.items():
        values = {value for value, _ in sources}
        if not sources:
            status = "not_stated"
        elif len(values) > 1:
            status = "conflict"
        elif next(iter(values)).startswith("UNCONFIRMED:"):
            status = "ambiguous"
        else:
            status = "stated"
        terms.append(
            ExtractedTerm(
                name=label,
                status=status,
                value=next(iter(values)) if status == "stated" else None,
                evidence=[evidence for _, evidence in sources],
            )
        )
    report = PolicyInspection(
        document=document,
        terms=terms,
        limitations=[
            "Limited parser for labelled synthetic clauses, not a general reader.",
            "Not stated means unknown; explicit none is not inferred from absence.",
            "This is extraction only, not a coverage assessment or payment assurance.",
        ],
    )
    verify_evidence(report, pages)
    return report


def verify_evidence(report: PolicyInspection, pages: list[str]):
    for term in report.terms:
        for evidence in term.evidence:
            locator = evidence.locator
            if (
                not isinstance(locator, PdfLocator)
                or locator.page > len(pages)
                or normalize(evidence.excerpt) not in normalize(pages[locator.page - 1])
            ):
                raise PolicyError("evidence_mismatch")


def load_policy(policy_id: str) -> PolicyInspection:
    if policy_id not in REGISTRY | CANDIDATES:
        raise PolicyError("unknown_policy_id")
    spec = (REGISTRY | CANDIDATES)[policy_id]
    try:
        path = (PDF_DIR / spec.filename).resolve(strict=True)
        if path.parent != PDF_DIR.resolve() or not path.is_file():
            raise PolicyError("invalid_registry_path")
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
    except OSError:
        raise PolicyError("document_unavailable") from None
    if len(data) > MAX_BYTES:
        raise PolicyError("oversized_file")
    if not data.startswith(b"%PDF-"):
        raise PolicyError("malformed_pdf")
    try:
        from pypdf import PdfReader
    except ImportError:
        raise PolicyError("dependencies_unavailable") from None
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise PolicyError("encrypted_pdf")
        if not 1 <= len(reader.pages) <= MAX_PAGES:
            raise PolicyError("excessive_pages")
        pages = []
        for page in reader.pages:
            contents = page.get_contents()
            if contents is not None and len(contents.get_data()) > 256 * 1024:
                raise PolicyError("excessive_page_stream")
            text = page.extract_text() or ""
            if not normalize(text):
                raise PolicyError("no_extractable_text")
            if len(text) > MAX_PAGE_TEXT:
                raise PolicyError("excessive_text")
            pages.append(text)
        if sum(map(len, pages)) > MAX_TOTAL_TEXT:
            raise PolicyError("excessive_text")
    except PolicyError:
        raise
    except Exception:
        raise PolicyError("malformed_pdf") from None
    document = PolicyDocument(
        document_id=policy_id,
        document_version=spec.version,
        sha256=hashlib.sha256(data).hexdigest(),
        source_type="pdf",
        title=spec.title,
        page_count=len(pages),
    )
    return parse_pages(document, pages)


def inspect_policy(policy_id: str) -> PolicyInspection:
    return inspect_policies([policy_id])[0]


def inspect_policies(policy_ids: list[str]) -> list[PolicyInspection]:
    """Reuse interpreter startup, with a fresh parser and deadline for each PDF."""
    if not 1 <= len(policy_ids) <= 5 or len(set(policy_ids)) != len(policy_ids):
        raise PolicyError("invalid_result")
    if any(p not in REGISTRY | CANDIDATES for p in policy_ids):
        raise PolicyError("unknown_policy_id")
    started = monotonic()
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "coverwise.policies", "--batch-worker", *policy_ids],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        raise PolicyError("extraction_failed") from None
    messages = Queue(maxsize=len(policy_ids) + 2)

    def read_reports():
        try:
            for _ in range(len(policy_ids) + 2):
                line = process.stdout.readline(MAX_REPORT + 2)
                messages.put_nowait(line)
                if not line:
                    break
        except (OSError, ValueError):
            messages.put_nowait(b"")

    reader = Thread(target=read_reports, daemon=True)
    reader.start()
    stage, stage_started, budget = "pdf_worker_startup", started, WORKER_STARTUP_SECONDS
    try:
        # Interpreter/dependency startup must not consume a PDF's parsing budget.
        ready = messages.get(timeout=max(0, started + budget - monotonic()))
        if len(ready.removesuffix(b"\n")) > MAX_REPORT:
            raise PolicyError("result_too_large")
        if not ready:
            raise PolicyError("extraction_failed")
        if ready != WORKER_READY:
            code = ready.decode("ascii", errors="ignore").strip()
            raise PolicyError(code if code in ERROR_CODES else "invalid_result")
        LOGGER.info(
            "event=pdf_worker_timing stage=%s elapsed_ms=%.3f "
            "deadline_s=%.3f outcome=ready",
            stage,
            (monotonic() - stage_started) * 1000,
            budget,
        )
        reports = []
        for policy_id in policy_ids:
            # The child cannot begin the next PDF until this deadline is armed.
            stage, stage_started, budget = "pdf_extraction", monotonic(), WORKER_SECONDS
            deadline = stage_started + budget
            process.stdin.write(b"\n")
            process.stdin.flush()
            line = messages.get(timeout=max(0, deadline - monotonic()))
            if len(line.removesuffix(b"\n")) > MAX_REPORT:
                raise PolicyError("result_too_large")
            if not line:
                raise PolicyError("extraction_failed")
            try:
                report = PolicyInspection.model_validate_json(line)
            except ValueError:
                code = line.decode("ascii", errors="ignore").strip()
                raise PolicyError(
                    code if code in ERROR_CODES else "invalid_result"
                ) from None
            spec = (REGISTRY | CANDIDATES)[policy_id]
            if (
                report.document.document_id != policy_id
                or report.document.document_version != spec.version
            ):
                raise PolicyError("invalid_result")
            reports.append(report)
            LOGGER.info(
                "event=pdf_worker_timing stage=%s policy_id=%s elapsed_ms=%.3f "
                "deadline_s=%.3f outcome=success",
                stage,
                policy_id,
                (monotonic() - stage_started) * 1000,
                budget,
            )
        stage, stage_started, budget = "pdf_worker_exit", monotonic(), WORKER_SECONDS
        if process.wait(timeout=WORKER_SECONDS):
            raise PolicyError("extraction_failed")
        return reports
    except (Empty, subprocess.TimeoutExpired):
        LOGGER.info(
            "event=pdf_worker_timing stage=%s elapsed_ms=%.3f deadline_s=%.3f "
            "outcome=extraction_timeout",
            stage,
            (monotonic() - stage_started) * 1000,
            budget,
        )
        raise PolicyError("extraction_timeout") from None
    except OSError:
        raise PolicyError("extraction_failed") from None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=WORKER_SECONDS)
        reader.join(timeout=WORKER_SECONDS)
        process.stdin.close()
        process.stdout.close()


ERROR_CODES = {
    "unknown_policy_id",
    "invalid_registry_path",
    "document_unavailable",
    "dependencies_unavailable",
    "oversized_file",
    "malformed_pdf",
    "encrypted_pdf",
    "excessive_pages",
    "excessive_page_stream",
    "no_extractable_text",
    "excessive_text",
    "unsupported_document",
    "term_too_large",
    "too_many_sources",
    "evidence_mismatch",
    "extraction_timeout",
    "extraction_failed",
    "result_too_large",
    "invalid_result",
}


def present(report: PolicyInspection) -> str:
    from coverwise.money import display_money

    doc = report.document
    lines = [
        f"Synthetic demo policy — no real insurance\n{doc.title}",
        f"ID: {doc.document_id}; version: {doc.document_version}; "
        f"pages: {doc.page_count}",
        f"SHA-256: {doc.sha256}",
        "Extracted terms (not a coverage assessment):",
    ]
    for term in report.terms:
        detail = f"- {term.name}: {term.status}"
        if term.value:
            detail += " — " + display_money(term.value)
        for evidence in term.evidence:
            excerpt = evidence.excerpt
            shortened = excerpt[:120] + (
                "… [excerpt shortened]" if len(excerpt) > 120 else ""
            )
            detail += (
                f"\n  p{evidence.locator.page}, {evidence.clause_id}, "
                f'{evidence.evidence_id}: "{shortened}"'
            )
        if len("\n".join(lines)) + len(detail) > MAX_REPLY - 600:
            lines.append("Further display details omitted due to reply limit.")
            break
        lines.append(detail)
    lines.extend(report.limitations)
    text = "\n".join(lines)
    if len(text) > MAX_REPLY:
        text = (
            text[: MAX_REPLY - 70]
            + "\nFurther display details omitted due to reply limit."
        )
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy_ids", nargs="+")
    workers = parser.add_mutually_exclusive_group()
    workers.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    workers.add_argument("--batch-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.batch_worker and len(args.policy_ids) != 1:
        parser.error("single-policy inspection requires exactly one policy ID")
    try:
        if args.batch_worker:
            if not 1 <= len(args.policy_ids) <= 5 or any(
                p not in REGISTRY | CANDIDATES for p in args.policy_ids
            ):
                raise PolicyError("unknown_policy_id")
            try:
                import_module("pypdf")
            except ImportError:
                raise PolicyError("dependencies_unavailable") from None
            sys.stdout.buffer.write(WORKER_READY)
            sys.stdout.buffer.flush()
            for policy_id in args.policy_ids:
                if sys.stdin.buffer.read(1) != b"\n":
                    return 1
                serialized = load_policy(policy_id).model_dump_json().encode("utf-8")
                if len(serialized) > MAX_REPORT:
                    raise PolicyError("result_too_large")
                sys.stdout.buffer.write(serialized + b"\n")
                sys.stdout.buffer.flush()
            return 0
        report = (
            load_policy(args.policy_ids[0])
            if args.worker
            else inspect_policy(args.policy_ids[0])
        )
        serialized = report.model_dump_json()
        if len(serialized.encode("utf-8")) > MAX_REPORT:
            raise PolicyError("result_too_large")
        if args.worker:
            sys.stdout.buffer.write(serialized.encode("utf-8"))
        else:
            print(present(report))
        return 0
    except PolicyError as exc:
        print(
            str(exc)
            if args.worker or args.batch_worker
            else f"Inspection unavailable: {exc}",
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
