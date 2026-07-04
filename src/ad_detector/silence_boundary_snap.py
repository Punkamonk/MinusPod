"""Snap detected ad edges to nearby silence spans (task B3, Phase B).

DAI ads are bracketed by short silences inserted by the ad-injection
platform. When the LLM places an edge a second or two away from the real
silence, snapping to the silence midpoint lands the cut in dead air and the
retained half reconstitutes one natural pause.

Cue snap runs first and is stronger evidence; silence snap skips any edge
already committed by cue snap. Pure function; no DB, no LLM, no IO.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from config import MIN_AD_DURATION_FOR_REMOVAL, MERGE_GAP_SECONDS

logger = logging.getLogger('podcast.claude.silence_snap')


def _midpoint(span: Dict) -> float:
    return (span['start'] + span['end']) / 2.0


def _span_duration(span: Dict) -> float:
    return span.get('duration', span['end'] - span['start'])


def _pick_span(
    spans: List[Dict],
    edge: float,
    max_distance_s: float,
    min_silence_s: float,
    exclude_ids: set,
    proposed_must_be_less_than: Optional[float] = None,
    proposed_must_be_greater_than: Optional[float] = None,
) -> Optional[Dict]:
    """Return the best silence span to snap ``edge`` to.

    Selection key: nearest midpoint first; ties within 0.1s -> longer silence.
    """
    # Cache (span, mid, dur) so the max() key never recomputes them.
    candidates = []
    for span in spans:
        if id(span) in exclude_ids:
            continue
        dur = _span_duration(span)
        if dur < min_silence_s:
            continue
        mid = _midpoint(span)
        dist = abs(mid - edge)
        if dist > max_distance_s:
            continue
        if dist < 0.01:
            continue
        if proposed_must_be_less_than is not None and mid >= proposed_must_be_less_than:
            continue
        if proposed_must_be_greater_than is not None and mid <= proposed_must_be_greater_than:
            continue
        candidates.append((span, mid, dur))

    if not candidates:
        return None

    # Nearest first; within 0.1s bucket -> longer silence wins.
    best, _, _ = max(candidates, key=lambda t: (-round(abs(t[1] - edge), 1), t[2]))
    return best


def snap_ad_boundaries_to_silence(
    ads: List[Dict],
    silence_spans: List[Dict],
    max_distance_s: float,
    min_silence_s: float,
) -> None:
    """Mutate ads in place, snapping each start/end to a nearby silence midpoint.

    Contract mirrors snap_ad_boundaries_to_cues: same guards, same audit record
    layout (silence_snap instead of cue_snap). Cue snap runs first; any edge
    already in ad['cue_snap'] is skipped.

    Also sorts ads by start in place (needed for neighbour gap checks).

    Guards (mandatory):
      a. If pre-snap duration >= MIN_AD_DURATION_FOR_REMOVAL and the snap would
         reduce the ad below that threshold, revert the entire ad's silence snap.
      b. Reject an edge snap that would leave < MERGE_GAP_SECONDS between this
         ad and its neighbour.
    """
    if not ads or not silence_spans:
        return

    # Sort ads by start so neighbour lookup is deterministic.
    ads.sort(key=lambda a: a.get('start', 0.0))

    for idx, ad in enumerate(ads):
        try:
            original_start = float(ad['start'])
            original_end = float(ad['end'])
        except (KeyError, TypeError, ValueError):
            continue

        pre_snap_duration = original_end - original_start
        cue_snap = ad.get('cue_snap') or {}
        # Tracks spans already committed to one edge so they cannot snap the other.
        used_span_ids: set = set()
        snap_record: Dict = {}
        new_start = original_start
        new_end = original_end

        # --- Start edge ------------------------------------------------
        if 'start' not in cue_snap:
            prev_ad = ads[idx - 1] if idx > 0 else None
            prev_end = prev_ad.get('end') if prev_ad else None

            span = _pick_span(
                silence_spans, original_start,
                max_distance_s=max_distance_s,
                min_silence_s=min_silence_s,
                exclude_ids=used_span_ids,
                proposed_must_be_less_than=original_end,
            )
            if span is not None:
                mid = round(_midpoint(span), 3)
                # Merge-gap guard: reject if gap to preceding ad is too small.
                gap_ok = (prev_end is None) or (mid - prev_end >= MERGE_GAP_SECONDS)
                if gap_ok:
                    new_start = mid
                    snap_record['start'] = _build_record(original_start, mid, span)
                    used_span_ids.add(id(span))
                    logger.info(
                        'Silence snap (start): %.3fs -> %.3fs '
                        '(delta=%+.3fs, silence=%.3f-%.3f)',
                        original_start, new_start, new_start - original_start,
                        span['start'], span['end'],
                    )
                else:
                    logger.info(
                        'Silence snap (start) skipped: merge-gap guard '
                        '(prev_end=%.3f proposed_start=%.3f gap=%.3fs < %.1fs)',
                        prev_end, mid, mid - prev_end, MERGE_GAP_SECONDS,
                    )

        # --- End edge --------------------------------------------------
        if 'end' not in cue_snap:
            next_ad = ads[idx + 1] if idx < len(ads) - 1 else None
            next_start = next_ad.get('start') if next_ad else None

            span = _pick_span(
                silence_spans, original_end,
                max_distance_s=max_distance_s,
                min_silence_s=min_silence_s,
                exclude_ids=used_span_ids,
                proposed_must_be_greater_than=new_start,
            )
            if span is not None:
                mid = round(_midpoint(span), 3)
                # Merge-gap guard: reject if gap to following ad is too small.
                gap_ok = (next_start is None) or (next_start - mid >= MERGE_GAP_SECONDS)
                if gap_ok:
                    new_end = mid
                    snap_record['end'] = _build_record(original_end, mid, span)
                    used_span_ids.add(id(span))
                    logger.info(
                        'Silence snap (end): %.3fs -> %.3fs '
                        '(delta=%+.3fs, silence=%.3f-%.3f)',
                        original_end, new_end, new_end - original_end,
                        span['start'], span['end'],
                    )
                else:
                    logger.info(
                        'Silence snap (end) skipped: merge-gap guard '
                        '(next_start=%.3f proposed_end=%.3f gap=%.3fs < %.1fs)',
                        next_start, mid, next_start - mid, MERGE_GAP_SECONDS,
                    )

        if not snap_record:
            continue

        # Guard A: if the pre-snap ad was long enough to be removable and the
        # snap shrinks it below the removal threshold, revert entirely.
        # Rationale: compute_applied_cuts silently drops sub-threshold cuts.
        snapped_duration = new_end - new_start
        if (
            pre_snap_duration >= MIN_AD_DURATION_FOR_REMOVAL
            and snapped_duration < MIN_AD_DURATION_FOR_REMOVAL
        ):
            logger.info(
                'Silence snap reverted for %.3f-%.3f: snapped duration %.3fs '
                'would fall below removal threshold %.1fs',
                original_start, original_end, snapped_duration, MIN_AD_DURATION_FOR_REMOVAL,
            )
            continue

        ad['start'] = new_start
        ad['end'] = new_end
        ad['silence_snap'] = snap_record


def _build_record(original: float, snap_point: float, span: Dict) -> Dict:
    """Build the per-edge audit record (mirrors _snap_record in cue_boundary_snap)."""
    return {
        'original': round(original, 3),
        'silence_start': round(span['start'], 3),
        'silence_end': round(span['end'], 3),
        'snap_point': round(snap_point, 3),
        'shift_seconds': round(snap_point - original, 3),
        'silence_duration': round(_span_duration(span), 3),
    }
