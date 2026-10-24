"""Cost observations must include source material and readers without inventing savings."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger.contracts import Error, dump
from novel_ledger.sqlite_store import SQLiteRepository


def tool(name):
    spec = importlib.util.spec_from_file_location('cost_test_' + name, ROOT / 'validation' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cost_report = tool('cost_report')
read_waste = tool('read_waste_probe')
measure = tool('measure')


class ProjectCostTests(unittest.TestCase):
    def test_report_expands_shared_source_records_and_counts_independent_reads_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'book'
            repo = SQLiteRepository.initialize(project, {})
            source = {'versions': [{'version': n, 'text': '完整来源' * 120} for n in range(300)]}
            ident = repo.document(source)
            work = {'stage': 'write', 'chapter': 1, 'required': ['world_core', 'world_model'],
                    'records': {'world_core': ident, 'world_model': ident}}
            task = repo.add_task(work)
            repo.finish_task(task['id'], {'data': {'prose': '已接受正文。'}})
            repo.record('read', {'task': task['id'], 'records': ['world_core'], 'chars': 321})
            repo.record('continuity_read', {'task': task['id'], 'records': ['candidate'], 'chars': 12000})
            repo.close()
            before = (project / 'novel.sqlite3').read_bytes()
            report = cost_report.summary(project)
            self.assertEqual(report['tasks']['input_chars'], len(dump(work)))
            self.assertEqual(report['tasks']['required_material_chars'], 2 * len(dump(source)))
            self.assertEqual(report['tasks']['by_stage']['write']['mean_required_material_chars'],
                             2 * len(dump(source)))
            self.assertEqual(report['supplemental_reads'], {'events': 1, 'chars': 321})
            self.assertEqual(report['continuity_reads'], {'events': 1, 'chars': 12000})
            self.assertEqual((project / 'novel.sqlite3').read_bytes(), before)

    def test_same_envelope_size_does_not_hide_larger_required_material(self):
        with tempfile.TemporaryDirectory() as directory:
            reports = []
            for size in (10, 100000):
                project = Path(directory) / str(size)
                repo = SQLiteRepository.initialize(project, {})
                ident = repo.document('文' * size)
                repo.add_task({'stage': 'write', 'chapter': 1, 'required': ['source'],
                               'records': {'source': ident}})
                repo.close()
                reports.append(cost_report.summary(project))
            self.assertEqual(reports[0]['tasks']['input_chars'], reports[1]['tasks']['input_chars'])
            self.assertEqual([r['tasks']['required_material_chars'] for r in reports], [12, 100002])

    def test_reports_refuse_old_schema_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'book'
            repo = SQLiteRepository.initialize(project, {})
            repo.put('schema', 'novel-ledger/4')
            repo.close()
            before = (project / 'novel.sqlite3').read_bytes()
            for report in (cost_report.summary, read_waste.summary):
                with self.subTest(tool=report.__module__), self.assertRaises(Error):
                    report(project)
                self.assertEqual((project / 'novel.sqlite3').read_bytes(), before)


class DeliveryObservationTests(unittest.TestCase):
    def test_execution_and_hash_changes_are_new_deliveries_and_mixed_payloads_are_not_prorated(self):
        def row(execution, hashes, chars=100, task='task'):
            return {'task': task, 'records': list(hashes), 'chars': chars,
                    'execution_id': execution, 'record_hashes': hashes}

        report = read_waste.analyze([
            row('first', {'state': 'a'}),
            row('fresh-context', {'state': 'a'}),
            row('fresh-context', {'state': 'b'}),
            row('fresh-context', {'state': 'b'}, task='next-chapter'),
            row('fresh-context', {'state': 'b', 'long-source': 'c'}, chars=10000),
        ])
        self.assertEqual(report['first_or_changed']['events'], 3)
        self.assertEqual(report['same_execution_same_hash'], {'events': 1, 'response_chars': 100})
        self.assertEqual(report['mixed_known_and_new'], {'events': 1, 'response_chars': 10000})
        self.assertNotIn('saved_chars', report)

    def test_legacy_and_incomplete_metadata_remain_unknown_and_report_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'book'
            repo = SQLiteRepository.initialize(project, {})
            row = {'task': 'task', 'records': ['state'], 'chars': 100}
            repo.record('read', row)
            repo.record('read', row)
            repo.record('read', {**row, 'execution_id': 'new-context', 'record_hashes': {}})
            repo.close()
            before = (project / 'novel.sqlite3').read_bytes()
            report = read_waste.summary(project)
            self.assertEqual(report['unclassified'], {'events': 3, 'response_chars': 300})
            self.assertEqual(report['legacy_same_name_candidates'], {'events': 2, 'response_chars': 200})
            self.assertEqual(report['same_execution_same_hash']['events'], 0)
            run = subprocess.run([sys.executable, str(ROOT / 'validation/read_waste_probe.py'), str(project)],
                                 capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertNotIn('合计可省', run.stdout)
            self.assertEqual((project / 'novel.sqlite3').read_bytes(), before)


class DispatchAccountingTests(unittest.TestCase):
    def test_hundred_chapters_include_independent_readers_only_when_required(self):
        rows = {}
        for mode in ('required', 'off'):
            report = measure.dispatch_ledger(mode)
            rows[mode] = next(row for row in report['by_tier']
                              if row['tier'] == 't2' and row['volume_scope'] == 'all')
        self.assertEqual(rows['required']['continuity_observers'], 100)
        self.assertEqual(rows['required']['fast_total_workers'], 119)
        self.assertEqual(rows['off']['continuity_observers'], 0)
        self.assertEqual(rows['off']['fast_total_workers'], 19)
        self.assertEqual(rows['required']['story_tasks'], 106)
        self.assertEqual(rows['off']['story_tasks'], 106)
        self.assertEqual(rows['required']['standard_total_workers'], 206)
        self.assertEqual(rows['off']['standard_total_workers'], 106)

    def test_cli_exposes_policy_without_changing_story_task_count(self):
        for options, expected in (([], 'required'), (['--continuity', 'off'], 'off')):
            run = subprocess.run([sys.executable, str(ROOT / 'validation/measure.py'),
                                  '--only', 'dispatch', *options], capture_output=True,
                                 text=True, encoding='utf-8')
            self.assertEqual(run.returncode, 0, run.stderr)
            report = json.loads(run.stdout)['dispatch']['value']
            self.assertEqual(report['continuity'], expected)
            self.assertTrue(all(row['continuity'] == expected for row in report['by_tier']))


if __name__ == '__main__':
    unittest.main()
