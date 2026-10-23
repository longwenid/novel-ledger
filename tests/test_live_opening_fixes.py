"""Fixes measured from the 2026-10-18 live opening run (session 7253a7e0, 项目1014).

That run paid a per-gate plumbing tax and a set of avoidable worker failures: briefs reachable
only by dumping input.json to a temp file (console tools truncate the single long line), a
hand-copied input_hash, board echoes nobody read because the card was already materialized,
option descriptions re-authored while the engine's pitch never reached the author, hand-written
dispatch prompts until one taught a worker to run `claim` (rejected by worker_boundary),
alignment rejections without the expected string (the worker probed the rule with a scratch
directory), re-review scope checks hand-rolled with diff scripts and engine source, and an
opening archaeology round hunting an older project for a result.json sample. Each fix is
pinned here.
"""
import argparse
import json
import os
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

import novel
from novel_ledger import creation, delivery, workflow, world
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import RESULT, Error
from novel_ledger.sqlite_store import SQLiteRepository
from test_opening import shown
from test_opening_inline import gate_result

CHOICES = {'world': {'world_premise': '一座仓库的夜班退件纠纷。', 'mechanism': {'mode': 'none'}},
           'protagonist': {'id': 'shen', 'name': '沈桐', 'identity': '夜班退件工，背着一笔旧账。',
                           'desire': '查清退件来源并洗掉违规记录。', 'limit': '不牵连无关同事。'}}


def minimal_world(premise):
    value = {'selection_hash': 'sel', 'premise': premise, 'story_capacity': '工程夹具：制度与人情可持续供料。'}
    for section in world.SECTIONS:
        value[section] = []
    return value


class ArtifactTests(unittest.TestCase):
    """The engine materializes what every reader opens: brief, bootstrap card, question, snapshot."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_the_task_directory_carries_brief_md_and_dispatch_md(self):
        handoff = self.app.advance(compact=True)
        task = handoff['task']
        brief_path = Path(task['brief_path'])
        dispatch_path = Path(task['dispatch_path'])
        self.assertTrue(brief_path.exists() and dispatch_path.exists())
        # brief.md is the markdown twin of input.json's single-line brief, not a second authority.
        brief = brief_path.read_text(encoding='utf-8')
        frozen = json.loads((brief_path.parent / 'input.json').read_text(encoding='utf-8'))['brief']
        self.assertEqual(brief, frozen)
        self.assertIn('hatch.md', brief)
        # Controller-only opening must not bootstrap a worker or ask for a worker lease.
        card = dispatch_path.read_text(encoding='utf-8')
        full = json.loads(Path(task['task_path']).read_text(encoding='utf-8'))
        self.assertEqual(full['execution']['state'], 'controller')
        self.assertNotIn('ready', full['commands'])
        self.assertNotIn('worker', full['commands']['read'])
        result = subprocess.run(full['commands']['read'], text=True, capture_output=True,
                                encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['task_id'], task['task_id'])

    def test_a_redispatched_task_quarantines_the_previous_attempt_draft(self):
        """A live reviewer found a dropped session's half-written receipt beside the blank form.

        The next reviewer must not read it as their own judgment (or submit it under someone
        else's session): a re-render of the unsubmitted task moves it to result.stale.json and
        the dispatch card says so.
        """
        first = self.app.advance()
        base = Path(first['task']['task_path']).parent
        (base / 'result.json').write_text(json.dumps(
            {'schema': RESULT, 'task_id': first['task']['task_id'], 'input_hash': 'x',
             'session': 'worker-dropped-session', 'data': {'gate': 'genre', 'options': []}}, ensure_ascii=False),
            encoding='utf-8')
        again = self.app.advance(compact=True)
        self.assertFalse((base / 'result.json').exists())
        quarantined = json.loads((base / 'result.stale.json').read_text(encoding='utf-8'))
        self.assertEqual(quarantined['session'], 'worker-dropped-session')
        self.assertEqual(again['task']['redispatch_count'], 2)
        self.assertEqual(again['task']['stale_result_session'], 'worker-dropped-session')
        card = Path(again['task']['dispatch_path']).read_text(encoding='utf-8')
        self.assertIn('遗留草稿已隔离', card)
        self.assertIn('worker-dropped-session', card)
        # The blank form is untouched by the quarantine; a fresh render of a fresh task keeps
        # whatever the active worker has written (no prior view, no quarantine).
        self.assertTrue((base / 'result.template.json').exists())

    def test_the_question_payload_uses_engine_text_verbatim(self):
        state = shown(self.app.repo.load()['creation'])
        question = delivery.render_question(state['board'])
        options = question['questions'][0]['options']
        # Capped at four: common ask components stop there, and a live controller facing the cap
        # silently dropped the fixed actions (and once offered 4 of 12 categories as the gate).
        self.assertLessEqual(len(options), 4)
        for row, option in zip(options, state['board']['options']):
            self.assertIn(option['title'], row['label'])
            self.assertEqual(row['description'], option['pitch'])
        self.assertIn('自定义', options[-1]['label'])
        self.assertIn('Other', options[-1]['description'])
        # The structural gate has no pitch; the ask falls back to the tier premise the engine wrote.
        state = self.app.repo.load()['creation']
        system = creation.SYSTEM_GATES.get(creation.opening_version(state), ())
        for _ in range(len(creation.gates(state))):
            if creation.current(state)['id'] in system:
                break
            state = shown(state)
            state = creation.pick(state, state['board']['options'][0]['id'],
                                  state['board']['hash'], '作者选它。')
        scale_board = creation.view(state)['board']
        self.assertTrue(scale_board.get('system'))
        tier_ask = delivery.render_question(scale_board)['questions'][0]['options'][0]
        self.assertEqual(tier_ask['description'], scale_board['options'][0]['premise'])
        regrouped = dict(scale_board, round=1)
        self.assertIn('新一组', delivery.render_question(regrouped)['questions'][0]['header'])

    def test_read_hash_changes_with_new_choices_and_is_stable_for_rereads(self):
        self.app.advance()
        first = self.app.read(self.repo.pending()['id'])
        self.app.submit(gate_result(self.app, 'lead-main'))
        self.app.opening_choice(first and self.repo.load()['creation']['board']['options'][0]['id'],
                                self.repo.load()['creation']['board']['hash'], '作者选它。')
        self.app.advance()
        second = self.app.read(self.repo.pending()['id'])
        self.assertTrue(first['records_hash'] and second['records_hash'])
        self.assertNotEqual(first['records_hash'], second['records_hash'])
        reread = self.app.read(self.repo.pending()['id'])
        self.assertEqual(second['records_hash'], reread['records_hash'])


class AlignmentMessageTests(unittest.TestCase):
    """Alignment rejections carry the expected string; the worker stops probing with scratch dirs."""

    def test_rejections_name_what_the_engine_expected(self):
        with self.subTest(rejection='world_premise'):
            data = minimal_world('一座完全不同的前提。')
            with self.assertRaises(Error) as caught:
                world.validate(data, CHOICES, 'sel')
            self.assertEqual(caught.exception.code, 'world_alignment')
            details = caught.exception.details
            self.assertEqual(details['expect'], CHOICES['world']['world_premise'])
            self.assertEqual(details['got'], '一座完全不同的前提。')
            self.assertIn('逐字', details['rule'])
            self.assertEqual(details['source'], 'opening_choices.world.world_premise')
        with self.subTest(rejection='world_reference'):
            data = minimal_world(CHOICES['world']['world_premise'])
            data['rules'] = [{'id': 'r1', 'principle': '夜班退件必须登记负责人。', 'scope': '本仓库。',
                              'limits': '不覆盖白班。', 'consequences': '漏登由当班负责。', 'links': ['rules:missing']}]
            with self.assertRaises(Error) as caught:
                world.validate(data, CHOICES, 'sel', sections=('rules',))
            self.assertEqual(caught.exception.code, 'world_reference')
            self.assertEqual(caught.exception.details['missing'], ['rules:missing'])
            self.assertEqual(caught.exception.details['record'], 'rules:r1')
        with self.subTest(rejection='protagonist'):
            data = minimal_world(CHOICES['world']['world_premise'])
            data['rules'] = [{'id': 'r1', 'principle': '夜班退件必须登记负责人。', 'scope': '本仓库。',
                              'limits': '不覆盖白班。', 'consequences': '漏登由当班负责。', 'links': []}]
            data['characters'] = [{'id': 'other', 'name': '白班主任', 'role': '对手', 'desire': '压住退件。',
                                   'limit': '不当面撒谎。', 'knowledge_boundary': '不知道旧账。', 'links': []}]
            with self.assertRaises(Error) as caught:
                world.validate(data, CHOICES, 'sel', sections=('rules', 'characters', 'mechanisms'))
            self.assertEqual(caught.exception.code, 'world_alignment')
            self.assertEqual(caught.exception.details['expect'],
                             {key: CHOICES['protagonist'][key] for key in ('id', 'name', 'desire', 'limit')})
        with self.subTest(rejection='submit_hash'):
            temp = tempfile.TemporaryDirectory()
            self.addCleanup(temp.cleanup)
            project = Path(temp.name) / 'book'
            repo = SQLiteRepository.initialize(project, workflow.preparing_book(guided=True))
            self.addCleanup(repo.close)
            app = Application(repo)
            app.advance()
            result = gate_result(app, 'lead-main')
            result['input_hash'] = ''
            with self.assertRaises(Error) as caught:
                app.submit(result)
            self.assertEqual(caught.exception.code, 'input_version')
            self.assertEqual(caught.exception.details['got'], '')
            self.assertTrue(caught.exception.details['expected'])
            self.assertIn('result.template.json', caught.exception.details['recover'])


class ClaimRoleTests(unittest.TestCase):
    def test_a_worker_running_claim_is_told_the_controller_exit(self):
        os.environ['NOVEL_TASK_ID'] = 'task-claim-lesson'
        self.addCleanup(os.environ.pop, 'NOVEL_TASK_ID', None)
        with self.assertRaises(Error) as caught:
            novel.worker_guard(None, argparse.Namespace(command='claim'))
        self.assertEqual(caught.exception.code, 'worker_boundary')
        self.assertIn('主干', caught.exception.message)
        self.assertEqual(caught.exception.details['recovery']['actor'], 'controller')
        self.assertFalse(caught.exception.details['recovery']['retry_allowed'])


class RepairScopeTests(unittest.TestCase):
    """A local repair may only change the records its findings name; the summary says what moved.

    v2 keeps the guard but moves it to the one repair that still re-drafts records in bulk: the
    volume outline. A chapter outline repair is re-derived from the state that actually moved, so
    the guard's job is narrower — an unnamed record must come back byte-identical.
    """

    def test_a_local_repair_refuses_unnamed_records_and_the_summary_counts_the_moves(self):
        with self.subTest(guard='a record the findings never named'):
            previous = {'chapters': [{'chapter': 1, 'synopsis': '旧第一章。'},
                                     {'chapter': 2, 'synopsis': '旧第二章。'}]}
            candidate = {'chapters': [{'chapter': 1, 'synopsis': '被悄悄改掉的第一章。'},
                                      {'chapter': 2, 'synopsis': '新第二章。'}]}
            findings = [{'criterion': 'chapter_quality', 'reason': '第 2 章的推进需要改写。',
                         'evidence': [], 'target_chapter': 2, 'repair_scope': 'local'}]
            with self.assertRaises(Error) as caught:
                workflow.require_narrow_repair(previous, candidate, findings)
            self.assertEqual(caught.exception.code, 'repair_scope')
            self.assertEqual(caught.exception.details['changed_but_not_named'], ['chapter:1'])
            # The guarded case is exactly the named one: a chapter-scope finding may move more.
            workflow.require_narrow_repair(previous, candidate, [{**findings[0], 'repair_scope': 'chapter'}])
        with self.subTest(guard='the summary says what moved'):
            previous = {'rules': [{'id': 'r1', 'principle': '旧规则。'}, {'id': 'r2', 'principle': '稳定规则。'}]}
            candidate = {'rules': [{'id': 'r1', 'principle': '新规则。'}, {'id': 'r2', 'principle': '稳定规则。'}],
                         'everyday': [{'id': 'e1', 'practice': '新日常。'}]}
            findings = [{'criterion': 'rule_quality', 'reason': 'r1 的规则不成句。', 'evidence': [],
                         'target_chapter': 0, 'repair_scope': 'local'}]
            summary = workflow.repair_summary(previous, candidate, findings)
            self.assertEqual(summary['changed'], ['rules:r1'])
            self.assertEqual(summary['unchanged'], ['rules:r2'])
            self.assertEqual(summary['added'], ['everyday:e1'])
            self.assertEqual(summary['removed'], [])
            self.assertEqual(summary['changed_but_not_named'], [])


class ExampleAssetTests(unittest.TestCase):
    def test_the_opening_options_example_stays_a_valid_receipt_shape(self):
        raw = json.loads((ROOT / 'assets' / 'opening-options.example.json').read_text(encoding='utf-8'))
        self.assertEqual(raw['schema'], RESULT)
        self.assertTrue(raw['task_id'] and raw['input_hash'] and raw['session'])
        options = raw['data']['options']
        self.assertEqual(raw['data']['gate'], 'genre')
        self.assertTrue(2 <= len(options) <= 3)
        seen = set()
        for option in options:
            for field in ('id', 'title', 'pitch', 'scene', 'premise', 'driver', 'tradeoff', 'fit_reason'):
                self.assertTrue(option[field])
            self.assertLessEqual(len(option['pitch'].strip()), 40)
            self.assertTrue(2 <= len(option['scene']) <= 3)
            for scene in option['scene']:
                self.assertGreaterEqual(len(scene), 12)
            for field in ('genre', 'reader_promise', 'tone'):
                self.assertTrue(option['value'][field])
            for field in ('id', 'title', 'premise', 'driver'):
                seen.add(option[field])
        self.assertEqual(len(seen), 4 * len(options), '同组方案必须实质不同')


if __name__ == '__main__':
    unittest.main()
