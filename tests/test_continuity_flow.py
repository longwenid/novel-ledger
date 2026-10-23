"""Candidate isolation, blind-read ordering, versioned evidence and story-time constraints."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from novel_ledger.bootstrap import open_local_runtime
from novel_ledger.contracts import Error, digest, dump
from novel_ledger.continuity_service import SCHEMA
from novel_ledger.continuity import timeline_findings
from support import contract, drive, response


class ContinuityFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = open_local_runtime(Path(self.temp.name) / 'book', initialize=True, contract=contract(3))
        self.addCleanup(self.runtime.close)
        self.app, self.repo = self.runtime.app, self.runtime.repo
        self.app.configure_assurance('advisory', 'required', '本轮启用独立连读。')
        self.task = drive(self.app, until='write')['task']
        self.receipt = response(self.app, session='writer-context')

    def request(self, receipt=None):
        result = self.app.submit(receipt or self.receipt)
        self.assertEqual(result['outcome'], 'continuity_review_required')
        return result['request_id']

    def reader(self, ident, name='independent-reader'):
        prepared = self.app.prepare_observer(ident, name)
        return name, prepared['token']

    def freeze(self, ident, actor, observations=None):
        view = self.app.read_review(ident, *actor)
        payload = {'schema': SCHEMA, 'request_id': ident, 'candidate_hash': view['candidate_hash'],
                   'read_sources': list(view['sources']), 'observations': observations or []}
        return self.app.observe_review(payload, *actor)

    def report(self, ident, actor, frozen, findings=None):
        return self.app.report_review({'schema': SCHEMA, 'request_id': ident, 'candidate_hash': ident,
                                      'observations_hash': frozen['observations_hash'],
                                      'findings': findings or [], 'assessment': '已连读原文并比较动作、时间、人物与章纲。'}, *actor)

    def citation(self, prose, quote):
        return {'source': 'candidate', 'prose_hash': digest(prose), 'quote': quote, 'start': prose.index(quote)}

    def test_preview_is_read_only_and_formal_candidate_does_not_spend_or_publish(self):
        before = tuple(self.repo.db.iterdump())
        preview = self.app.submit(self.receipt, preview=True)
        self.assertEqual(preview['outcome'], 'continuity_review_required')
        self.assertEqual(tuple(self.repo.db.iterdump()), before)
        book = self.repo.load()
        ident = self.request()
        self.assertEqual(self.repo.load(), book)
        self.assertEqual(self.repo.pending()['id'], self.task['task_id'])
        self.assertEqual(self.app.advance()['action'], 'review_required')
        self.assertEqual(self.request(), ident)
        self.assertEqual(self.repo.headers('main'), [])

    def test_same_writer_or_reused_context_cannot_be_the_reader(self):
        ident = self.request()
        with self.assertRaises(Error):
            self.app.prepare_observer(ident, 'writer-context')
        self.repo.bind_session('previous-design-context', 'other-task')
        with self.assertRaises(Error):
            self.app.prepare_observer(ident, 'previous-design-context')

    def test_blind_read_cannot_see_self_check_until_observations_are_frozen(self):
        ident = self.request()
        actor = self.reader(ident)
        blind = self.app.read_review(ident, *actor)
        self.assertNotIn('self_check', json.dumps(blind))
        with self.assertRaises(Error):
            self.app.read_review(ident, *actor, compare=True)
        frozen = self.freeze(ident, actor)
        compared = self.app.read_review(ident, *actor, compare=True)
        self.assertEqual(compared['comparison']['self_check'], self.receipt['data']['self_check'])
        changed = {'schema': SCHEMA, 'request_id': ident, 'candidate_hash': ident, 'read_sources': ['candidate'],
                   'observations': [], 'limitations': ['看了自评后重写首读判断']}
        with self.assertRaises(Error):
            self.app.observe_review(changed, *actor)
        self.report(ident, actor, frozen)
        self.assertEqual(self.app.advance()['action'], 'review_complete')
        result = self.app.submit(self.receipt)
        self.assertEqual(result['outcome'], 'chapter_committed')
        audit = self.app.audit()['continuity_review']
        self.assertEqual(audit['reviewed_chapters'], [1])
        self.assertEqual(audit['host_verified_chapters'], [])

    def test_explicit_death_then_alive_is_not_waived_by_an_empty_report(self):
        self.receipt['data']['prose'] += '老周死了。老周又说话。'
        prose = self.receipt['data']['prose']
        ident = self.request()
        actor = self.reader(ident)
        observations = [{'entity': 'person_zhou', 'predicate': 'life_state', 'value': value, 'certainty': 'explicit',
                         'evidence': self.citation(prose, quote)}
                        for value, quote in [('dead', '老周死了。'), ('alive', '老周又说话。')]]
        frozen = self.freeze(ident, actor, observations)
        self.report(ident, actor, frozen)
        result = self.app.submit(self.receipt)
        self.assertEqual(result['outcome'], 'repair_required')
        self.assertTrue(any(item['criterion'] == 'continuity' for item in result['findings']))
        self.assertEqual(self.repo.headers('main'), [])
        self.assertEqual(self.repo.load()['rework']['1']['repairs'], 0)

    def test_apparent_death_and_cited_revival_are_not_an_automatic_contradiction(self):
        from novel_ledger.continuity import observed_contradictions
        dead = {'entity': 'zhou', 'predicate': 'life_state', 'value': 'dead', 'certainty': 'apparent',
                'evidence': {'source': '1', 'start': 0}}
        alive = {'entity': 'zhou', 'predicate': 'life_state', 'value': 'alive', 'certainty': 'explicit',
                 'evidence': {'source': 'candidate', 'start': 0}}
        self.assertFalse(observed_contradictions([dead, alive]))
        dead['certainty'] = 'explicit'
        alive['evidence']['start'] = 20
        alive['transition'] = {'kind': 'revival', 'evidence': {'source': 'candidate', 'start': 10}}
        self.assertFalse(observed_contradictions([dead, alive]))
        alive['transition']['evidence']['source'] = '0'
        self.assertTrue(observed_contradictions([dead, alive]))
        alive.pop('transition')
        for time_frame in ('flashback', 'parallel', 'uncertain'):
            alive['time_frame'] = time_frame
            self.assertFalse(observed_contradictions([dead, alive]))

    def test_wrong_quote_and_wrong_version_are_rejected(self):
        ident = self.request()
        actor = self.reader(ident)
        self.app.read_review(ident, *actor)
        observation = {'entity': 'lu', 'predicate': 'life_state', 'value': 'alive', 'certainty': 'explicit',
                       'evidence': {'source': 'candidate', 'prose_hash': digest(self.receipt['data']['prose']),
                                    'start': 0, 'quote': '原文里没有这句话'}}
        with self.assertRaises(Error):
            self.freeze(ident, actor, [observation])
        frozen = self.freeze(ident, actor)
        payload = {'schema': SCHEMA, 'request_id': ident, 'candidate_hash': 'different',
                   'observations_hash': frozen['observations_hash'], 'findings': [], 'assessment': '错误版本'}
        with self.assertRaises(Error):
            self.app.report_review(payload, *actor)

    def test_changed_candidate_cannot_reuse_a_clean_report(self):
        ident = self.request()
        actor = self.reader(ident)
        frozen = self.freeze(ident, actor)
        self.report(ident, actor, frozen)
        changed = copy.deepcopy(self.receipt)
        changed['data']['prose'] += '门关着。'
        new_ident = self.request(changed)
        self.assertNotEqual(new_ident, ident)
        with self.assertRaises(Error):
            self.app.read_review(ident, *actor)
        self.assertEqual(self.repo.headers('main'), [])

    def test_worker_recovery_rotates_credentials_without_rereading_unchanged_candidate(self):
        prepared = self.app.prepare_worker(self.task['task_id'], 'writer-context', seconds=1)
        self.receipt['execution_claim'] = prepared['worker_env']['NOVEL_EXECUTION_CLAIM']
        ident = self.request()
        actor = self.reader(ident)
        self.report(ident, actor, self.freeze(ident, actor))
        now = self.app.clock()
        self.app.clock = lambda: now + 2
        replacement = self.app.prepare_worker(self.task['task_id'], 'replacement-writer')
        recovered = copy.deepcopy(self.receipt)
        recovered.update(session='replacement-writer', execution_claim=replacement['worker_env']['NOVEL_EXECUTION_CLAIM'])
        result = self.app.submit(recovered)
        self.assertEqual(result['outcome'], 'chapter_committed')
        self.assertEqual(result['quality_report']['request_id'], ident)

    def test_observer_cannot_continue_after_frozen_engine_or_rules_change(self):
        ident = self.request()
        actor = self.reader(ident)
        before = tuple(self.repo.db.iterdump())
        self.app.build_info = {**self.app.build_info, 'rules_hash': 'changed'}
        with self.assertRaises(Error) as caught:
            self.app.read_review(ident, *actor)
        self.assertEqual(caught.exception.code, 'engine_changed')
        self.assertEqual(tuple(self.repo.db.iterdump()), before)

    def test_metadata_and_whitespace_cannot_reroll_a_reader_for_the_same_prose(self):
        ident = self.request()
        actor = self.reader(ident)
        self.report(ident, actor, self.freeze(ident, actor))
        for whitespace in (False, True):
            changed = copy.deepcopy(self.receipt)
            changed['data']['summary'] += '换一段说明。'
            if whitespace:
                changed['data']['prose'] += '\n  '
            before = tuple(self.repo.db.iterdump())
            with self.assertRaises(Error) as caught:
                self.app.submit(changed)
            self.assertEqual(caught.exception.code, 'no_progress')
            self.assertEqual(tuple(self.repo.db.iterdump()), before)

    def test_active_reader_or_blocking_report_must_be_settled_before_replacement(self):
        ident = self.request()
        actor = self.reader(ident)
        changed = copy.deepcopy(self.receipt)
        changed['data']['prose'] += '门关着。'
        with self.assertRaises(Error) as caught:
            self.app.submit(changed)
        self.assertEqual(caught.exception.code, 'continuity_pending')
        frozen = self.freeze(ident, actor)
        prose = self.receipt['data']['prose']
        finding = {'kind': 'contradiction', 'reason': '工程夹具：成对证据与结论冲突。',
                   'evidence': [self.citation(prose, prose[:8]), self.citation(prose, prose[-8:])]}
        self.report(ident, actor, frozen, [finding])
        with self.assertRaises(Error) as caught:
            self.app.submit(changed)
        self.assertEqual(caught.exception.code, 'continuity_settlement')
        settled = self.app.submit(self.receipt)
        self.assertEqual(settled['outcome'], 'repair_required')
        self.assertTrue(self.repo.load()['rework']['1']['initial_used'])
        self.assertEqual(self.repo.task(self.task['task_id'])['status'], 'done')

    def test_review_retries_keep_resolved_phase_and_do_not_rewrite_the_journal(self):
        ident = self.request()
        actor = self.reader(ident)
        view = self.app.read_review(ident, *actor)
        observation = view['observation_template']
        frozen = self.app.observe_review(observation, *actor)
        prose = self.receipt['data']['prose']
        finding = {'kind': 'uncertain', 'reason': '指代未决。', 'evidence': [self.citation(prose, prose[:8])]}
        self.report(ident, actor, frozen, [finding])
        source = '保留未决。'
        self.app.resolve_review(ident, 'accept_uncertainty', source)
        before = tuple(self.repo.db.iterdump())
        for result in (self.app.observe_review(observation, *actor),
                       self.report(ident, actor, frozen, [finding]),
                       self.app.resolve_review(ident, 'accept_uncertainty', source)):
            self.assertTrue(result['idempotent'])
            self.assertEqual(result['phase'], 'done')
        self.assertEqual(tuple(self.repo.db.iterdump()), before)
        with self.assertRaises(Error):
            self.app.resolve_review(ident, 'repair', '改成返修。')
        self.assertEqual(self.app.submit(self.receipt)['outcome'], 'chapter_committed')

    def test_malformed_observation_lists_are_rejected_without_mutating_the_request(self):
        ident = self.request()
        actor = self.reader(ident)
        template = self.app.read_review(ident, *actor)['observation_template']
        before = tuple(self.repo.db.iterdump())
        for invalid in ({'read_sources': [{}]}, {'read_sources': 'candidate'},
                        {'read_sources': ['candidate', 'not-delivered']}, {'limitations': {'reason': 'unknown'}}):
            with self.assertRaises(Error):
                self.app.observe_review({**template, **invalid}, *actor)
        self.assertEqual(tuple(self.repo.db.iterdump()), before)

    def test_independent_read_cost_is_visible_separately_from_writer_materials(self):
        ident = self.request()
        actor = self.reader(ident)
        before = self.app.usage()
        blind = self.app.read_review(ident, *actor)
        self.app.observe_review(blind['observation_template'], *actor)
        comparison = self.app.read_review(ident, *actor, compare=True)
        usage = self.app.usage()
        self.assertEqual(usage['continuity_read_calls'] - before['continuity_read_calls'], 2)
        self.assertEqual(usage['continuity_read_chars'] - before['continuity_read_chars'],
                         len(dump(blind)) + len(dump(comparison)))
        self.assertEqual(usage['supplemental_read_chars'], before['supplemental_read_chars'])
        self.assertIsNone(usage['billed_tokens'])

    def test_uncertainty_waits_for_scoped_resolution_and_keeps_the_decision(self):
        ident = self.request()
        actor = self.reader(ident)
        frozen = self.freeze(ident, actor)
        quote = self.receipt['data']['prose'][:8]
        finding = {'kind': 'uncertain', 'reason': '此处指代有两种解释，需要作者选择。',
                   'evidence': [self.citation(self.receipt['data']['prose'], quote)]}
        self.report(ident, actor, frozen, [finding])
        self.assertEqual(self.app.submit(self.receipt)['outcome'], 'continuity_review_required')
        self.assertEqual(self.repo.headers('main'), [])
        self.app.resolve_review(ident, 'accept_uncertainty', '保留这一歧义，不宣称已经解释清楚。')
        self.assertEqual(self.app.submit(self.receipt)['committed_chapter'], 1)
        self.assertEqual(self.app.audit()['continuity_review']['accepted_uncertainty_chapters'], [1])

    def test_out_of_band_budget_reset_is_detected_after_official_checkpoint(self):
        self.receipt['data']['prose'] += '他等了许久，窗外的雨沿着破损的玻璃往下流。值班室另一头有人收起了钥匙，走廊的灯熄了一盏，门后的脚步声渐渐远去。'
        self.app.submit(self.receipt)
        book = self.repo.load()
        book['draft']['findings'] = []
        self.repo.save(book)
        with self.assertRaises(Error) as caught:
            self.app.status()
        self.assertEqual(caught.exception.code, 'governance_integrity')

    def test_real_cli_writer_observer_writer_handoff_commits_once(self):
        base_env = {key: value for key, value in os.environ.items() if not key.startswith('NOVEL_')}

        def run(argv, env=None):
            process = subprocess.run(argv, env={**base_env, **(env or {})}, text=True, capture_output=True, timeout=20)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            return json.loads(process.stdout)

        prepared = self.app.prepare_worker(self.task['task_id'], 'writer-context')
        view = json.loads(Path(self.task['task_path']).read_text())
        receipt = copy.deepcopy(self.receipt)
        receipt['session'] = ''
        Path(view['result_path']).write_text(json.dumps(receipt), encoding='utf-8')
        candidate = run(view['commands']['submit'], prepared['worker_env'])
        self.assertEqual(candidate['worker_boundary'], 'await_review')
        command = [sys.executable, str(ROOT / 'scripts/novel.py'), '--project', str(self.repo.project)]
        reader = run(command + ['prepare-observer', '--request', candidate['request_id'], '--session', 'real-reader-context'])
        read = run(reader['commands']['review-read'], reader['observer_env'])
        observation_file = Path(self.temp.name) / 'observations.json'
        observation_file.write_text(json.dumps(read['observation_template']), encoding='utf-8')
        run(reader['commands']['review-observe'] + ['--file', str(observation_file)], reader['observer_env'])
        compare = run(reader['commands']['review-read'] + ['--compare'], reader['observer_env'])
        report_file = Path(self.temp.name) / 'report.json'
        report = compare['report_template']
        report['assessment'] = '工程全文夹具已阅读，未发现连续性矛盾。'
        report_file.write_text(json.dumps(report), encoding='utf-8')
        run(reader['commands']['review-report'] + ['--file', str(report_file)], reader['observer_env'])
        committed = run(view['commands']['submit'], prepared['worker_env'])
        self.assertEqual(committed['committed_chapter'], 1)
        replay = run(view['commands']['submit'], prepared['worker_env'])
        self.assertTrue(replay['idempotent'])
        self.assertEqual(len(self.repo.headers('main')), 1)


class TimelineTests(unittest.TestCase):
    def row(self, start, end, days=0, relation='after', **more):
        return {'chapter': 70, 'clock': {'advance_days': days},
                'timeline': {'scene_id': 'pump-battle', 'relation': relation, 'start': start, 'end': end, **more}}

    def test_minutes_of_one_battle_cannot_be_settled_as_a_whole_day(self):
        self.assertTrue(timeline_findings(self.row([60, 60], [65, 65], days=1)))
        self.assertFalse(timeline_findings(self.row([60, 60], [65, 65])))
        self.assertFalse(timeline_findings(self.row([1439, 1439], [1441, 1441], days=1)))

    def test_two_hour_train_cannot_remain_pending_after_a_day(self):
        deadline = {'id': 'train-2305', 'due': [1385, 1385], 'status': 'open'}
        self.assertTrue(timeline_findings(self.row([1265, 1265], [2705, 2705], days=1, deadlines=[deadline])))
        deadline.update(status='extended', resolution_event='调度取消今晚班次，次日重发。')
        self.assertTrue(timeline_findings(self.row([1265, 1265], [2705, 2705], days=1, deadlines=[deadline])))
        deadline['due'] = [2825, 2825]
        self.assertFalse(timeline_findings(self.row([1265, 1265], [2705, 2705], days=1, deadlines=[deadline])))

    def test_overnight_gap_uses_previous_scene_and_unresolved_deadlines_cannot_disappear(self):
        deadline = {'id': 'train', 'due': [1385, 1385], 'status': 'open'}
        prior = self.row([1265, 1265], [1270, 1270], deadlines=[deadline])
        following = self.row([2700, 2700], [2705, 2705], days=1)
        self.assertTrue(timeline_findings(following, prior))
        self.assertTrue(timeline_findings({'chapter': 71}, prior))
        following['timeline']['deadlines'] = [{**deadline, 'status': 'failed', 'resolution_event': '他们错过了列车。'}]
        self.assertFalse(timeline_findings(following, prior))
        following['timeline']['deadlines'] = [{**deadline, 'due': [2825, 2825]}]
        self.assertTrue(timeline_findings(following, prior))
        following['timeline']['deadlines'][0].update(status='extended', resolution_event='调度延期到翌日。')
        self.assertFalse(timeline_findings(following, prior))

    def test_parallel_and_flashback_do_not_rewind_the_current_story_clock(self):
        prior = self.row([200, 200], [210, 210])
        self.assertTrue(timeline_findings(self.row([100, 100], [110, 110], relation='continues'), prior))
        self.assertFalse(timeline_findings(self.row([100, 100], [110, 110], relation='parallel'), prior))
        self.assertFalse(timeline_findings(self.row([100, 100], [110, 110], relation='flashback'), prior))


if __name__ == '__main__':
    unittest.main()
