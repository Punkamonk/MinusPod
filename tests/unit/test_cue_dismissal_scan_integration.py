"""_decoded_dismissals: JSON decode + bad-row tolerance."""
from unittest.mock import MagicMock

from api.cue_templates import _decoded_dismissals, CUE_CANDIDATE_SCHEMA_VERSION


def test_decodes_and_skips_bad_rows():
    db = MagicMock()
    db.list_cue_candidate_dismissals.return_value = [
        {'id': 1, 'fingerprint': '[1, 2, 3]'},
        {'id': 2, 'fingerprint': 'not json'},
        {'id': 3, 'fingerprint': '[]'},
        {'id': 4, 'fingerprint': '{"a": 1}'},
    ]
    out = _decoded_dismissals(db, 5)
    assert out == [{'id': 1, 'raw_ints': [1, 2, 3]}]
    db.list_cue_candidate_dismissals.assert_called_once_with(5)


def test_schema_version_bumped_for_dismissals():
    assert CUE_CANDIDATE_SCHEMA_VERSION == 5
