"""opening/5: the grand world keeps what the gates declared, word for word.

The redesign widened the world from ten flat domains to twelve (`powers`, `cosmology`), made the
world gate deliver a rank ladder and a hard currency as structured rows, and gave the older domains
optional deep fields. What makes those decisions more than decoration is the binding check: a rank,
a currency or a scale rung that exists in the gates but not in the world model is a design drift, and
the engine refuses it before a word is written. Two compatibility red lines run through everything
here: a world written before opening/5 (ten domains, no `powers`/`cosmology` key) must still pass,
and a gate that declared nothing new must not be asked about anything new.
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from novel_ledger import briefs, contracts, creation, drift, world, workflow
from novel_ledger.bootstrap import local_application as Application
from novel_ledger.contracts import Error, dump
from novel_ledger.sqlite_store import SQLiteRepository
from support import contract, drive, response, seeded_book, volume_rows

PREMISE = '退件来源背后是一条被垄断的登记制度。'
PROTAGONIST = {'id': 'shen', 'name': '沈桐', 'identity': '夜班工人',
               'desire': '查清责任。', 'limit': '不牵连无关同事。'}
TIER = 't3'


def tier_rows(count=4):
    """The rank ladder the world gate declares; `powers` has to keep it verbatim."""
    return [{'name': '第%d阶登记员' % (index + 1),
             'condition': '完成第%d次退件核对。' % (index + 1),
             'gain': '可调阅第%d层凭据。' % (index + 1),
             'cost': '承担第%d层的登记责任。' % (index + 1),
             'limit': '不得超过第%d层权限。' % (index + 1)} for index in range(count)]


def ladder_rows(scopes=('一城', '一界')):
    rows = []
    for index, scope in enumerate(scopes):
        rows.append({'stage': ('青云城', '青云界', '诸天之外')[index],
                     'scope': scope,
                     'growth': ('地盘', '规则', '文明')[index],
                     'new_rule': '第%d级起适用的新规则：登记与通行。' % (index + 1),
                     'cost': '升到第%d级要付出的代价：旧身份作废。' % (index + 1)})
    return rows


def choices_v5(tiers=True, ladder=True, resource=True, scales=('一城', '一界'), tier=TIER):
    """The selected opening choices a v5 world is checked against."""
    value = {'scale': {'tier': tier},
             'world': {'world_premise': PREMISE,
                       'mechanism': {'mode': 'none', 'principle': '只有规章与人情。',
                                     'cost': '行动承担现实责任。', 'limits': []},
                       'red_lines': [], 'allow_special_mechanism': False},
             'protagonist': dict(PROTAGONIST)}
    if tiers:
        value['world']['tiers'] = tier_rows()
    if resource:
        value['world']['resource'] = {'name': '登记凭证', 'source': '夜班结余里扣下的一份。',
                                      'allocator': '夜班主管'}
    if ladder:
        value['ladder'] = {'scale': {'opening': '第一章只见一座仓库与一条夜班线。',
                                     'terminal': '势力',
                                     'unchanged': '跨卷不变的是登记制度本身。'},
                           'ladder': ladder_rows(scales)}
    return value


def record(section, ident, **fields):
    row = {'id': ident, 'links': []}
    for field in world.SECTIONS[section]:
        row[field] = fields.get(field) or ('%s 的 %s。' % (ident, field))
    row.update(fields)
    return row


def base_model(choices, **overrides):
    """A world model that satisfies every binding these choices declared."""
    model = {'selection_hash': 'sel', 'premise': PREMISE,
             'story_capacity': '一条制度垄断线与一次责任追查足以承载长篇。'}
    for section in world.SECTIONS:
        model[section] = []
    model['characters'] = [{'id': PROTAGONIST['id'], 'name': PROTAGONIST['name'], 'role': '夜班工人',
                            'desire': PROTAGONIST['desire'], 'limit': PROTAGONIST['limit'],
                            'knowledge_boundary': '只知自己经手的货物。', 'links': []}]
    model['rules'] = [record('rules', 'r1', principle='退件必须登记负责人。')]
    declared = (choices.get('world') or {}).get('tiers') or []
    model['powers'] = [record('powers', 'rank%d' % (index + 1), **row)
                       for index, row in enumerate(declared)]
    resource = (choices.get('world') or {}).get('resource') or {}
    if resource:
        model['economy'] = [record('economy', 'currency', resource=resource['name'],
                                   distribution='由%s按班次分配。' % resource['allocator'])]
    for index, row in enumerate((choices.get('ladder') or {}).get('ladder') or []):
        if row['scope'] in contracts.COSMOLOGY_SCOPES:
            model['cosmology'].append(record('cosmology', 'layer%d' % index, name=row['stage']))
        else:
            model['geography'].append(record('geography', 'stage%d' % index, name=row['stage']))
    model.update(overrides)
    return model


def check(model, choices):
    """Validate against one explicit required domain, so the tier floor is never the subject.

    These cases are about the opening/5 declarations and bindings; asking for a whole tier's world
    here would make every failure ambiguous between "the binding was refused" and "the fixture did
    not fill ten domains".
    """
    return world.validate(model, choices, 'sel', sections=('rules',))


class LegacyWorldTests(unittest.TestCase):
    """The compatibility red line: a world written before opening/5 keeps passing."""

    def legacy_choices(self):
        value = choices_v5(tiers=False, ladder=False, resource=False)
        value.pop('ladder', None)
        return value

    def test_a_ten_domain_world_passes_and_is_normalized_to_the_full_shape(self):
        choices = self.legacy_choices()
        model = base_model(choices)
        for section in world.GRAND_SECTIONS:
            model.pop(section)                      # exactly what an in-flight project has on disk
        checked = check(model, choices)
        self.assertEqual(checked['powers'], [])
        self.assertEqual(checked['cosmology'], [])
        self.assertEqual(set(checked), {'selection_hash', 'premise', 'story_capacity', *world.SECTIONS})

    def test_the_legacy_tier_floor_never_demands_the_grand_domains(self):
        choices = self.legacy_choices()
        self.assertEqual(world.required_sections(TIER, choices), world.LEGACY_SECTIONS)
        for section in world.GRAND_SECTIONS:
            self.assertNotIn(section, world.required_sections(TIER, choices))
        self.assertEqual(world.declared_sections(choices), ())

    def test_the_ten_domains_are_still_declared_field_for_field(self):
        legacy = {'geography': ('name', 'environment', 'resources', 'access', 'story_pressure'),
                  'history': ('period', 'event', 'consequence', 'present_effect'),
                  'rules': ('principle', 'scope', 'limits', 'consequences'),
                  'factions': ('name', 'goal', 'power', 'dependencies', 'conflicts'),
                  'economy': ('resource', 'production', 'distribution', 'scarcity', 'conflict'),
                  'society': ('institution', 'norm', 'enforcement', 'pressure'),
                  'everyday': ('practice', 'constraint', 'story_use'),
                  'characters': ('name', 'role', 'desire', 'limit', 'knowledge_boundary'),
                  'mysteries': ('truth', 'disclosure', 'causal_role'),
                  'mechanisms': ('principle', 'cost', 'limits', 'failure_condition')}
        for section, fields in legacy.items():
            self.assertEqual(tuple(world.SECTIONS[section]), fields, section)
        self.assertEqual(world.SECTIONS['powers'], ('name', 'condition', 'gain', 'cost', 'limit'))
        self.assertEqual(world.SECTIONS['cosmology'], ('name', 'inhabitant', 'law', 'entry'))
        self.assertEqual(world.LABELS['powers'], '力量与位阶阶梯')
        self.assertEqual(world.LABELS['cosmology'], '空间与位面')


class DeclaredSectionTests(unittest.TestCase):
    """A domain the gates declared is a domain the world has to fill."""

    def test_a_declared_rank_ladder_makes_powers_required(self):
        choices = choices_v5(ladder=False, resource=False)
        self.assertEqual(world.declared_sections(choices), ('powers',))
        self.assertIn('powers', world.required_sections(TIER, choices))
        model = base_model(choices)
        model['powers'] = []
        with self.assertRaises(Error) as caught:
            check(model, choices)
        self.assertEqual(caught.exception.code, 'world_section')
        self.assertIn('powers', dump(caught.exception.details))
        # With the declared ranks present, the same model passes.
        check(base_model(choices), choices)

    def test_declared_currency_reaches_the_small_tier_brief_and_validator(self):
        for tier in ('t0', 't1', 't2'):
            with self.subTest(tier=tier):
                choices = choices_v5(tier=tier, scales=('局部', '一城', '一域'))
                # These stages are already represented in powers, so a small
                # world does not need extra geography solely to hold the names.
                for index, rung in enumerate(choices['ladder']['ladder']):
                    rung['stage'] = choices['world']['tiers'][index]['name']
                required = world.required_sections(tier, choices)
                self.assertIn('economy', required)
                brief = briefs.world_model(sections=required)
                instruction = next(line for line in brief.splitlines()
                                   if line.startswith('本项目按体量只需要：'))
                requested, empty = instruction.split('其余领域（', 1)
                self.assertIn('economy（资源与经济）', requested)
                self.assertNotIn('economy', empty)
                # Follow the rendered brief exactly: only its required domains
                # are populated, while all other domains stay empty.
                model = base_model(choices)
                for section in world.SECTIONS:
                    if section not in required:
                        model[section] = []
                    elif section != 'mechanisms' and not model[section]:
                        model[section] = [record(section, section + '-1')]
                checked = world.validate(model, choices, 'sel', sections=required)
                self.assertEqual(checked['economy'][0]['resource'],
                                 choices['world']['resource']['name'])
                model['economy'] = []
                with self.assertRaises(Error) as caught:
                    world.validate(model, choices, 'sel', sections=required)
                self.assertEqual(caught.exception.code, 'world_section')

    def test_a_legacy_small_world_does_not_gain_a_currency_requirement(self):
        for tier in ('t0', 't1', 't2'):
            with self.subTest(tier=tier):
                choices = choices_v5(tier=tier, tiers=False, ladder=False, resource=False)
                self.assertEqual(world.required_sections(tier, choices), world.TIER_SECTIONS[tier])

    def test_a_scope_ladder_that_reaches_a_plane_makes_cosmology_required(self):
        for scope in contracts.COSMOLOGY_SCOPES:
            with self.subTest(scope=scope):
                choices = choices_v5(tiers=False, resource=False, scales=('一城', scope))
                self.assertEqual(world.declared_sections(choices), ('cosmology',))
                model = base_model(choices)
                model['cosmology'] = []
                with self.assertRaises(Error) as caught:
                    check(model, choices)
                self.assertEqual(caught.exception.code, 'world_section')
                self.assertIn('cosmology', dump(caught.exception.details))

    def test_a_purely_local_ladder_does_not_require_cosmology(self):
        choices = choices_v5(tiers=False, resource=False, scales=('一城', '一域'))
        self.assertEqual(world.declared_sections(choices), ())
        self.assertNotIn('cosmology', world.required_sections(TIER, choices))
        model = base_model(choices)
        model['cosmology'] = []
        check(model, choices)

    def test_the_required_set_keeps_the_canonical_section_order(self):
        choices = choices_v5(scales=('一城', '一界'))
        required = world.required_sections(TIER, choices)
        self.assertEqual(required, tuple(section for section in world.SECTIONS if section in required))
        self.assertLess(required.index('powers'), required.index('cosmology'))


class BindingTests(unittest.TestCase):
    """The three verbatim bindings: a gate's decision must exist in the world, word for word."""

    def test_a_declared_rank_must_exist_verbatim_in_powers(self):
        choices = choices_v5(ladder=False, resource=False)
        declared = choices['world']['tiers'][1]
        missing = base_model(choices)
        missing['powers'] = [row for row in missing['powers'] if row['name'] != declared['name']]
        with self.assertRaises(Error) as caught:
            check(missing, choices)
        self.assertEqual(caught.exception.code, 'world_alignment')
        self.assertIn('world_tiers→powers', dump(caught.exception.details))
        # One changed field is already a mismatch: the binding is verbatim, not approximate.
        edited = base_model(choices)
        edited['powers'][1]['gain'] = '可调阅全部凭据。'
        with self.assertRaises(Error) as caught:
            check(edited, choices)
        self.assertEqual(caught.exception.code, 'world_alignment')
        self.assertIn('逐字', caught.exception.message + dump(caught.exception.details))

    def test_the_hard_currency_must_exist_in_the_economy_with_its_allocator(self):
        choices = choices_v5(ladder=False, tiers=False)
        declared = choices['world']['resource']
        absent = base_model(choices)
        absent['economy'] = [record('economy', 'other', resource='别的资源')]
        with self.assertRaises(Error) as caught:
            check(absent, choices)
        self.assertEqual(caught.exception.code, 'world_alignment')
        self.assertIn('world_resource→economy', dump(caught.exception.details))
        # A same-named resource whose record never names the allocator is still not bound.
        anonymous = base_model(choices)
        anonymous['economy'][0]['distribution'] = '按班次发放。'
        with self.assertRaises(Error) as caught:
            check(anonymous, choices)
        self.assertEqual(caught.exception.code, 'world_alignment')
        self.assertIn(declared['allocator'], dump(caught.exception.details))
        # Naming the allocator in another field of the same record does not bind it either: the
        # allocator has to appear where allocation is described (adversarial review F1).
        elsewhere = base_model(choices)
        elsewhere['economy'][0]['distribution'] = '按班次发放。'
        elsewhere['economy'][0]['conflict'] = '由%s决定份额。' % declared['allocator']
        with self.assertRaises(Error) as caught:
            check(elsewhere, choices)
        self.assertEqual(caught.exception.code, 'world_alignment')
        self.assertIn('distribution', dump(caught.exception.details))

    def test_every_ladder_stage_needs_a_same_named_record(self):
        choices = choices_v5(tiers=False, resource=False)
        stage = choices['ladder']['ladder'][0]['stage']
        model = base_model(choices)
        model['geography'] = [row for row in model['geography'] if row.get('name') != stage]
        with self.assertRaises(Error) as caught:
            check(model, choices)
        self.assertEqual(caught.exception.code, 'world_alignment')
        self.assertIn('world_ladder', dump(caught.exception.details))
        self.assertIn(stage, dump(caught.exception.details))
        # A same-named record in any of the four sections settles it.
        for section in ('geography', 'factions', 'powers'):
            with self.subTest(section=section):
                fixed = base_model(choices)
                fixed['geography'] = [row for row in fixed['geography'] if row.get('name') != stage]
                fixed[section].append(record(section, 'carrier', name=stage))
                check(fixed, choices)

    def test_an_unbound_world_that_declares_nothing_is_never_asked(self):
        choices = choices_v5(tiers=False, ladder=False, resource=False)
        model = base_model(choices)
        check(model, choices)


class OptionalFieldTests(unittest.TestCase):
    """Deep fields are optional; a field that is written has to say something."""

    CASES = (('history', 'epoch', '旧登记纪元'),
             ('history', 'carryover', '旧凭据在新制度下仍被承认。'),
             ('geography', 'scale', '一城'),
             ('geography', 'counter_space', '仓库背面的里世界。'),
             ('factions', 'survives_scale_up', '旧班组被新制度吸收为登记节点。'),
             ('mysteries', 'reveal_window', '第 12 章前后披露。'),
             ('mysteries', 'survival', '真相公开后靠旧凭据换取庇护。'))

    def choices(self):
        return choices_v5(tiers=False, ladder=False, resource=False)

    def test_a_written_deep_field_must_be_non_empty_text(self):
        for section, field, value in self.CASES:
            with self.subTest(section=section, field=field):
                choices = self.choices()
                good = base_model(choices)
                good[section] = [record(section, section + '1', **{field: value})]
                check(good, choices)
                for blank in ('', '   '):
                    with self.subTest(section=section, field=field, blank=repr(blank)):
                        broken = base_model(choices)
                        broken[section] = [record(section, section + '1', **{field: blank})]
                        with self.assertRaises(Error) as caught:
                            check(broken, choices)
                        self.assertEqual(caught.exception.code, 'world_optional')
                        self.assertIn(field, dump(caught.exception.details))

    def test_a_world_without_the_deep_fields_is_still_complete(self):
        choices = self.choices()
        model = base_model(choices)
        model['history'] = [record('history', 'h1')]
        model['factions'] = [record('factions', 'f1')]
        check(model, choices)


class VolumeStageTests(unittest.TestCase):
    """§6: the scale ladder lands on the volumes, verbatim and only climbing."""

    def setUp(self):
        self.book = seeded_book(contract(chapters=4, volumes=2))
        self.contract = self.book['contract']
        self.world = self.book['world']
        self.state = self.book['state']
        self.rows = volume_rows(self.book, ['v1', 'v2'])
        self.selected = {'ladder': {'scale': {'opening': '第一章只见一座仓库。',
                                              'terminal': '势力',
                                              'unchanged': '登记制度本身。'},
                                    'ladder': ladder_rows()}}

    def submit(self, rows, selected=None):
        return drift.validate_volume_outline({'volumes': rows}, self.contract, self.world,
                                             self.selected if selected is None else selected,
                                             {}, ['v1', 'v2'], self.state)

    def assertRejected(self, rows, needle=None):
        with self.assertRaises(Error) as caught:
            self.submit(rows)
        self.assertEqual(caught.exception.code, 'design_drift')
        criteria = {finding.get('criterion') for finding in caught.exception.details['findings']}
        self.assertIn('volume_stage', criteria, dump(caught.exception.details))
        if needle is not None:
            self.assertIn(needle, dump(caught.exception.details))
        return caught.exception

    def stages(self):
        rungs = [row['stage'] for row in self.selected['ladder']['ladder']]
        rows = copy.deepcopy(self.rows)
        rows[0]['stage'] = rungs[0]
        rows[1]['stage'] = rungs[1]
        return rows

    def test_the_declared_stage_survives_into_the_report(self):
        report = self.submit(self.stages())
        rungs = [row['stage'] for row in self.selected['ladder']['ladder']]
        self.assertEqual([report['v1']['stage'], report['v2']['stage']], [rungs[0], rungs[1]])

    def test_a_stage_that_is_not_one_of_the_ladder_rungs_is_rejected(self):
        rows = self.stages()
        rows[1]['stage'] = '不存在的层级'
        self.assertRejected(rows, '不存在的层级')

    def test_the_stages_may_repeat_but_may_not_descend(self):
        rungs = [row['stage'] for row in self.selected['ladder']['ladder']]
        repeated = self.stages()
        repeated[1]['stage'] = rungs[0]                 # holding a rung is legal
        self.assertEqual(self.submit(repeated)['v2']['stage'], rungs[0])
        descending = self.stages()
        descending[0]['stage'] = rungs[1]
        descending[1]['stage'] = rungs[0]
        self.assertRejected(descending)

    def test_an_opening_without_a_ladder_may_leave_the_stage_empty(self):
        report = self.submit(copy.deepcopy(self.rows), selected={})
        self.assertEqual([report['v1']['stage'], report['v2']['stage']], ['', ''])

    def test_a_free_stage_is_ignored_when_no_ladder_was_declared(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['stage'] = '任何旧项目写下的层级'
        report = self.submit(rows, selected={})
        self.assertEqual(report['v1']['stage'], '任何旧项目写下的层级')


class PromiseAnchorTests(unittest.TestCase):
    """§4.4: the theme anchor is promised to a chapter inside the tier's own window."""

    def payoff(self, deliverable='第 N 章前必须让读者看到一次当众兑现。', deadline_chapter='30'):
        return {'ending': '退件来源公开，工人承担违规开箱的后果。',
                'theme': '责任怎样在人之间传递。',
                'plan': {'ways': ['核对签字打脸推责的人', '拿到被压的第二层笔迹'],
                         'cadence': '三到五章一次小兑现，章末留一个待查的封条。',
                         'hooks': '每卷中段翻出上一层签字链，卷尾落一次责任。'},
                'anchor': {'deliverable': deliverable, 'deadline_chapter': deadline_chapter}}

    def test_the_deadline_is_capped_by_the_tier_window_and_the_platform_line(self):
        cap = contracts.DEFAULTS['world_ladder']['anchor_max_chapter']
        choices = {'scale': {'tier': TIER}}
        creation.validate_value('payoff', self.payoff(deadline_chapter=str(cap)), 5, choices)
        with self.assertRaises(Error) as caught:
            creation.validate_value('payoff', self.payoff(deadline_chapter=str(cap + 1)), 5, choices)
        self.assertEqual(caught.exception.code, 'opening_option')
        self.assertIn(str(cap), dump(caught.exception.details))

    def test_the_anchor_needs_a_concrete_deliverable_and_a_numeric_deadline(self):
        choices = {'scale': {'tier': TIER}}
        for anchor in ({'deliverable': '待补', 'deadline_chapter': '10'},
                       {'deliverable': '第 N 章前必须兑现一次当众反转。', 'deadline_chapter': '十章'},
                       {'deliverable': '第 N 章前必须兑现一次当众反转。', 'deadline_chapter': '0'}):
            with self.subTest(anchor=anchor):
                with self.assertRaises(Error) as caught:
                    creation.validate_value('payoff', self.payoff(**anchor), 5, choices)
                self.assertEqual(caught.exception.code, 'opening_option')


class LegacyV4ProjectTests(unittest.TestCase):
    """The largest compatibility risk: an in-flight v4 project with a ten-domain world.

    opening/5 widened the world and the gate set, but a project already running keeps its own
    protocol: its eleven gates still put boards in front of the author, its world (written before the
    grand domains existed, so it has no `powers`/`cosmology` key at all) still passes the `_audit`
    re-check, and the derived book page still renders every legacy domain.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'book'
        self.repo = SQLiteRepository.initialize(self.project,
                                                workflow.preparing_book(guided=True, opening_version=4))
        self.app = Application(self.repo)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_a_v4_opening_still_puts_a_board_in_front_of_the_author(self):
        handoff = self.app.advance()
        self.assertEqual(handoff['task']['stage'], 'opening_options')
        self.app.submit(response(self.app))
        handoff = self.app.advance()
        self.assertEqual(handoff['action'], 'await_choice')
        self.assertTrue(handoff['board']['options'])
        card = Path(handoff['board_card']).read_text(encoding='utf-8')
        self.assertIn(handoff['board']['hash'], card)
        self.assertIn(handoff['board']['gate']['title'], card)
        self.assertIn('第 1/%d 门' % len(creation.GATE_SETS[4]), card)

    def test_a_v4_project_with_a_ten_domain_world_still_audits_and_renders(self):
        from novel_ledger import bookpage
        handoff = drive(self.app)
        self.assertEqual(handoff['action'], 'outline_ready')
        book = self.repo.load()
        self.assertEqual(len(book['creation']['selections']), 11)     # the v4 gate set
        for section in world.GRAND_SECTIONS:
            book['world'].pop(section, None)                          # exactly what an old project has
        self.repo.save(book)
        self.assertTrue(self.app.audit()['ok'])
        page = bookpage.render(self.repo)
        for section in world.LEGACY_SECTIONS:
            self.assertIn(world.LABELS[section], page, section)


if __name__ == '__main__':
    unittest.main()
