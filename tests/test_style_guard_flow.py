"""Style observations remain visible without forcing factual prose into metric quotas."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts')]
from novel_ledger import contracts, planning, style
from novel_ledger.bootstrap import local_application
from novel_ledger.contracts import Error
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response, seeded_book


def dialogue_prose(head, quoted_count, total=17, length=4, start=0x4e00, marker='我'):
    """`head` (the stub's evidence quote) plus equal-length sentences, the first `quoted_count`
    quoted — dialogue share is exactly `quoted_count * length / (han(head) + total * length)`."""
    rows, cursor = [], start
    for index in range(total):
        body = marker + ''.join(chr(cursor + offset) for offset in range(length - 1))
        cursor += length
        rows.append(('「%s」' % body) if index < quoted_count else body)
    return head + '。'.join(rows) + '。'


class StyleGuardFlowTests(unittest.TestCase):
    def build(self, guard=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        raw = contract(chapters=2)
        raw.update(pov='第一人称', chapter_min=40, chapter_max=900, chapter_aim=120)
        if guard is not None:
            raw['style_guard'] = guard
        repo = SQLiteRepository.initialize(Path(temporary.name) / 'book', seeded_book(raw))
        self.addCleanup(repo.close)
        app = local_application(repo)
        drive(app, until='write')
        return repo, app

    def test_default_observations_are_visible_in_preview_and_saved_without_using_repair_budget(self):
        repo, app = self.build()
        self.assertEqual(repo.load()['contract']['style_guard'], contracts.DEFAULTS['style_guard'])
        result = response(app)
        # The original receipt supplies the true planned events and evidence. This introduction
        # adds no factual event; mentioning another person does not change first-person POV.
        result['data']['prose'] = (
            '我把书包挪到膝上，他还占着窗口。玻璃外一只蛾子撞着灯罩，'
            '我原想问昨晚的事，听见走廊里有人咳嗽，又把话咽了回去。\n'
            + result['data']['prose'])
        before = copy.deepcopy(repo.load())
        preview = app.submit(result, preview=True)
        report = preview['style_report']
        self.assertTrue(any(row['metric'] == 'person' for row in report['observations']))
        self.assertEqual(report['findings'], [])
        self.assertIsNone(preview['next_stage'])
        self.assertEqual(repo.load(), before)
        self.assertEqual(repo.headers('main'), [])
        accepted = app.submit(result)
        self.assertEqual(accepted['committed_chapter'], 1)
        self.assertEqual(repo.load()['rework']['1'],
                         {'initial_used': True, 'repairs': 0, 'redesigns': 0})
        record = repo.read_document(repo.chapter('main', 1)['review'])
        self.assertEqual(record['style_report'], accepted['style_report'])
        self.assertEqual(record['style_report']['observations'], report['observations'])

    def test_explicit_dialogue_target_remains_a_repair_condition_in_observe_mode(self):
        repo, app = self.build()
        # The scope is an isolated fixture: freeze a real zero-dialogue chapter declaration.
        book = repo.load()
        book['plans']['1']['style']['dialogue_ratio'] = 0
        repo.save(book)
        repo.cancel_pending('fixture refreezes the explicit chapter target')
        app.advance()
        result = response(app)
        result['data']['prose'] = '“先把门关上。”\n' + result['data']['prose']
        preview = app.submit(result, preview=True)
        self.assertEqual(preview['next_stage'], 'repair')
        self.assertTrue(any(row['metric'] == 'dialogue_ratio'
                            for row in preview['style_report']['findings']))
        self.assertEqual(repo.headers('main'), [])

    def test_a_later_chapters_dialogue_observation_expects_the_rolling_median(self):
        """Three chapters in, the untargeted dialogue row expects the median of the approved
        chapters rather than the pilot's opening number — and still neither blocks the commit
        nor spends repair budget (the observe semantics this file pins)."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        raw = contract(chapters=3)
        raw.update(pov='第一人称', chapter_min=40, chapter_max=900, chapter_aim=120)
        repo = SQLiteRepository.initialize(Path(temporary.name) / 'book', seeded_book(raw))
        self.addCleanup(repo.close)
        app = local_application(repo)
        owner = app.run(through=3, source='工程夹具：三章。')['owner']
        shares, outcome = {}, None
        for number, quoted in ((1, 4), (2, 8), (3, 17)):
            drive(app, owner, until='write')
            result = response(app)
            result['data']['prose'] = dialogue_prose(
                result['data']['prose'][:14], quoted, start=0x4e00 + number * 0x400)
            shares[number] = style.metrics(result['data']['prose'])['dialogue_share']
            outcome = app.submit(result)
            self.assertEqual(outcome['committed_chapter'], number)
            self.assertEqual(outcome['findings'], [])
        rows = [row for row in outcome['style_report']['observations']
                if row['metric'] == 'dialogue_share']
        self.assertEqual(len(rows), 1, outcome['style_report']['observations'])
        self.assertEqual(rows[0]['expect'], round((shares[1] + shares[2]) / 2, 3))
        self.assertNotEqual(rows[0]['expect'], shares[1])
        self.assertEqual(repo.load()['rework']['3'],
                         {'initial_used': True, 'repairs': 0, 'redesigns': 0})

    def test_guard_values_are_validated_and_a_strict_author_choice_is_preserved(self):
        strict = planning.validate_contract({**contract(), 'style_guard': 'strict'})
        self.assertEqual(strict['style_guard'], 'strict')
        for value in ('', 'loose', True, None):
            with self.subTest(value=value):
                with self.assertRaises(Error):
                    planning.validate_contract({**contract(), 'style_guard': value})


if __name__ == '__main__':
    unittest.main()
