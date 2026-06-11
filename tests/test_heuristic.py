"""Tests for the default heuristic classifier.

These double as a spec for the weighted model: a tool fingerprint or a
booking+keywords pair is cold; a single weak signal is not; known senders and
signal-free mail are spared. A contributor changing heuristic.py should keep
these passing (or update them deliberately).
"""

import pytest

from coldwar.classifiers.heuristic import COLD_THRESHOLD, HeuristicClassifier
from tests.fixtures import BORDERLINE, COLD, WANTED


@pytest.fixture
def clf():
    return HeuristicClassifier()


@pytest.mark.parametrize("msg", COLD, ids=lambda m: m.id)
def test_cold_messages_are_flagged(clf, msg):
    verdict = clf.classify(msg)
    assert verdict.is_cold is True
    assert verdict.score >= COLD_THRESHOLD
    # The dashboard relies on reasons explaining *why* — never flag silently.
    assert verdict.reasons
    assert any("first contact" in r for r in verdict.reasons)


@pytest.mark.parametrize("msg", BORDERLINE, ids=lambda m: m.id)
def test_single_weak_signal_is_not_cold(clf, msg):
    """A booking link alone, or sales keywords alone, stays under threshold —
    but the signal still fired, so score > 0 and the reason is recorded."""
    verdict = clf.classify(msg)
    assert verdict.is_cold is False
    assert 0.0 < verdict.score < COLD_THRESHOLD
    assert verdict.reasons  # the weak signal is still surfaced


@pytest.mark.parametrize("msg", WANTED, ids=lambda m: m.id)
def test_wanted_messages_are_not_flagged(clf, msg):
    verdict = clf.classify(msg)
    assert verdict.is_cold is False


def test_known_sender_is_skipped_entirely(clf):
    from tests.fixtures import WANTED_KNOWN_SENDER

    # Not first contact: short-circuits regardless of cold-looking content.
    verdict = clf.classify(WANTED_KNOWN_SENDER)
    assert verdict.is_cold is False
    assert verdict.score == 0.0
    assert verdict.reasons == []


def test_reasons_name_the_specific_signal(clf):
    from tests.fixtures import COLD_BOOKING_AND_KEYWORDS, COLD_OUTREACH_TOOL

    booking = clf.classify(COLD_BOOKING_AND_KEYWORDS)
    assert any("booking link" in r for r in booking.reasons)
    assert any("sales-intent" in r for r in booking.reasons)

    tool = clf.classify(COLD_OUTREACH_TOOL)
    assert any("outreach-tool fingerprint" in r for r in tool.reasons)


def test_score_orders_by_signal_strength(clf):
    from tests.fixtures import (
        BORDERLINE_KEYWORDS_ONLY,
        COLD_BOOKING_AND_KEYWORDS,
        COLD_OUTREACH_TOOL,
    )

    tool = clf.classify(COLD_OUTREACH_TOOL).score
    pair = clf.classify(COLD_BOOKING_AND_KEYWORDS).score
    weak = clf.classify(BORDERLINE_KEYWORDS_ONLY).score
    # tool fingerprint > booking+keywords > a single weak signal.
    assert tool >= pair > weak
