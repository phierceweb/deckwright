from dataclasses import FrozenInstanceError

import pytest

from deckwright.qa.model import Finding, QaReport, Severity


def _f(slide=1, severity=Severity.ERROR, check="bounds", detail="d"):
    return Finding(slide=slide, check=check, severity=severity, detail=detail)


def test_severity_orders_error_above_warn_above_info():
    assert Severity.ERROR.rank > Severity.WARN.rank > Severity.INFO.rank


def test_count_totals_one_severity():
    report = QaReport(deck="d.pptx", findings=(_f(), _f(), _f(severity=Severity.WARN)))
    assert report.count(Severity.ERROR) == 2


def test_worst_returns_the_highest_severity_present():
    assert (
        QaReport(
            deck="d", findings=(_f(severity=Severity.WARN), _f(severity=Severity.INFO))
        ).worst()
        is Severity.WARN
    )


def test_worst_is_none_for_a_clean_report():
    assert QaReport(deck="d", findings=()).worst() is None


def test_by_slide_groups_and_sorts():
    report = QaReport(deck="d", findings=(_f(slide=3), _f(slide=1), _f(slide=3)))
    grouped = report.by_slide()
    assert list(grouped) == [1, 3]
    assert len(grouped[3]) == 2


def test_exceeds_is_true_when_a_finding_meets_the_threshold():
    assert QaReport(deck="d", findings=(_f(severity=Severity.ERROR),)).exceeds(Severity.WARN)


def test_exceeds_is_false_below_the_threshold():
    assert not QaReport(deck="d", findings=(_f(severity=Severity.INFO),)).exceeds(Severity.WARN)


def test_a_clean_report_never_exceeds():
    assert not QaReport(deck="d", findings=()).exceeds(Severity.INFO)


def test_findings_are_frozen():
    with pytest.raises(FrozenInstanceError):
        _f().slide = 9


def test_report_converts_list_to_tuple_and_isolates_from_mutations():
    findings_list = [_f(slide=1), _f(slide=2)]
    report = QaReport(deck="d", findings=findings_list)
    assert isinstance(report.findings, tuple)
    assert len(report.findings) == 2
    findings_list.append(_f(slide=3))
    assert len(report.findings) == 2
