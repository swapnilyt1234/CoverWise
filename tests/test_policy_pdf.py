"""Real-PDF integration tests; skipped explicitly until PDF dependencies exist."""

import hashlib
import io
import json

import pytest

pypdf = pytest.importorskip("pypdf", reason="Install declared PDF dependencies")
pytest.importorskip(
    "reportlab", reason="Install declared generation development dependency"
)

from coverwise import policies  # noqa: E402
from coverwise.generate_policies import generate  # noqa: E402


@pytest.fixture
def generated(tmp_path, monkeypatch):
    monkeypatch.setattr(policies, "PDF_DIR", tmp_path)
    sources = {}
    for policy_id, spec in policies.REGISTRY.items():
        source = json.loads(
            (policies.ROOT / "fixtures" / "policies" / f"{policy_id}.json").read_text(
                encoding="utf-8"
            )
        )
        sources[policy_id] = source
        generate(source, tmp_path / spec.filename)
    return tmp_path, sources


@pytest.mark.parametrize("policy_id", ["existing-employer", "existing-personal"])
def test_pdf_bytes_terms_hash_and_all_page_evidence(generated, policy_id):
    root, _ = generated
    path = root / policies.REGISTRY[policy_id].filename
    report = policies.load_policy(policy_id)
    assert report.document.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    reader = pypdf.PdfReader(path)
    assert report.document.page_count == len(reader.pages)
    for term in report.terms:
        for evidence in term.evidence:
            page = reader.pages[evidence.locator.page - 1].extract_text()
            assert policies.normalize(evidence.excerpt) in policies.normalize(page)
    terms = {term.name: term for term in report.terms}
    assert terms["Deductible"].value.startswith("None")
    assert terms["Renewal date"].status == "not_stated"
    if policy_id == "existing-employer":
        assert "2026-12-31" in terms["Employment termination"].value
        assert terms["Event sublimits"].status == "ambiguous"
    else:
        assert terms["Pre-existing condition wait"].status == "not_stated"


def test_changed_pdf_changes_terms_hash_and_conflicting_sources(generated):
    root, sources = generated
    before = policies.load_policy("existing-employer")
    source = sources["existing-employer"]
    source["pages"][0]["clauses"][2]["value"] = (
        "50000000 INR paise, shared family limit."
    )
    generate(source, root / "existing-employer.pdf")
    after = policies.load_policy("existing-employer")
    assert before.document.sha256 != after.document.sha256
    assert next(t.value for t in after.terms if t.name == "Sum insured").startswith(
        "50000000"
    )
    source["pages"][2]["clauses"].append(
        {"id": "EMP-99", "term": "Sum insured", "value": "100000000 INR paise."}
    )
    generate(source, root / "existing-employer.pdf")
    conflict = next(
        t
        for t in policies.load_policy("existing-employer").terms
        if t.name == "Sum insured"
    )
    assert conflict.status == "conflict" and conflict.value is None
    assert {e.locator.page for e in conflict.evidence} == {1, 3}


@pytest.mark.parametrize(
    "kind, code",
    [
        ("malformed", "malformed_pdf"),
        ("blank", "no_extractable_text"),
        ("image", "no_extractable_text"),
        ("encrypted", "encrypted_pdf"),
        ("pages", "excessive_pages"),
    ],
)
def test_pdf_rejections(generated, kind, code):
    root, _ = generated
    path = root / "existing-employer.pdf"
    if kind == "malformed":
        path.write_bytes(b"%PDF-1.7\ncorrupt")
    elif kind == "image":
        from PIL import Image
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen.canvas import Canvas

        image = io.BytesIO()
        Image.new("RGB", (20, 20), "white").save(image, format="PNG")
        canvas = Canvas(str(path))
        canvas.drawImage(ImageReader(image), 0, 0, width=100, height=100)
        canvas.showPage()
        canvas.save()
    else:
        writer = pypdf.PdfWriter()
        for _ in range(7 if kind == "pages" else 1):
            writer.add_blank_page(width=100, height=100)
        if kind == "encrypted":
            writer.encrypt("synthetic-test-password")
        writer.write(path)
    with pytest.raises(policies.PolicyError, match=code):
        policies.load_policy("existing-employer")


def test_batch_worker_extracts_each_actual_pdf_and_verifies_evidence(
    generated, monkeypatch, capsys
):
    import sys
    from types import SimpleNamespace

    monkeypatch.setattr(
        sys,
        "argv",
        ["policies", "--batch-worker", "existing-employer", "existing-personal"],
    )
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b"\n\n")))
    assert policies.main() == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].encode() + b"\n" == policies.WORKER_READY
    reports = [
        policies.PolicyInspection.model_validate_json(line) for line in lines[1:]
    ]
    for identifier, report in zip(("existing-employer", "existing-personal"), reports):
        assert report == policies.load_policy(identifier)


def batch_process(monkeypatch, content, *, ready=True):
    """Bounded fake pipes for parent framing/error/cleanup checks."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    process = SimpleNamespace(
        stdin=io.BytesIO(),
        stdout=io.BytesIO((policies.WORKER_READY if ready else b"") + content),
        poll=lambda: 0,
        wait=lambda **_: 0,
        kill=Mock(),
    )
    factory = Mock(return_value=process)
    monkeypatch.setattr(policies.subprocess, "Popen", factory)
    return process, factory


def test_batch_parent_uses_one_interpreter_and_preserves_order(generated, monkeypatch):
    ids = ["existing-employer", "existing-personal"]
    reports = [policies.load_policy(p) for p in ids]
    content = b"\n".join(p.model_dump_json().encode() for p in reports) + b"\n"
    process, factory = batch_process(monkeypatch, content)
    assert policies.inspect_policies(ids) == reports
    factory.assert_called_once()
    assert factory.call_args.args[0][-3:] == ["--batch-worker", *ids]
    assert process.stdin.closed and process.stdout.closed


@pytest.mark.parametrize(
    "content,code",
    [
        (b"encrypted_pdf\n", "encrypted_pdf"),
        (b"private document details\n", "invalid_result"),
        (b"", "extraction_failed"),
        (b"x" * (policies.MAX_REPORT + 2), "result_too_large"),
        (b" " * (policies.MAX_REPORT + 1), "result_too_large"),
    ],
    ids=[
        "known-error",
        "untrusted-text",
        "empty",
        "oversized",
        "unterminated-oversized",
    ],
)
def test_batch_parent_rejects_bad_frames_without_partial_results(
    monkeypatch, content, code
):
    process, _ = batch_process(monkeypatch, content)
    with pytest.raises(policies.PolicyError, match=code):
        policies.inspect_policies(["existing-employer"])
    assert process.stdin.closed and process.stdout.closed


def test_batch_parent_rejects_wrong_document(generated, monkeypatch):
    content = (
        policies.load_policy("existing-personal").model_dump_json().encode() + b"\n"
    )
    batch_process(monkeypatch, content)
    with pytest.raises(policies.PolicyError, match="invalid_result"):
        policies.inspect_policies(["existing-employer"])


@pytest.mark.parametrize("stage", ["startup", "extraction"])
def test_batch_parent_keeps_deadline_and_reaps_timed_out_child(
    monkeypatch, stage, caplog
):
    import threading
    from types import SimpleNamespace
    from unittest.mock import Mock

    stopped = threading.Event()

    class SlowPipe:
        closed = False
        ready = False

        def readline(self, _limit):
            if stage == "extraction" and not self.ready:
                self.ready = True
                return policies.WORKER_READY
            assert stopped.wait(1)
            return b""

        def close(self):
            self.closed = True

    process = SimpleNamespace(
        stdin=io.BytesIO(),
        stdout=SlowPipe(),
        poll=lambda: 0 if stopped.is_set() else None,
        wait=lambda **_: 0,
        kill=stopped.set,
    )
    monkeypatch.setattr(policies.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(
        policies,
        "WORKER_STARTUP_SECONDS" if stage == "startup" else "WORKER_SECONDS",
        0.03,
    )
    caplog.set_level("INFO", logger="coverwise")
    with pytest.raises(policies.PolicyError, match="extraction_timeout"):
        policies.inspect_policies(["existing-employer"])
    assert stopped.is_set() and process.stdout.closed and process.stdin.closed
    assert (
        f"stage={'pdf_worker_startup' if stage == 'startup' else 'pdf_extraction'}"
        in caplog.text
    )
    assert "outcome=extraction_timeout" in caplog.text
    if stage == "startup":
        assert not process.stdout.ready


@pytest.mark.parametrize(
    "content,code",
    [
        (b"dependencies_unavailable\n", "dependencies_unavailable"),
        (b"private startup details\n", "invalid_result"),
        (b"", "extraction_failed"),
    ],
)
def test_batch_parent_requires_readiness_before_starting_a_pdf(
    monkeypatch, content, code
):
    process, _ = batch_process(monkeypatch, content, ready=False)
    with pytest.raises(policies.PolicyError, match=code):
        policies.inspect_policies(["existing-employer"])
    assert process.stdin.closed and process.stdout.closed


def test_batch_rejects_unknown_or_unbounded_ids_before_process_start(monkeypatch):
    from unittest.mock import Mock

    factory = Mock(side_effect=AssertionError("must validate before subprocess"))
    monkeypatch.setattr(policies.subprocess, "Popen", factory)
    for ids in ([], ["unknown"], ["existing-employer"] * 6):
        with pytest.raises(policies.PolicyError):
            policies.inspect_policies(ids)
    factory.assert_not_called()
