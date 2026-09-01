"""Write a QA report as markdown for a human and JSON for a machine."""

from __future__ import annotations

from pathlib import Path

from pf_core.utils.io import atomic_write_json, atomic_write_text

from deckwright.qa.model import QaReport, Severity

_ICON = {Severity.ERROR: "✗", Severity.WARN: "!", Severity.INFO: "·"}


def write_markdown(report: QaReport, path: str | Path) -> Path:
    """Write ``report`` as markdown; returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# QA — {report.deck}", ""]
    if not report.findings:
        lines += ["No findings.", ""]
    else:
        counts = ", ".join(f"{report.count(s)} {s.value}" for s in Severity)
        lines += [counts, ""]
        for index, findings in report.by_slide().items():
            lines.append(f"## Slide {index}")
            lines += [
                f"- {_ICON[f.severity]} **{f.check}** — {' '.join(f.detail.split())}"
                for f in findings
            ]
            lines.append("")
    atomic_write_text(path, "\n".join(lines))
    return path


def write_json(report: QaReport, path: str | Path) -> Path:
    """Write ``report`` as JSON; returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "deck": report.deck,
        "counts": {s.value: report.count(s) for s in Severity},
        "findings": [
            {
                "slide": f.slide,
                "check": f.check,
                "severity": f.severity.value,
                "detail": f.detail,
                "shape": f.shape,
                "box": None if f.box is None else dict(zip("xywh", f.box, strict=True)),
            }
            for f in report.findings
        ],
    }
    atomic_write_json(path, payload, indent=2, ensure_ascii=False)
    return path
