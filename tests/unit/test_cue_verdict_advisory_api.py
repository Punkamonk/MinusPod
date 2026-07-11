"""API tests for the advisory endpoint's templateHints field."""
import os
import sys
import tempfile

import pytest

_test_data_dir = tempfile.mkdtemp(prefix='cue_advisory_api_test_')
os.environ['SECRET_KEY'] = 'test-secret'
os.environ['DATA_DIR'] = _test_data_dir
os.environ['MINUSPOD_MASTER_PASSPHRASE'] = 'cue-advisory-api-test-passphrase'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import database
import storage as storage_mod

database.Database._instance = None
database.Database.__init__.__defaults__ = (_test_data_dir,)
database.Database.__new__.__defaults__ = (_test_data_dir,)
storage_mod.Storage.__init__.__defaults__ = (_test_data_dir,)

from main_app import app

from database import Database


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def db():
    return Database()


def test_advisory_carries_template_hints(client, db):
    pid = db.create_podcast('hfeed', 'http://x/rss', 'Feed')
    db.record_cue_detections(pid, 'ep1', [
        {'template_id': 1, 'label': 'ding', 'start_s': float(i), 'end_s': float(i) + 0.5,
         'match_score': 0.76 + i * 0.01, 'outcome': 'none'}
        for i in range(3)
    ])
    for r in db.list_cue_detections_for_episode(pid, 'ep1'):
        db.set_cue_detection_verdict(r['id'], 'rejected')
    resp = client.get('/api/v1/feeds/hfeed/cue-detections/advisory')
    assert resp.status_code == 200
    hints = resp.get_json()['templateHints']
    assert hints == [{'templateId': 1, 'label': 'ding',
                      'hint': 'raise_threshold', 'rejected': 3, 'confirmed': 0}]
