"""The opening choice chain runs inline: the controller executes its own gates.

Measured on a live run: each gate dispatched to a cold subagent cost 0.4M~1M input tokens and
2~5 minutes for a 3.6K-character envelope, and the author waited on every roundtrip. The gates
carry no prose, no blind first read and no review independence, so the cold-session rule bought
nothing — the same conclusion the v3 guided-hatching line reached ("选择链全流程内联执行").
These tests pin the carve-out: controller reads for opening gates only, one session across all
gates, and every other stage keeping the new-worker rule.
"""
import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

import novel
from novel_ledger import creation, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import CONTROLLER_STAGES, Error
from novel_ledger.result_templates import template
from novel_ledger.sqlite_store import SQLiteRepository
from test_opening import rows_for, shown

GATE_RECEIPT = {'genre': {'genre': '都市异能', 'reader_promise': '看他从仓库夜班把签字责任查到底。', 'tone': '冷硬利落。'},
                'voice': {'pov': '第三人称限知。', 'voice': '短句推进。', 'style_traits': ['少解释多动作。', '章末留钩。']}}


def gate_result(app, session):
    task = app.repo.pending()
    work = task['input']
    data = template(work['stage'], work['chapter'], {}, work['obligations'], version=1,
                    payload=work['payload'], tracking=False)
    data.update(gate=work['payload']['gate']['id'], options=rows_for(work['payload']['gate']['id']))
    return {'schema': 'novel-ledger.result/1', 'task_id': task['id'], 'input_hash': task['input_hash'],
            'session': session, 'data': data}


class InlineOpeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project, workflow.preparing_book(guided=True))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def sessions(self):
        return self.repo.db.execute('SELECT count(*) c FROM sessions').fetchone()['c']

    def test_one_session_runs_the_whole_choice_chain(self):
        controller = 'controller-main-session'
        chosen = []
        for _ in range(2):
            handoff = self.app.advance()
            self.assertEqual(handoff['action'], 'task_ready')
            task_id = handoff['task']['task_id']
            result = gate_result(self.app, controller)
            outcome = self.app.submit(result)
            self.assertTrue(outcome['accepted'])
            chosen.append(task_id)
            self.app.opening_choice(result['data']['options'][0]['id'],
                                    self.app.repo.load()['creation']['board']['hash'], '作者选它。')
        self.assertEqual(len(set(chosen)), 2)
        # No independence requirement to enforce, so nothing was bound: a later gate may follow.
        self.assertEqual(self.sessions(), 0)
        self.assertEqual(self.app.status()['opening']['selected_gates'], 2)

    def test_controller_reads_are_allowed_only_for_opening_gates(self):
        handoff = self.app.advance()
        args = argparse.Namespace(command='read', project=str(self.project),
                                  task=handoff['task']['task_id'])
        novel.role_guard(args)                      # no NOVEL_TASK_ID: the gate identity vouches
        blocked = argparse.Namespace(command='patch', project=str(self.project),
                                     task=handoff['task']['task_id'])
        with self.assertRaises(Error):
            novel.role_guard(blocked)
        # A prose-bearing stage is not let through even with a task named.
        work = self.project / 'work' / '00000000-prose-task'
        work.mkdir(parents=True)
        (work / 'identity.json').write_text(json.dumps({'schema': 'novel-ledger.identity/1',
                                                       'stage': 'write', 'task_id': '00000000-prose-task'}),
                                            encoding='utf-8')
        with self.assertRaises(Error):
            novel.role_guard(argparse.Namespace(command='read', project=str(self.project),
                                                task='00000000-prose-task'))
        self.assertEqual(CONTROLLER_STAGES, frozenset({'opening_options'}))

    def test_cliche_protagonist_names_come_back_as_board_warnings_not_blocks(self):
        state = self.app.repo.load()['creation']
        for _gate in ('genre', 'voice', 'scale', 'edge'):
            offered = shown(state)
            state = creation.pick(offered, offered['board']['options'][0]['id'],
                                  offered['board']['hash'], '作者选它。')
        self.assertEqual(creation.current(state)['id'], 'protagonist')
        rows = rows_for('protagonist')
        rows[0]['value'] = {**rows[0]['value'], 'name': '沈砚'}
        offered = creation.offer(state, {'gate': 'protagonist', 'options': rows})
        warnings = offered['board'].get('name_warnings') or []
        self.assertEqual([row['code'] for row in warnings], ['protagonist_name_cliche'])
        self.assertIn('沈砚', warnings[0]['message'])
        # Advisory, not a gate: the author may still choose the name they were warned about.
        picked = creation.pick(offered, rows[0]['id'], offered['board']['hash'], '作者就要这个名。')
        self.assertEqual(creation.selected(picked)['protagonist']['name'], '沈砚')

    def test_the_first_gate_brief_spreads_the_whole_catalog_when_no_direction_given(self):
        self.app.advance()
        work = self.repo.pending()['input']
        self.assertEqual(work['payload']['gate']['id'], 'genre')
        self.assertIn('全类目目录', work['brief'])
        for name, _hook in __import__('novel_ledger.contracts', fromlist=['GENRE_CATALOG']).GENRE_CATALOG:
            self.assertIn(name, work['brief'])


if __name__ == '__main__':
    unittest.main()
