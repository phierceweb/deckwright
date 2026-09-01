"""QA findings.

Findings are data, never exceptions: a deck with problems still builds, and only an
explicit ``--fail-on`` threshold turns them into a non-zero exit.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    """How much a finding matters."""

    ERROR = "error"
    WARN = "warn"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"info": 0, "warn": 1, "error": 2}[self.value]


@dataclass(frozen=True)
class Finding:
    """One problem found on one slide."""

    slide: int
    check: str
    severity: Severity
    detail: str
    box: tuple[float, float, float, float] | None = None  # left, top, width, height
    shape: str | None = None


@dataclass(frozen=True)
class QaReport:
    """Every finding for one deck."""

    deck: str
    findings: tuple[Finding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity is severity)

    def worst(self) -> Severity | None:
        return max((f.severity for f in self.findings), key=lambda s: s.rank, default=None)

    def by_slide(self) -> dict[int, list[Finding]]:
        grouped: dict[int, list[Finding]] = defaultdict(list)
        for finding in self.findings:
            grouped[finding.slide].append(finding)
        return {index: grouped[index] for index in sorted(grouped)}

    def exceeds(self, threshold: Severity) -> bool:
        worst = self.worst()
        return worst is not None and worst.rank >= threshold.rank
