"""template_verdict_hint: rejects-near-threshold vs rejects-spread."""
from audio_analysis.cue_verdict_hints import (
    template_verdict_hint, HINT_RAISE_THRESHOLD, HINT_RECAPTURE,
)


def test_below_minimum_rejections_no_hint():
    assert template_verdict_hint([0.8, 0.81], [0.95], 0.75) is None
    assert template_verdict_hint([], [0.9, 0.9, 0.9], 0.75) is None


def test_clustered_just_above_threshold_raise():
    assert template_verdict_hint(
        [0.76, 0.78, 0.80], [0.92, 0.95], 0.75) == HINT_RAISE_THRESHOLD


def test_clustered_but_overlapping_confirmed_recapture():
    assert template_verdict_hint(
        [0.76, 0.78, 0.80], [0.79, 0.95], 0.75) == HINT_RECAPTURE


def test_spread_rejections_recapture():
    assert template_verdict_hint(
        [0.76, 0.88, 0.97], [0.99], 0.75) == HINT_RECAPTURE


def test_no_confirmed_clustered_still_raise():
    assert template_verdict_hint(
        [0.76, 0.77, 0.84], [], 0.75) == HINT_RAISE_THRESHOLD


def test_none_scores_filtered():
    assert template_verdict_hint([0.76, None, 0.78], [0.9], 0.75) is None
