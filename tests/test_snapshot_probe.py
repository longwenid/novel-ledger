"""The scale probe must verify old frozen sources, not merely the newest book head."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'validation'))
from storage_snapshot_probe import measure, verify_snapshot_sources
from novel_ledger.contracts import digest


class SnapshotProbeTests(unittest.TestCase):
    def test_probe_reads_every_frozen_version_before_and_after_prune_and_reopen(self):
        report = measure([2, 34], prose_han=1)
        before, after = report['frozen_sources_before_prune'], report['frozen_sources_after_prune']
        self.assertEqual(before['full_logical_hashes_verified'], 68)
        self.assertEqual(before['complete_states_verified'], 34)
        self.assertEqual(before['complete_understandings_verified'], 34)
        self.assertTrue(before['all_expected_version_sequences_verified'])
        self.assertEqual(before['frozen_source_hash_stream_sha256'], after['frozen_source_hash_stream_sha256'])
        self.assertEqual(before['logical_frozen_source_bytes'], report['checkpoints'][-1]['logical_frozen_source_bytes'])
        self.assertEqual(report['checkpoints'][-1]['frozen_source_storage'], report['prune']['frozen_source_storage'])
        self.assertTrue(report['reload']['connection_reopened'])
        self.assertTrue(report['reload_after_prune']['connection_reopened'])
        self.assertTrue(report['source_unchanged_during_probe'])
        self.assertTrue(report['temporary_project_removed'])
        point = report['checkpoints'][-1]
        self.assertEqual(point['physical_document_bytes'], point['document_bytes'] + point['document_block_bytes'])

    def test_verifier_detects_old_snapshot_mutation_even_when_later_snapshot_is_valid(self):
        state = {'developments': {'shen': [{'evidence': {'chapter': 1}}]}}
        memory = {'versions': [{'id': 'hero', 'version': 1, 'producer': 'fixture-1',
                               'evidence': [{'chapter': 1}], 'counterevidence': []}]}
        state_hash, memory_hash = digest(state), digest(memory)
        snapshot = {'chapter': 1, 'task': 'old-task',
                    'records': {'complete_state': state_hash, 'complete_understanding': memory_hash}}
        later_state = copy.deepcopy(state)
        later_state['developments']['shen'].append({'evidence': {'chapter': 2}})
        later_memory = copy.deepcopy(memory)
        later_memory['versions'].append({'id': 'hero', 'version': 2, 'producer': 'fixture-2',
                                         'evidence': [{'chapter': 2}], 'counterevidence': []})
        later_state_hash, later_memory_hash = digest(later_state), digest(later_memory)
        later = {'chapter': 2, 'task': 'later-task',
                 'records': {'complete_state': later_state_hash, 'complete_understanding': later_memory_hash}}
        documents = {state_hash: state, memory_hash: memory,
                     later_state_hash: later_state, later_memory_hash: later_memory}

        class Repository:
            def task(self, key):
                frozen = snapshot if key == 'old-task' else later
                return {'status': 'done', 'input': {'records': frozen['records']}}

            def read_document(self, key):
                value = copy.deepcopy(documents[key])
                if key == state_hash:
                    value['developments']['shen'].clear()
                return value

        repo = Repository()
        self.assertEqual(digest(repo.read_document(later_state_hash)), later_state_hash)
        self.assertEqual(digest(repo.read_document(later_memory_hash)), later_memory_hash)
        with self.assertRaisesRegex(AssertionError, 'digest differs'):
            verify_snapshot_sources(repo, [snapshot, later])


if __name__ == '__main__':
    unittest.main()
