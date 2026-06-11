"""Tests for the default heuristic classifier.

These double as a spec: a contributor changing heuristic.py should keep cold mail
flagged and wanted mail untouched.
"""

import pytest

from coldwar.classifiers.heuristic import HeuristicClassifier
from tests.fixtures import COLD, WANTED


@pytest.fixture
def clf():
    return HeuristicClassifier()


@pytest.mark.parametrize("msg", COLD, ids=lambda m: m.id)
def test_cold_messages_are_flagged(clf, msg):
    verdict = clf.classify(msg)
    assert verdict.is_cold is True
    assert verdict.score > 0
    # The dashboard relies on reasons explaining *why* — never flag silently.
    assert verdict.reasons
    assert any("first contact" in r for r in verdict.reasons)


@pytest.mark.parametrize("msg", WANTED, ids=lambda m: m.id)
def test_wanted_messages_are_not_flagged(clf, msg):
    verdict = clf.classify(msg)
    assert verdict.is_cold is False
    assert verdict.score == 0.0
    assert verdict.reasons == []


def test_reasons_name_the_specific_signal(clf):
    from tests.fixtures import COLD_BOOKING_LINK, COLD_OUTREACH_TOOL

    booking = clf.classify(COLD_BOOKING_LINK)
    assert any("booking link" in r for r in booking.reasons)

    tool = clf.classify(COLD_OUTREACH_TOOL)
    assert any("outreach-tool fingerprint" in r for r in tool.reasons)


def test_more_signals_means_higher_score(clf):
    from tests.fixtures import COLD_SALES_KEYWORDS, COLD_OUTREACH_TOOL

    # COLD_OUTREACH_TOOL fires keywords + tool fingerprint; one-signal mail scores
    # lower than multi-signal mail.
    one_signal = clf.classify(COLD_SALES_KEYWORDS)
    multi_signal = clf.classify(COLD_OUTREACH_TOOL)
    assert multi_signal.score >= one_signal.score
