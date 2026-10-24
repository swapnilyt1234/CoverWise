"""Reproduce allowlisted synthetic PDFs from editable JSON sources."""

import hashlib
import io
import json
import textwrap
from pathlib import Path

from coverwise.policies import ASSET_ROOT, CANDIDATES, PDF_DIR, REGISTRY

WARNING = "Synthetic demo policy — no real insurance"


def generate(source: dict, output: Path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen.canvas import Canvas

    output.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=A4, invariant=1, pageCompression=1)
    canvas.setTitle(source["title"] + " — synthetic demo")
    canvas.setAuthor("CoverWise synthetic fixtures")
    width, height = A4
    for number, page in enumerate(source["pages"], 1):
        canvas.setFillColorRGB(0.08, 0.2, 0.3)
        canvas.rect(0, height - 125, width, 125, fill=1, stroke=0)
        canvas.setFillColorRGB(1, 1, 1)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(48, height - 48, source["title"])
        canvas.setFont("Helvetica", 10)
        canvas.drawString(48, height - 70, source["insurer"])
        canvas.drawString(
            48, height - 91, f"{source['id']} | version {source['version']}"
        )
        canvas.setFillColorRGB(0.12, 0.16, 0.2)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(48, height - 155, page["heading"])
        y = height - 191
        for clause in page["clauses"]:
            text = f"{clause['id']} | {clause['term']}: {clause['value']}"
            text += f" [END {clause['id']}]"
            lines = textwrap.wrap(text, width=80, break_long_words=False)
            if y - len(lines) * 16 < 105:
                raise ValueError(
                    "Fixture page overflow; split the editable source page"
                )
            canvas.setFont("Helvetica", 10)
            for line in lines:
                canvas.drawString(48, y, line)
                y -= 16
            y -= 22
        canvas.setStrokeColorRGB(0.7, 0.75, 0.8)
        canvas.line(48, 83, width - 48, 83)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(48, 62, WARNING)
        canvas.setFont("Helvetica", 9)
        canvas.drawString(48, 44, f"Page {number} of {len(source['pages'])}")
        canvas.showPage()
    canvas.save()
    temporary = output.with_suffix(".pdf.tmp")
    try:
        temporary.write_bytes(buffer.getvalue())
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    try:
        import reportlab  # noqa: F401
    except ImportError:
        print("Generation unavailable: install development dependencies (ReportLab).")
        return 1
    for policy_id, spec in (REGISTRY | CANDIDATES).items():
        source_path = ASSET_ROOT / "fixtures" / "policies" / f"{policy_id}.json"
        source = json.loads(source_path.read_text(encoding="utf-8"))
        if source["id"] != policy_id or source["version"] != spec.version:
            raise ValueError("Registry/source identity mismatch")
        generate(source, PDF_DIR / spec.filename)
        print(f"Generated {policy_id}: {len(source['pages'])} pages")
    from coverwise.catalogue import load_catalogue

    for product in load_catalogue().catalogue.products:
        path = PDF_DIR / CANDIDATES[product.document.document_id].filename
        if hashlib.sha256(path.read_bytes()).hexdigest() != product.document.sha256:
            raise ValueError(
                "Generated candidate hash differs from versioned catalogue"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
