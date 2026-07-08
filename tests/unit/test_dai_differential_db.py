"""Persistence tests for episode-level dai_differential storage (Layer 3)."""
import json

DIFF_A = {'status': 'ok',
          'regions': [{'start_s': 10.3, 'end_s': 16.3,
                       'kind': 'differential', 'corr': 0.0}],
          'refetch_meta': {'ua': 'AntennaPod/3.4.0'}, 'error': None}


class TestDaiDifferentialPersistence:
    def test_round_trip(self, temp_db, mock_episode):
        slug = mock_episode['slug']
        ep_id = mock_episode['episode_id']
        temp_db.save_episode_dai_differential(slug, ep_id, json.dumps(DIFF_A))
        raw = temp_db.get_episode_dai_differential(slug, ep_id)
        assert json.loads(raw) == DIFF_A

    def test_get_returns_none_when_unset(self, temp_db, mock_episode):
        assert temp_db.get_episode_dai_differential(
            mock_episode['slug'], mock_episode['episode_id']) is None

    def test_unknown_episode_no_op(self, temp_db, mock_podcast):
        temp_db.save_episode_dai_differential(
            mock_podcast['slug'], 'nonexistent-id', json.dumps(DIFF_A))
        assert temp_db.get_episode_dai_differential(
            mock_podcast['slug'], 'nonexistent-id') is None

    def test_get_episode_includes_raw_json(self, temp_db, mock_episode):
        slug = mock_episode['slug']
        ep_id = mock_episode['episode_id']
        temp_db.save_episode_dai_differential(slug, ep_id, json.dumps(DIFF_A))
        episode = temp_db.get_episode(slug, ep_id)
        assert json.loads(episode['dai_differential_json']) == DIFF_A

    def test_overwrite_updates(self, temp_db, mock_episode):
        slug = mock_episode['slug']
        ep_id = mock_episode['episode_id']
        temp_db.save_episode_dai_differential(slug, ep_id, json.dumps(DIFF_A))
        updated = dict(DIFF_A, status='no_differential', regions=[])
        temp_db.save_episode_dai_differential(slug, ep_id, json.dumps(updated))
        assert json.loads(
            temp_db.get_episode_dai_differential(slug, ep_id)) == updated
