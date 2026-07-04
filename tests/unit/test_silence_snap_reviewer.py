"""Unit tests: silence_snap in ad_reviewer._format_cue_section (task B3)."""
import os
import tempfile

os.environ.setdefault('MINUSPOD_DATA_DIR', tempfile.mkdtemp(prefix='silence_reviewer_test_'))
os.environ.setdefault('SECRET_KEY', 'test-secret')

from ad_reviewer import _format_cue_section


def test_silence_snap_line_in_prompt_when_start_snapped():
    silence_snap = {
        'start': {
            'original': 100.0,
            'silence_start': 98.0,
            'silence_end': 99.0,
            'snap_point': 98.5,
            'shift_seconds': -1.5,
            'silence_duration': 1.0,
        }
    }
    result = _format_cue_section(
        audio_analysis=None,
        ad_start=98.5,
        ad_end=160.0,
        silence_snap=silence_snap,
    )
    assert 'SILENCE SNAP APPLIED' in result
    assert 'start' in result
    assert '100.0' in result   # original boundary mentioned
    assert 'do not move it' in result


def test_silence_snap_line_in_prompt_when_end_snapped():
    silence_snap = {
        'end': {
            'original': 160.0,
            'silence_start': 161.0,
            'silence_end': 162.0,
            'snap_point': 161.5,
            'shift_seconds': 1.5,
            'silence_duration': 1.0,
        }
    }
    result = _format_cue_section(
        audio_analysis=None,
        ad_start=100.0,
        ad_end=161.5,
        silence_snap=silence_snap,
    )
    assert 'SILENCE SNAP APPLIED' in result
    assert 'end' in result
    assert '160.0' in result


def test_no_silence_snap_line_when_silence_snap_absent():
    result = _format_cue_section(
        audio_analysis=None,
        ad_start=100.0,
        ad_end=160.0,
        silence_snap=None,
    )
    assert 'SILENCE SNAP' not in result


def test_silence_snap_and_cue_snap_both_render():
    cue_snap = {
        'start': {
            'original': 100.0,
            'label': 'ding',
            'shift_seconds': -0.5,
        }
    }
    silence_snap = {
        'end': {
            'original': 160.0,
            'silence_start': 161.0,
            'silence_end': 162.0,
            'snap_point': 161.5,
            'shift_seconds': 1.5,
            'silence_duration': 1.0,
        }
    }
    result = _format_cue_section(
        audio_analysis=None,
        ad_start=99.5,
        ad_end=161.5,
        cue_snap=cue_snap,
        silence_snap=silence_snap,
    )
    assert 'CUE SNAP APPLIED' in result
    assert 'SILENCE SNAP APPLIED' in result
