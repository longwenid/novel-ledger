"""The volume-outline confirmation gate: staged designs, author commands, merged-half lock.

The gate sits between a volume outline's mechanical acceptance and its installation. What these
tests pin, in the order the design states them:

- a validated submission *stages* (`pending_design`); nothing installs until the author's own
  words confirm the exact `volumes_hash` — and on the merged tiers the chapter-outline half and
  the settlement rows stay locked with it, so confirmation installs both halves at once;
- the author's three commands: confirm (version-bound), revise (whitelist-narrow, re-validated,
  hash rebound) and regroup (reasoned refusal that feeds the next dispatch as frozen input);
- the blueprint: a book-level author choice that travels with the volume dispatch, switchable in
  the gate's regroup, and regenerable outside it without touching written volumes;
- the unattended boundary: `must_continue` is false and the advisories warn without blocking.
"""
import sys
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from novel_ledger.contracts import SCALE_TIERS, Error, digest
from novel_ledger import workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response, seeded_book, volume_outline_fixture


def tier_contract(tier_id, chapters=4, volumes=2):
    """A contract whose chapter band names `tier_id` (the merge switch is tier-declared)."""
    row = next(entry for entry in SCALE_TIERS if entry['id'] == tier_id)
    raw = contract(chapters=chapters, volumes=volumes)
    raw.update(chapter_min=row['chapter_min'], chapter_max=row['chapter_max'],
               chapter_aim=row['chapter_aim'])
    return raw


class VolumeGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'

    def tearDown(self):
        if getattr(self, 'repo', None) is not None:
            self.repo.close()
        self.temp.cleanup()

    def open(self, raw):
        self.repo = SQLiteRepository.initialize(self.project, seeded_book(raw))
        self.app = Application(self.repo)
        return self.app

    def stage(self, raw, hooks=None):
        """Advance to the volume dispatch, submit its receipt, and return the boundary handoff."""
        self.open(raw)
        self.owner = self.app.run(finish=True, source='工程夹具授权跑到卷纲。')['owner']
        handoff = drive(self.app, until='volume_outline')
        result = response(self.app)
        if hooks is not None:
            result['data'] = volume_outline_fixture(self.app, self.repo.pending()['input'], hooks=hooks)
        outcome = self.app.submit(result)
        boundary = self.app.advance(owner=self.owner)
        return outcome, boundary

    def test_a_merged_submission_stages_and_locks_both_halves(self):
        outcome, boundary = self.stage(tier_contract('t1', chapters=4, volumes=2))
        self.assertEqual(outcome['outcome'], 'volume_confirmation_required')
        self.assertEqual(outcome['next_action'], {'actor': 'author', 'action': 'confirm_volume'})
        self.assertFalse(outcome['continuation']['must_continue'])
        self.assertEqual(boundary['action'], 'await_volume_confirm')
        self.assertEqual(boundary['volumes'], ['v1', 'v2'])
        book = self.repo.load()
        pending = book['pending_design']
        self.assertEqual(pending['volume_ids'], ['v1', 'v2'])
        self.assertEqual(pending['volumes_hash'], boundary['volumes_hash'])
        self.assertEqual(pending['chapters'].keys(), {'v1', 'v2'})
        # The lock is structural, not a flag: neither half is installed while staged.
        self.assertEqual(book['volumes_outline'], {})
        self.assertEqual(book['chapter_outlines'], {})
        self.assertEqual(book['plans'], {})

    def test_the_board_is_materialized_and_compact_names_the_version(self):
        self.stage(contract(chapters=4, volumes=2))
        boundary = self.app.advance(owner=self.owner, compact=True)
        self.assertEqual(boundary['action'], 'await_volume_confirm')
        board = boundary['board']
        self.assertEqual(set(board), {'round', 'hash', 'volume_ids'})
        self.assertEqual(board['volume_ids'], ['v1', 'v2'])
        self.assertTrue(Path(boundary['board_card']).name == 'volume-board.md'
                        and Path(boundary['board_card']).is_file())
        card = Path(boundary['board_card']).read_text(encoding='utf-8')
        self.assertIn('卷纲待认可', card)
        self.assertNotIn(boundary['volumes_hash'], card)
        self.assertIn('完整待认可内容', card)
        self.assertIn('volume-design.md', card)
        self.assertTrue(Path(boundary['question_card']).name == 'volume-question.json'
                        and Path(boundary['question_card']).is_file())
        self.assertIn('认可这一版', Path(boundary['question_card']).read_text(encoding='utf-8'))

    def test_confirmation_card_and_hash_cover_merged_design(self):
        _outcome, boundary = self.stage(tier_contract('t1', chapters=4, volumes=2))
        pending = self.repo.load()['pending_design']
        self.assertNotIn('design', boundary['board'])
        self.assertEqual(boundary['volumes_hash'], workflow.design_hash(pending))
        card = Path(boundary['board_card']).read_text(encoding='utf-8')
        detail = Path(boundary['board_card']).with_name('volume-design.md')
        self.assertIn(str(detail), card)
        self.assertNotIn('```json', card)
        content = detail.read_text(encoding='utf-8')
        found = {}
        for label, ident, value in re.findall(r'### (卷纲|合并章纲|结算行) ([^\n]+)\n\n```json\n(.*?)\n```', content, re.S):
            found.setdefault({'卷纲': 'volumes', '合并章纲': 'chapters', '结算行': 'plans'}[label], {})[ident] = json.loads(value)
        self.assertEqual(found, {key: pending[key] for key in ('volumes', 'chapters', 'plans')})
        changed = dict(pending)
        changed['plans'] = {**pending['plans'], 'extra': {'chapter': 100}}
        self.assertNotEqual(workflow.design_hash(changed), boundary['volumes_hash'])
        self.assertFalse(workflow.verify_design_hash(changed))
        with self.repo.transaction():
            book = self.repo.load()
            book['pending_design']['plans'] = changed['plans']
            self.repo.save(book)
        with self.assertRaises(Error) as caught:
            self.app.confirm_volume(boundary['volumes_hash'], '认可已展示版本。', self.owner)
        self.assertEqual(caught.exception.code, 'volume_confirm')
        with self.assertRaises(Error) as caught:
            self.app.revise_volume([{'volume': 'v1', 'purpose': '调整叙述。'}],
                                   boundary['volumes_hash'], '调整叙述。', self.owner)
        self.assertEqual(caught.exception.code, 'volume_confirm')
        self.assertEqual(self.repo.load()['volumes_outline'], {})

    def test_legacy_volume_only_pending_still_confirms_with_clear_scope(self):
        _outcome, boundary = self.stage(tier_contract('t1', chapters=4, volumes=2))
        with self.repo.transaction():
            book = self.repo.load()
            pending = book['pending_design']
            pending['volumes_hash'] = digest(pending['volumes'])
            self.repo.save(book)
        boundary = self.app.advance(owner=self.owner)
        self.assertEqual(boundary['board']['hash_scope'], 'legacy_volumes')
        self.assertIn('确认版本仅绑定卷纲', Path(boundary['board_card']).read_text(encoding='utf-8'))
        self.assertTrue(self.app.confirm_volume(boundary['volumes_hash'], '认可旧版完整内容。', self.owner)['confirmed'])

    def test_rolling_advisories_compare_the_preceding_approved_volume(self):
        raw = contract(chapters=4, volumes=2)
        raw['volume_outline'] = {'scope': 'rolling', 'words': 2500, 'tolerance': 500}
        _outcome, boundary = self.stage(raw, hooks=False)
        self.assertNotIn('volume_turn_template', {w['code'] for w in boundary['board']['warnings']})
        self.app.confirm_volume(boundary['volumes_hash'], '认可第一卷。', self.owner)
        book = self.repo.load()
        prior = book['volumes_outline']['v1']
        current = copy.deepcopy(prior)
        current['id'] = 'v2'
        book['pending_design'] = {'scope': 'rolling', 'volume_ids': ['v2'], 'volumes': {'v2': current},
                                  'chapters': {}, 'plans': {}, 'round': 0}
        book['pending_design']['volumes_hash'] = workflow.design_hash(book['pending_design'])
        codes = {w['code'] for w in workflow.volume_board(book)['warnings']}
        self.assertIn('volume_turn_template', codes)
        self.assertIn('volume_entanglement_missing', codes)

    def test_confirmation_is_version_bound_and_installs_both_halves(self):
        _outcome, boundary = self.stage(tier_contract('t1', chapters=4, volumes=2))
        with self.assertRaises(Error) as caught:
            self.app.confirm_volume('0' * 64, '工程夹具认可错误版本。', self.owner)
        self.assertEqual(caught.exception.code, 'volume_confirm')
        # Completion stays refused while the design is staged: choose never says ready.
        with self.assertRaises(Error) as caught:
            self.app.complete(self.owner)
        self.assertEqual(caught.exception.code, 'completion')
        result = self.app.confirm_volume(boundary['volumes_hash'], '工程夹具认可这一版卷纲。', self.owner)
        self.assertTrue(result['confirmed'])
        book = self.repo.load()
        self.assertIsNone(book.get('pending_design'))
        self.assertEqual(sorted(book['volumes_outline']), ['v1', 'v2'])
        self.assertEqual(sorted(book['chapter_outlines']), ['v1', 'v2'])          # both halves, at once
        self.assertEqual(sorted(book['plans'], key=int), ['1', '2', '3', '4'])
        confirmed = book['volume_gate']['confirmed']['all']
        self.assertEqual(confirmed['volumes_hash'], boundary['volumes_hash'])
        actions = {row[0] for row in self.repo.db.execute("SELECT action FROM journal")}
        self.assertIn('volume_confirm', actions)
        # The gate opened: the merged tier goes straight from confirmation to prose.
        handoff = self.app.advance(owner=self.owner)
        self.assertEqual(handoff['action'], 'task_ready')
        self.assertEqual(handoff['task']['stage'], 'write')

    def test_revise_accepts_narrative_fields_revalidates_and_rebinds(self):
        _outcome, boundary = self.stage(contract(chapters=4, volumes=2))
        old_hash = boundary['volumes_hash']
        with self.assertRaises(Error) as caught:
            self.app.revise_volume([{'volume': 'v1', 'nodes': []}], old_hash, '工程夹具试图改结构。', self.owner)
        self.assertEqual(caught.exception.code, 'volume_revise')
        self.assertIn('nodes', caught.exception.details['unknown_fields'])
        with self.assertRaises(Error) as caught:
            self.app.revise_volume([{'volume': 'v1', 'style': {'trend': '更紧。',
                                                               'window': {'dialogue': 0.5}}}],
                                   old_hash, '工程夹具试图改容差。', self.owner)
        self.assertEqual(caught.exception.code, 'volume_revise')
        revised = self.app.revise_volume([{'volume': 'v1', 'purpose': '把退件来源从个人纠纷推到制度责任，并留下代价。'}],
                                         old_hash, '工程夹具只改卷职责。', self.owner)
        book = self.repo.load()
        self.assertNotEqual(revised['volumes_hash'], old_hash)
        self.assertEqual(book['pending_design']['volumes_hash'], revised['volumes_hash'])
        self.assertEqual(book['pending_design']['volumes']['v1']['purpose'],
                         '把退件来源从个人纠纷推到制度责任，并留下代价。')
        # The old version's hash no longer confirms anything: the author's words bind one version.
        with self.assertRaises(Error) as caught:
            self.app.confirm_volume(old_hash, '工程夹具按旧版认可。', self.owner)
        self.assertTrue(self.app.confirm_volume(revised['volumes_hash'], '工程夹具认可调整版。', self.owner)['confirmed'])

    def test_regroup_records_the_reason_and_feeds_the_next_dispatch(self):
        _outcome, boundary = self.stage(contract(chapters=4, volumes=2))
        result = self.app.regroup_volume(boundary['volumes_hash'], '两卷都只是换地图，旧账全清。', owner=self.owner)
        self.assertTrue(result['regrouped'])
        book = self.repo.load()
        self.assertIsNone(book.get('pending_design'))
        self.assertEqual(book['volume_gate']['round'], 1)
        refusal = book['volume_gate']['rejections'][0]
        self.assertEqual(refusal['reason'], '两卷都只是换地图，旧账全清。')
        self.assertEqual([row['id'] for row in refusal['volumes']], ['v1', 'v2'])
        # The refusal is frozen input for the re-run, not just audit.
        self.app.advance(owner=self.owner)
        pending = self.repo.pending()
        self.assertEqual(pending['input']['stage'], 'volume_outline')
        self.assertIn('volume_rejections', pending['input']['required'])
        frozen = self.repo.read_document(pending['input']['records']['volume_rejections'])
        self.assertEqual(frozen, pending['input']['payload']['volume_rejections'])
        self.assertEqual(frozen[0]['reason'], '两卷都只是换地图，旧账全清。')
        self.assertIn('两卷都只是换地图', pending['input']['brief'])
        self.assertIn('结构纪律', pending['input']['brief'])          # the discipline rides every volume brief

    def test_a_bound_blueprint_travels_with_the_volume_dispatch(self):
        self.open(contract(chapters=4, volumes=2))
        self.app.blueprint('主线副线缠绕', '工程夹具选定结构蓝图。')
        book = self.repo.load()
        self.assertEqual(book['structure_blueprint'], {'name': '主线副线缠绕', 'source': '工程夹具选定结构蓝图。'})
        self.owner = self.app.run(finish=True, source='工程夹具授权跑到卷纲。')['owner']
        drive(self.app, until='volume_outline')
        pending = self.repo.pending()
        payload = pending['input']['payload']
        self.assertEqual(payload['structure_blueprint']['name'], '主线副线缠绕')
        self.assertIn('blueprint', pending['input']['required'])
        self.assertIn('结构蓝图（作者选定：主线副线缠绕）', pending['input']['brief'])

    def test_regroup_can_switch_the_blueprint_with_the_rerun(self):
        _outcome, boundary = self.stage(contract(chapters=4, volumes=2))
        self.app.regroup_volume(boundary['volumes_hash'], '按新结构重出。', blueprint='双层揭秘', owner=self.owner)
        self.assertEqual(self.repo.load()['structure_blueprint']['name'], '双层揭秘')
        self.app.advance(owner=self.owner)
        payload = self.repo.pending()['input']['payload']
        self.assertEqual(payload['structure_blueprint']['name'], '双层揭秘')

    def test_a_recontract_drops_the_staging_and_keeps_the_author_records(self):
        """The migration contract of the gate: recontract rebuilds via new_book, so the staged
        design does not travel (the volume division may have changed — journalled), while the
        author's blueprint and the confirmation audit do, with round/refusals reset."""
        raw = contract(chapters=4, volumes=2)
        raw['volume_outline'] = {'scope': 'rolling', 'words': 2500, 'tolerance': 500}
        _outcome, boundary = self.stage(raw)                    # volume one stages, then confirms
        self.app.confirm_volume(boundary['volumes_hash'], '工程夹具认可第一卷。', self.owner)
        self.app.blueprint('复仇反推', '工程夹具改选蓝图。', owner=self.owner)
        drive(self.app, owner=self.owner, until='volume_outline')   # rolling: volume two's turn
        self.app.submit(response(self.app))
        self.assertIsNotNone(self.repo.load().get('pending_design'))
        second = contract(chapters=4, volumes=2)
        second['title'] = '夜班退件（改约）'
        self.app.recontract(second, '工程夹具改约：换一版前提。', owner=self.owner)
        # One advance both activates the staged contract and dispatches under it.
        self.app.advance(owner=self.owner)
        book = self.repo.load()
        self.assertEqual(book['contract']['title'], '夜班退件（改约）')
        self.assertIsNone(book.get('pending_design'))
        self.assertEqual([row[0] for row in self.repo.db.execute(
            "SELECT action FROM journal WHERE action='volume_gate_reset'")], ['volume_gate_reset'])
        # The author's direction and audit travel with the rebuilt book; the counters reset.
        self.assertEqual(book['structure_blueprint'], {'name': '复仇反推', 'source': '工程夹具改选蓝图。'})
        self.assertEqual(book['volume_gate']['round'], 0)
        self.assertEqual(book['volume_gate']['rejections'], [])
        self.assertEqual(book['volume_gate']['confirmed']['rolling']['volumes_hash'],
                         boundary['volumes_hash'])

    def test_blueprint_regenerate_retires_only_unwritten_volumes(self):
        self.open(contract(chapters=4, volumes=2))
        self.owner = self.app.run(finish=True, source='工程夹具授权写一卷。')['owner']
        drive(self.app, until='write')
        self.app.submit(response(self.app))                          # chapter 1 commits
        self.assertEqual([row['n'] for row in self.repo.headers('main')], [1])
        result = self.app.blueprint('阶段升格-同图深化', '工程夹具换蓝图重排后续。', regenerate=True, owner=self.owner)
        self.assertEqual(result['removed_volumes'], ['v2'])
        book = self.repo.load()
        self.assertEqual(sorted(book['volumes_outline']), ['v1'])   # written volume keeps its design
        self.assertEqual(sorted(book['chapter_outlines']), ['v1'])
        self.assertEqual(sorted(book['plans'], key=int), ['1', '2'])
        # With every volume written there is nothing left to retire.
        drive(self.app, owner=self.owner)
        with self.assertRaises(Error) as caught:
            self.app.blueprint('多线交错', '工程夹具全写完再换。', regenerate=True, owner=self.owner)
        self.assertEqual(caught.exception.code, 'blueprint')

    def test_board_advisories_are_countable_and_never_block(self):
        _outcome, boundary = self.stage(contract(chapters=4, volumes=2), hooks=False)
        board = boundary['board']
        codes = {row['code'] for row in board['warnings']}
        self.assertIn('volume_entanglement_missing', codes)          # two volumes, no continues anywhere
        self.assertIn('volume_turn_template', codes)                 # fixture turns are exactly 卷中/卷尾
        for row in board['volumes']:
            self.assertEqual(len(row['band']), 2)
            self.assertTrue(row['band'][0] <= row['han'] <= row['band'][1])   # the validator's own count
        self.assertTrue(self.app.confirm_volume(boundary['volumes_hash'], '工程夹具仍认可。', self.owner)['confirmed'])

    def test_the_cli_registers_the_four_author_commands(self):
        import novel
        parsed = novel.parser().parse_args(
            ['confirm-volume', '--hash', 'h', '--source', '原话'])
        self.assertEqual(parsed.hash, 'h')
        parsed = novel.parser().parse_args(
            ['revise-volume', '--file', '调整.json', '--hash', 'h', '--source', '原话'])
        self.assertEqual(parsed.file, '调整.json')
        parsed = novel.parser().parse_args(
            ['regroup-volume', '--hash', 'h', '--reason', '理由', '--blueprint', '多线交错'])
        self.assertEqual(parsed.blueprint, '多线交错')
        parsed = novel.parser().parse_args(['blueprint', '--name', '复仇反推', '--source', '原话'])
        self.assertFalse(parsed.regenerate)


if __name__ == '__main__':
    unittest.main()
