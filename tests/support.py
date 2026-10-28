"""Synthetic engineering receipts and the five-step pipeline's fixtures.

These are never literary judgments: every string below exists so the mechanical checks can run.
The v2 pipeline (spec: `.team/spec-v2.md`) has four dispatches before prose instead of a review
chain, and two of them hand back *state declarations* rather than prose — a volume outline and a
chapter outline whose deltas the engine simulates. The fixtures therefore do two jobs the old ones
did not:

* `volume_outline_fixture` / `chapter_outline_fixture` build rows the engine's simulation accepts,
  including the `enter`/`exit` chain: chapter *i*'s `enter` is the simulated state after chapter
  *i-1*'s deltas, and its `exit` is `enter` plus this chapter's own deltas (spec §4.4–4.5).
* `drift_check_fixture` files the writer's own item-by-item comparison against that chapter row,
  one item per planned delta, with `actual.from` read off the projected state (spec §5).

Tests that want a drift to be *rejected* copy one of these and break exactly one field; the
fixtures stay valid by construction so a rejection never means "the fixture was wrong".
"""
import copy
import uuid

from novel_ledger import context, drift, drift_simulation, drift_validation, facts, store_keys, workflow
from novel_ledger.contracts import (CONTRACT_FIELDS, COSMOLOGY_SCOPES, DERIVED_FIELDS, RESULT, digest, han_count,
                                    opening_source, policy_default, require)
from novel_ledger.result_templates import drift_items, template


def link_or_skip(case, link, target, target_is_directory=False):
    """Create a symbolic link, or report the host's missing capability as a skip.

    Windows only creates symbolic links with SeCreateSymbolicLinkPrivilege (Developer Mode or an
    elevated token). The alias and escape regressions that need one cannot be executed without it,
    and failing them would blame the engine for a host setting it does not own. Hard links need no
    privilege, so they are never guarded this way. The created link is returned for chaining.
    """
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        case.skipTest('此宿主不能创建符号链接：' + str(exc))
    return link


# --------------------------------------------------------------------------------------------------
# The contract every engineering fixture writes
# --------------------------------------------------------------------------------------------------

def contract(chapters=2, volumes=1, volume_words=None, chapter_words=None,
             volume_tolerance=None, chapter_tolerance=None, structural_rows=False):
    """A small, complete author contract with the two v2 outline policies declared.

    `chapter_min`/`chapter_max` are deliberately tiny: these tests drive whole books, and the prose
    stub only has to land inside the band. The outline policies default to the engine's own
    declarations (`contracts.policy_default`) so a fixture can never disagree with the band the
    validator applies; a test may still shrink them explicitly to exercise the length check without
    writing a page of filler.

    `structural_rows` includes structured world rows for direct-import validation.
    """
    volume_policy = policy_default('volume_outline')
    chapter_policy = policy_default('chapter_outline')
    if volume_words is not None:
        volume_policy['words'] = volume_words
    if volume_tolerance is not None:
        volume_policy['tolerance'] = volume_tolerance
    if chapter_words is not None:
        chapter_policy['words'] = chapter_words
    if chapter_tolerance is not None:
        chapter_policy['tolerance'] = chapter_tolerance
    raw = {'narrative_tracking': False, 'editorial_features': False,
           'volume_outline': volume_policy,
           'chapter_outline': chapter_policy,
           'title': '夜班退件', 'genre': '都市生活',
           'reader_promise': '一个夜班工人查清退件来源并承担自己的选择。',
           'ending': '退件来源公开，工人承担违规开箱的后果。', 'world_premise': '一座仓库的夜班退件纠纷。',
           'story_engine': '核对退件来源，追查签字责任。', 'opposition': '主管担心调查影响考核。',
           'voice': '以动作、物件、对白和后果呈现夜班人情。', 'allow_special_mechanism': False,
           'style_traits': ['少重复解释。', '因果承接完整。'],
           'relationships': ['同事互相依赖，却各自担心承担责任。'],
           'protagonist_setup': {'id': 'shen', 'name': '沈桐', 'identity': '夜班工人',
                                 'desire': '查清责任。', 'limit': '不牵连无关同事。'},
           'world_rules': ['夜班退件必须登记负责人。'],
           'chapter_min': 12, 'chapter_max': 90, 'chapter_aim': 60,
           'word_range': [12 * chapters, 200 * chapters],
           'volumes': [{'id': 'v' + str(i + 1), 'purpose': '查明来源并面对后果。',
                        'end': (i + 1) * chapters // volumes} for i in range(volumes)],
           'entities': [{'id': 'shen', 'name': '沈桐', 'kind': 'person'}],
           'initial_resources': [{'holder': 'shen', 'asset': '车费', 'unit': '元', 'quantity': '4'}],
           # Two places so a chapter outline can declare a position delta without inventing one.
           'places': [{'id': 'office', 'name': '值班室'}, {'id': 'yard', 'name': '仓库后院'}],
           'placements': {'shen': 'office'}}
    if structural_rows:
        # opening/5's two structural rows, each exactly the declared shape (the validator compares
        # the row's key set for equality). These fields are optional for direct imports.
        raw['world_tiers'] = [{'name': '一阶登记员', 'condition': '连续夜班满一年',
                               'gain': '可独立开箱核对', 'cost': '每次核对耗掉一夜精力',
                               'limit': '只对本仓库的退件有效'}]
        raw['world_ladder'] = [{'stage': '夜班作业区', 'scope': '局部', 'growth': '地盘',
                                'new_rule': '退件必须登记负责人', 'cost': '得罪当班同事'}]
    return raw


def world_fixture(raw=None):
    """The minimum world model the seeded (non-opening) path needs.

    A book loaded from `workflow.new_book` has no world until the guided opening writes one, but the
    v2 chapter-outline validator reads the world for `world_refs` and for place/entity existence. The
    seeded path therefore installs this model, whose records line up one-for-one with what the
    outline fixtures reference: `rules:r1`, `geography:office`, `geography:yard`,
    `characters:shen`, and an economy record for the contract's starting resource.

    A contract that already carries the opening/5 structural rows (`world_tiers`,
    `world_resource`, `world_ladder`) gets them mirrored into `powers`/`economy`/`geography` (and
    `cosmology` for a grand rung), because the three bindings are what the world validator checks
    when the choices declared them.
    """
    raw = raw or contract()
    protagonist = (raw.get('protagonist_setup') or {}).get('id') or 'shen'
    name = (raw.get('protagonist_setup') or {}).get('name') or '沈桐'
    rules = raw.get('world_rules') or ['夜班退件必须登记负责人。']
    assets = [row.get('asset') for row in raw.get('initial_resources') or [] if row.get('asset')] or ['车费']
    model = {
        'premise': raw.get('world_premise') or '一座仓库的夜班退件纠纷。',
        'story_capacity': '仓库、夜班、退件流程与签字制度足以承载一次来源核对与责任追查。',
        'geography': [_place('office', '值班室'), _place('yard', '仓库后院')],
        'history': [],
        'rules': [{'id': 'r' + str(index + 1), 'principle': rule,
                   'scope': '本仓库的夜班退件处理。', 'limits': '只约束已登记的退件。',
                   'consequences': '违反者承担登记责任。', 'links': []}
                  for index, rule in enumerate(rules)],
        'factions': [],
        'economy': [{'id': 'asset-' + str(index + 1), 'resource': asset,
                     'production': '按班次发放。', 'distribution': '由主管登记后发放。',
                     'scarcity': '不足时需要自付。', 'conflict': '谁承担这笔支出。', 'links': []}
                    for index, asset in enumerate(assets)],
        'society': [],
        'everyday': [],
        'characters': [{'id': protagonist, 'name': name,
                        'role': '夜班工人', 'desire': '查清责任。', 'limit': '不牵连无关同事。',
                        'knowledge_boundary': '只知自己经手的货物。',
                        'links': ['rules:r1']}],
        'mysteries': [],
        'mechanisms': [],
        # All domains are present; unused domains are explicit empty arrays.
        # (`world.index` and the section walk read every declared section).
        'powers': [],
        'cosmology': [],
    }
    for index, tier in enumerate(raw.get('world_tiers') or [], 1):
        model['powers'].append({'id': 'tier%d' % index, 'name': tier.get('name', ''),
                                'condition': tier.get('condition', ''), 'gain': tier.get('gain', ''),
                                'cost': tier.get('cost', ''), 'limit': tier.get('limit', ''),
                                'links': []})
    resource = raw.get('world_resource') or {}
    if resource:
        allocator = resource.get('allocator') or '主管'
        model['economy'].append({'id': 'currency', 'resource': resource.get('name', ''),
                                 'production': resource.get('source') or '夜班结余',
                                 'distribution': '由' + allocator + '按班次登记后分配。',
                                 'scarcity': '每班只放行固定份额。',
                                 'conflict': '谁拿到分配权谁定责任。', 'links': []})
    from novel_ledger import world as world_module
    grand = COSMOLOGY_SCOPES
    for index, level in enumerate(raw.get('world_ladder') or [], 1):
        stage = level.get('stage', '')
        if not stage:
            continue
        if level.get('scope') in grand:
            model['cosmology'].append({'id': 'layer%d' % index, 'name': stage,
                                       'inhabitant': '在' + stage + '活动的势力与居民。',
                                       'law': '进入' + stage + '后适用的规则。',
                                       'entry': '沿' + stage + '的入口推进入场。', 'links': []})
        else:
            model['geography'].append(_place('stage%d' % index, stage,
                                             environment=stage + '的空间与环境。'))
    return model


def _place(ident, name, **extra):
    row = {'id': ident, 'name': name, 'environment': '夜间照明的作业区。',
           'resources': '退回的货物与登记册。', 'access': '夜班人员可进。',
           'story_pressure': '退件必须有人签字。', 'links': []}
    row.update(extra)
    row['links'] = list(extra.get('links') or [])
    return row


def seeded_book(raw=None):
    """A book ready for step three: the contract is installed and the world it reads is seeded.

    Without a guided opening the engine never dispatches `world_model`, so a test that starts from
    a hand-written contract has to put a world on the book itself — otherwise the chapter-outline
    validator has no world to ground `world_refs` against. This is the one line every flow test would
    otherwise repeat (spec §3/§4 read the world, not the contract).
    """
    book = workflow.new_book(raw if raw is not None else contract())
    book['world'] = world_fixture(book['contract'])
    return book


# The fixture's relation ladder: one stable short word per rung, so a chapter chain that walks it
# exercises the literal continuity (chapter N's `to` is chapter N+1's `from`) without free prose.
RELATION_WORDS = ('戒备', '试探', '同盟')


def relation_book(chapters=4, volumes=1):
    """A tracked book whose contract and world both carry a second registered entity.

    A relation coordinate needs two registered ends (`facts.apply_event` refuses a relation whose
    source or target is not an entity), and the default contract only registers the protagonist —
    so every relation-delta fixture starts here instead of patching `entities` by hand.
    """
    raw = contract(chapters=chapters, volumes=volumes)
    raw['narrative_tracking'] = True
    raw['entities'] = list(raw['entities']) + [{'id': 'guan', 'name': '管衡', 'kind': 'person'}]
    book = seeded_book(raw)
    book['world']['characters'].append({'id': 'guan', 'name': '管衡', 'role': '主管',
                                        'desire': '考核达标。', 'limit': '不替人担责。',
                                        'knowledge_boundary': '只看考核数字。', 'links': ['rules:r1']})
    return book


def _relation_step(current):
    """The next rung of the relation ladder, or None once the top rung is reached."""
    if current is None:
        return RELATION_WORDS[0]
    position = RELATION_WORDS.index(current) if current in RELATION_WORDS else len(RELATION_WORDS)
    return RELATION_WORDS[position + 1] if position + 1 < len(RELATION_WORDS) else None


def _relation_terminal(start, count):
    """The rung a chain starting at `start` reaches after `count` declared chapters."""
    at = start
    for _ in range(count):
        step = _relation_step(at)
        if step is None:
            break
        at = step
    return at


def node(ident, dependencies=()):
    """A volume-outline node row (spec §3). `dependencies` is accepted for the old call sites."""
    return {'id': ident, 'kind': 'main', 'purpose': '推进退件来源的核对。',
            'ending_condition': '来源核对有明确结论。', 'required': True,
            'window': [1, 1], 'depends_on': list(dependencies)}


# --------------------------------------------------------------------------------------------------
# Text shaping: the outline policies measure 汉字, so the fixtures have to hit a declared count
# --------------------------------------------------------------------------------------------------

SYNOPSIS_SENTENCE = ('沈桐为核对封条追问经手人，主管以签字制度阻拦，'
                     '他选择对照旧凭据并承担保管责任，发现笔迹矛盾后决定追查下一批退件。')
ARC_SENTENCE = ('本卷从一次退回的箱子写起，沈桐先被制度挡在门外，随后用旧凭据撬开缺口，'
                '中段以责任逐层扩散换取更深的证据，卷末由他公开来源并承担违规的代价。')
VOLUME_PURPOSE = '把退件来源从个人纠纷推到制度责任。'
VOLUME_CLIMAX = '公开来源与签字矛盾，沈桐承担违规开箱的后果。'
VOLUME_EXIT = '卷末：车费结余；沈桐在后院；对来源仅到怀疑；主线推进到登记责任。'


def _fit_text(seed, target):
    """Pad or trim `seed` until its 汉字 count is exactly `target`.

    Padding appends numbered beats (第一拍、第二拍…) instead of repeating the seed: the
    chapter-outline validator rejects verbatim-repeated clauses as filler, and fixtures
    stand for valid receipts.
    """
    digits = '零一二三四五六七八九'

    def _cn(number):
        return ''.join(digits[int(d)] for d in str(number))

    value = seed if isinstance(seed, str) and seed else '核对'
    beat = 0
    while han_count(value) < target:
        beat += 1
        value += '；第%s拍补叙核对与让步' % _cn(beat)
    while han_count(value) > target:
        value = value[:-1]
    return value


def _han(value):
    """Count every 汉字 in a nested JSON-shaped value."""
    if isinstance(value, str):
        return han_count(value)
    if isinstance(value, dict):
        return sum(_han(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(_han(item) for item in value)
    return 0


# --------------------------------------------------------------------------------------------------
# Step three: one ~1000-character outline per volume
# --------------------------------------------------------------------------------------------------







def _hooks_on(value):
    """Whether a fixture row declares promises: explicit wins, else the session default.

    Hooks are on by default. A test may explicitly use `hooks=False`.
    """
    if value is not None:
        return bool(value)
    return True

def volume_hooks(book, volume):
    """The volume's declared promises: one required in-volume hook plus one continuing one.

    The required hook is planted in the volume's first chapter and paid in its last, which is the
    tightest window the policy allows; the continuing hook is planted here and paid in the next
    volume's first chapter, which is the cross-volume shape §1.1 describes. The last volume declares
    no continuing hook: it has no later volume to pay it in, and `complete()` refuses an open one.
    """
    volumes = book['contract']['volumes']
    index = next(position for position, row in enumerate(volumes) if row['id'] == volume['id'])
    rows = [{'id': 'hook-%s-required' % volume['id'],
             'text': '读者看到退回凭据的来历，并要知道它最终由谁负责。',
             'plant': [volume['first'], volume['first']],
             'payoff': [volume['end'], volume['end']],
             'required': True, 'continues': False}]
    if index + 1 < len(volumes):
        following = volumes[index + 1]
        rows.append({'id': 'hook-%s-carry' % volume['id'],
                     'text': '读者记住那张旧凭据，等着看它最终落到谁手里。',
                     'plant': [volume['first'], volume['first']],
                     'payoff': [following['first'], following['first']],
                     'required': False, 'continues': True})
    return rows


def volume_outline_fixture(app, work, hooks=None, relations=False):
    """The receipt for `volume_outline`: one row per volume this dispatch answers.

    Declares the nodes and threads the following `chapter_outline` dispatch has to advance, the
    promises the volume opens and closes (`hooks`), and an `exit_state` the volume's simulated close
    has to land on. `arc` absorbs whatever length is left after the structured fields so the row's
    total 汉字 count is exactly the policy's `words`. `relations=True` also declares each volume's
    relation terminal, computed from the same ladder the chapter rows walk.

    On a tier that merges the two artifacts (`merge_chapter_outline`), the same receipt also carries
    `chapters`, grouped by volume id — the engine validates each group with the chapter-outline
    contract against the state the book is actually in, which is exactly a separate dispatch's check.
    """
    book = app.repo.load()
    contract = book['contract']
    payload = work.get('payload') or {}
    policy = payload.get('volume_outline') or contract.get('volume_outline') or {}
    words = policy.get('words') or 2500
    tracking = bool(contract.get('narrative_tracking'))
    wanted = payload.get('volume_ids') or [row['id'] for row in contract['volumes']]
    enabled = _hooks_on(hooks)
    rows = []
    walked = None
    for ident in wanted:
        volume = next(row for row in contract['volumes'] if row['id'] == ident)
        terminal = _relation_terminal(walked, volume['end'] - volume['first'] + 1) if relations else None
        walked = terminal if relations else walked
        rows.append(_volume_row(book, volume, words, tracking, hooks=enabled, relation_to=terminal))
    data = {'volumes': rows}
    if 'chapter_outline' in tuple(payload.get('also') or ()):
        # One receipt, several volumes: the engine validates them in book order and carries the
        # chain forward, so the fixture has to design them that way too — volume two's opening
        # chapter continues from volume one's designed close, not from the frozen book state.
        data['chapters'] = {}
        state = book['state']
        for ident, outline in zip(wanted, rows):
            volume = next(row for row in contract['volumes'] if row['id'] == ident)
            chapters = chapter_rows(book, volume, state, hooks=enabled, relations=relations)
            data['chapters'][ident] = chapters
            state = drift_simulation.simulate(chapters, state, book.get('world'), volume, outline)[0]
    return data


def volume_rows(book, volume_ids=None, words=None, hooks=None, stage=None, relations=False):
    """The volume outline rows for `volume_ids`, sized to the policy's per-volume 汉字 target.

    Public so a drift-unit test can build the same rows the dispatch fixture builds without an
    application: `drift_validation.validate_volume_outline` is deterministic over (contract, world, rows).
    `hooks=False` switches every promise off at once, which is how a test isolates the non-hook
    checks from the hook chain. `stage` may be a list of rungs to assign by volume order (a test
    building a book without an opening needs the ladder explicitly), or a single stage for all.
    `relations=True` declares each volume's relation terminal, walking the fixture ladder by volume
    order the same way the chapter rows do.
    """
    contract = book['contract']
    policy = contract.get('volume_outline') or {}
    target = words if words is not None else policy.get('words') or 2500
    tracking = bool(contract.get('narrative_tracking'))
    enabled = _hooks_on(hooks)
    volumes = contract['volumes']
    wanted = list(volume_ids or [row['id'] for row in volumes])
    rows = []
    walked = None
    for ident in wanted:
        volume = next(row for row in volumes if row['id'] == ident)
        chosen = None
        if isinstance(stage, (list, tuple)):
            position = next((index for index, row in enumerate(volumes) if row['id'] == ident), 0)
            chosen = stage[min(position, len(stage) - 1)] if stage else ''
        elif stage is not None:
            chosen = stage
        terminal = _relation_terminal(walked, volume['end'] - volume['first'] + 1) if relations else None
        walked = terminal if relations else walked
        rows.append(_volume_row(book, volume, target, tracking, hooks=enabled, stage=chosen,
                                relation_to=terminal))
    return rows


def volume_stage(book, volume):
    """The rung of the opening's scale ladder this volume sits on (opening/5 §6).

    The engine requires a volume's `stage` to be one of the declared ladder stages, rising
    monotonically with the contract's volume order. A book opened before the ladder existed declares
    none, and then the field stays empty for this direct import.
    """
    from novel_ledger import creation
    opening = book.get('creation') or {}
    choices = creation.selected(opening) if opening else {}
    levels = (book['contract']['world_ladder'] if 'world_ladder' in book['contract']
              else _ladder_levels(choices))
    if not levels:
        return ''
    volumes = book['contract']['volumes']
    index = next((position for position, row in enumerate(volumes) if row['id'] == volume['id']), 0)
    return levels[min(index, len(levels) - 1)].get('stage', '')


def _volume_row(book, volume, words, tracking, hooks=False, stage=None, relation_to=None):
    first, last = volume['first'], volume['end']
    count = last - first + 1
    nodes = [{'id': 'n' + str(chapter), 'kind': 'main',
              'purpose': '第%d章推进来源核对。' % chapter,
              'ending_condition': '本章核对有结论。', 'required': True,
              'window': [chapter, chapter]}
             for chapter in range(first, last + 1)]
    threads = [{'id': 'line-' + volume['id'], 'kind': 'main', 'purpose': '核对退件来源并承担后果。',
                'ending_condition': '来源公开且责任落实。', 'required': True}]
    row = {'id': volume['id'], 'purpose': VOLUME_PURPOSE,
           'stage': volume_stage(book, volume) if stage is None else stage,
           'arc': '',
           'turns': [{'at': '卷中', 'turn': '旧凭据暴露出签字矛盾。'},
                     {'at': '卷尾', 'turn': '沈桐公开来源并接受处理。'}],
           'climax': VOLUME_CLIMAX,
           'nodes': nodes, 'threads': threads,
           'resources': [], 'places': [], 'knowledge': [], 'characters': [],
           'clock': {'advance_days': count, 'to': last},
           'exit_state': VOLUME_EXIT,
           'style': {'trend': '以短句、动作与凭据核对推进，卷末用较长段落交代责任后果。'},
           # A required array in v2.1: an empty one is the declaration "this volume promises nothing
           # new", which is a claim the chain can read, while a missing field is nothing at all.
           'hooks': volume_hooks(book, volume) if hooks else []}
    if relation_to is not None:
        # The optional terminal: declared, so the volume's simulated close must land on it.
        protagonist = (book['contract'].get('protagonist_setup') or {}).get('id') or 'shen'
        row['relations'] = [{'source': protagonist, 'target': 'guan', 'key': 'alliance',
                             'to': relation_to, 'reason': '卷末两人关系到达这一档。'}]
    others = _han({key: value for key, value in row.items() if key != 'arc'})
    row['arc'] = _fit_text(ARC_SENTENCE, max(0, words - others))
    return row


# --------------------------------------------------------------------------------------------------
# Step four: one chapter outline per volume, carrying the enter/exit state chain
# --------------------------------------------------------------------------------------------------

def anchor_state(app, book, payload, volume):
    """The state a chapter-outline chain starts from on this dispatch.

    A volume drafted ahead of the writing front (`anchor: design`) continues from the *designed* end
    of every earlier volume whose outlines are already installed: no prose exists yet, so nothing has
    settled, and anchoring it on the frozen book state is what made a two-volume merged receipt
    unanswerable. The volume about to be written anchors on the projection instead.
    """
    state = book['state']
    if (payload or {}).get('anchor') != 'design':
        return state
    for prior in book['contract']['volumes']:
        if prior['end'] >= volume['first']:
            break
        rows = (book.get('chapter_outlines') or {}).get(prior['id'])
        if rows:
            outline = (book.get('volumes_outline') or {}).get(prior['id'])
            state = drift_simulation.simulate(rows, state, book.get('world'), prior, outline)[0]
    return state


def chapter_outline_fixture(app, work, resources=True, places=True, knowledge=True,
                            characters=None, nodes=None, clock_days=1, hooks=None, relations=False):
    """The receipt for `chapter_outline`: the volume's chapters, each declaring its deltas.

    Every chapter declares a clock advance, a resource spend, a position move and a step up the
    reveal ladder when the projected state has them; each row's `enter` holds the state the
    simulation arrives with and `exit` holds `enter` plus this chapter's deltas, which is the
    redundancy the engine recomputes. Nodes are only advanced on tracked contracts (spec §2:
    `narrative_tracking=false` may leave `plot.nodes/threads` empty). `hooks` schedules the volume's
    declared promises: planted in its first chapter, paid in its last, with the previous volume's
    continuing hook paid on entry (spec §1.2). `relations=True` also walks one rung of the relation
    ladder per chapter until its top, keying the coordinate the way the engine does.
    """
    book = app.repo.load()
    contract = book['contract']
    payload = work.get('payload') or {}
    policy = payload.get('chapter_outline') or contract.get('chapter_outline') or {}
    words = policy.get('words') or 150
    volume_id = payload.get('volume')
    volume = next(row for row in contract['volumes'] if row['id'] == volume_id)
    first = payload.get('from_chapter') or volume['first']
    last = policy.get('last', volume['end'])
    rows = chapter_rows(book, volume, anchor_state(app, book, payload, volume),
                        first=first, words=words,
                        resources=resources, places=places, knowledge=knowledge,
                        characters=characters, nodes=nodes, clock_days=clock_days, hooks=hooks,
                        relations=relations)
    return {'volume': volume['id'],
            **({'through_chapter': last} if payload.get('allow_retained_suffix') else {}),
            'chapters': [row for row in rows if row['chapter'] <= last]}


def chapter_rows(book, volume, state, first=None, words=None, resources=True, places=True,
                 knowledge=True, characters=None, nodes=None, clock_days=1, hooks=None,
                 relations=False):
    """The chapter rows for `volume`, each declaring its deltas and its enter/exit handshake.

    `state` is the projected state the chain starts from, and is copied: the caller's state is
    never advanced. Public so a drift-unit test can hand `drift_validation.validate_chapter_outline` rows
    without paying for an application dispatch. `hooks=False` switches the promise schedule off,
    which is how a test isolates a non-hook check from the chain. `relations=True` walks the
    relation ladder until its top rung, then stops declaring (the coordinate simply holds).
    """
    contract = book['contract']
    policy = contract.get('chapter_outline') or {}
    target = words if words is not None else policy.get('words') or 150
    tracking = bool(contract.get('narrative_tracking')) if nodes is None else bool(nodes)
    if characters is None:
        characters = tracking
    enabled = _hooks_on(hooks)
    scratch = copy.deepcopy(state)
    start = first if first is not None else volume['first']
    return [_chapter_row(scratch, book, volume, number, target,
                         resources=resources, places=places, knowledge=knowledge,
                         characters=characters, tracking=tracking, clock_days=clock_days,
                         hooks=enabled, relations=relations)
            for number in range(start, volume['end'] + 1)]


def chapter_hooks(book, volume, number):
    """The promise actions one chapter executes (spec §1.2).

    Only two actions exist. The volume's own required hook is planted in the first chapter and paid
    in the last (the same chapter when the volume is a single chapter, which is the short hook the
    spec allows). A continuing hook is planted on entry and paid by the next volume's first chapter,
    which pays its predecessor's. Nothing else re-mentions a promise: that is `hook_refs`.
    """
    volumes = book['contract']['volumes']
    index = next(position for position, row in enumerate(volumes) if row['id'] == volume['id'])
    last_volume = index + 1 == len(volumes)
    rows = []
    if number == volume['first']:
        if index:
            rows.append({'hook': 'hook-%s-carry' % volumes[index - 1]['id'], 'action': 'payoff',
                         'note': '本卷开篇兑现上一卷留下的承诺。'})
        rows.append({'hook': 'hook-%s-required' % volume['id'], 'action': 'plant',
                     'note': '本卷开篇埋下对读者的具体承诺。'})
        if not last_volume:
            rows.append({'hook': 'hook-%s-carry' % volume['id'], 'action': 'plant',
                         'note': '埋下一条跨卷承诺，留给下一卷兑现。'})
    if number == volume['end']:
        rows.append({'hook': 'hook-%s-required' % volume['id'], 'action': 'payoff',
                     'note': '本卷末兑现本卷承诺。'})
    return rows


def _chapter_row(state, book, volume, number, words, resources=True, places=True,
                 knowledge=True, characters=None, tracking=False, clock_days=1, hooks=False,
                 relations=False):
    """Build one chapter row and advance `state` by its deltas (the simulation the engine repeats)."""
    contract = book['contract']
    protagonist = (contract.get('protagonist_setup') or {}).get('id') or 'shen'
    row = {'chapter': number, 'synopsis': _fit_text(SYNOPSIS_SENTENCE, words),
           'plot': {'beat': '沈桐核对封条与签字，逼出下一处矛盾。', 'nodes': [], 'threads': []},
           'resources': [], 'places': [], 'knowledge': [], 'characters': [], 'relations': [],
           'clock': {'advance_days': clock_days}, 'enter': [], 'exit': [],
           'disclosures': [], 'world_refs': _world_refs(book), 'new_entities': [],
           'hook_refs': [], 'reader_refs': [], 'history_refs': [], 'scenes': [], 'pacing': {},
           'style': {'pov': contract.get('pov') or '第三人称限知',
                     'rhythm': '短句交代动作，核对结果后用完整句说明后果。'},
           # Required in v2.1; `[]` means this chapter executes no promise action.
           'hooks': chapter_hooks(book, volume, number) if hooks else []}
    deltas = []          # (kind, key, before, after)
    # Clock: the one delta every chapter declares, and the one the prose stub always supports.
    deltas.append(('clock', 'clock', state['clock'], state['clock'] + clock_days))
    state['clock'] += clock_days
    # Resources: spend one unit of the first balance that has anything left, keyed by the projection
    # key `facts.resource_key` itself uses so the two sides cannot disagree about identity.
    if resources and state.get('resources'):
        for key in sorted(state['resources']):
            current = _as_number(state['resources'][key])
            if current >= 1:
                before = _plain_number(current)
                after = _plain_number(current - 1)
                row['resources'].append({'key': key, 'from': before, 'to': after,
                                         'reason': '核对退件时花掉一趟车费。'})
                deltas.append(('resources', key, before, after))
                state['resources'][key] = str(after)
                break
    # Places: move the protagonist between the two contract places, alternating each chapter.
    if places and state.get('placements') and len(state.get('places') or {}) >= 2:
        ident = next(iter(sorted(state['placements'])))
        places_list = sorted(state['places'])
        current = state['placements'][ident]
        target = next(place for place in places_list if place != current)
        row['places'].append({'entity': ident, 'from': current, 'to': target,
                              'reason': '从值班室走到后院核对退件。'})
        deltas.append(('places', ident, current, target))
        state['placements'][ident] = target
    # Knowledge: the reader-facing reveal ladder the outline speaks in (hinted→suspected→confirmed).
    if knowledge:
        key = protagonist + ':source'
        current = _reveal(state, key)
        after = {None: 'hinted', 'hinted': 'suspected', 'suspected': 'confirmed'}.get(current)
        if after is not None:
            row['knowledge'].append({'who': protagonist, 'topic': 'source', 'from': current,
                                     'to': after, 'reason': '本章核对让沈桐对来源多了一层判断。'})
            deltas.append(('knowledge', key, current, after))
            state.setdefault('knowledge', {})[key] = {'status': after}
    if characters and tracking:
        before = state.get('character_current', {}).get(protagonist, {}).get('value')
        after = {'desire': '查清退件来源。', 'stance': '先核对再行动。',
                 'relationship_focus': '与主管的责任边界。'}
        row['characters'].append({'entity': protagonist, 'from': before, 'to': after,
                                  'choice': '先核对凭据再开箱。', 'cost': '承担违规开箱的责任。'})
        deltas.append(('characters', protagonist, before, after))
        state.setdefault('character_current', {})[protagonist] = {'value': after}
    # Relations: one rung up the ladder per chapter until the top, then the coordinate holds.
    # `from` is the rung the scratch state stands on, so chapter N's `to` is chapter N+1's `from`
    # verbatim — the literal continuity the engine's drift_chain check enforces.
    if relations:
        coordinate = protagonist + '>guan:alliance'
        current = (state.get('relations') or {}).get(coordinate)
        after = _relation_step(current)
        if after is not None:
            row['relations'].append({'source': protagonist, 'target': 'guan', 'key': 'alliance',
                                     'from': current, 'to': after,
                                     'reason': '核对退件让两人的相处方式变了。'})
            deltas.append(('relations', coordinate, current, after))
            state.setdefault('relations', {})[coordinate] = after
    # Nodes: one per chapter in the volume row, advanced here only on tracked contracts.
    if tracking:
        ident = 'n' + str(number)
        before = state.get('story_nodes', {}).get(ident, {}).get('status')
        row['plot']['nodes'] = [{'node': ident, 'after': 'resolved',
                                 'outcome': '本章核对有结论。'}]
        deltas.append(('node', ident, before, 'resolved'))
        state.setdefault('story_nodes', {})[ident] = {'status': 'resolved'}
        if number == volume['end']:
            thread = 'line-' + volume['id']
            before = state.get('thread_progress', {}).get(thread, {}).get('status')
            row['plot']['threads'] = [{'thread': thread, 'after': 'resolved',
                                       'reason': '本卷核对完成，线路收束。'}]
            deltas.append(('thread', thread, before, 'resolved'))
            state.setdefault('thread_progress', {})[thread] = {'status': 'resolved'}
    for kind, key, before, after in deltas:
        enter_kind = 'character' if kind == 'characters' else kind
        # The main clock's coordinate is `clock/main` everywhere the engine reads coordinates
        # (story_memory, narrative); the delta array itself stays keyed by `clock`.
        enter_key = 'main' if kind == 'clock' else key
        row['enter'].append({'kind': enter_kind, 'key': enter_key, 'expected': before})
        row['exit'].append({'kind': enter_kind, 'key': enter_key, 'expected': after})
    return row


def _world_refs(book):
    """Refs the row can cite: the seeded records the chapter actually walks through.

    `everyday` joins the filter so a fixture chapter can name life material — with the written
    `nightshift` record the opening path's stored world now cites it, and a world without
    everyday records keeps exactly the refs it always had. Tests that need a specific set of
    refs set `world_refs` explicitly rather than leaning on this cap's ordering.
    """
    model = book.get('world') or {}
    refs = []
    for section, rows in model.items():
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and row.get('id'):
                    refs.append(section + ':' + row['id'])
    wanted = [ref for ref in refs if ref.split(':', 1)[0] in ('geography', 'rules', 'characters', 'everyday')]
    return wanted[:3]


# The reader-facing reveal ladder the chapter outline declares, and how the projection spells it.
REVEALS = ('hinted', 'suspected', 'misled', 'confirmed', 'retracted')
STANCES = {'hinted': 'suspects', 'suspected': 'suspects', 'misled': 'believes',
           'confirmed': 'knows', 'retracted': 'disproved'}
STANCE_REVEALS = {stance: reveal for reveal, stance in STANCES.items()}


def _reveal(state, key):
    """The reveal stage a knowledge projection entry stands at, or None."""
    entry = ((state or {}).get('knowledge') or {}).get(key)
    if not isinstance(entry, dict):
        return None
    if entry.get('status') in REVEALS:
        return entry['status']
    return STANCE_REVEALS.get(entry.get('stance'))


def _as_number(value):
    from decimal import Decimal
    try:
        return Decimal(str(value))
    except Exception:                       # noqa: BLE001 - a non-numeric balance is not spendable
        return Decimal(0)


def _plain_number(value):
    """A JSON-safe int/float for a declared quantity: the outlines speak numbers, not strings."""
    return int(value) if value == int(value) else float(value)


# --------------------------------------------------------------------------------------------------
# Step five: the writer's self-comparison
# --------------------------------------------------------------------------------------------------

def chapter_row_of(app, work):
    """The chapter settlement row a dispatch is about, from the frozen material.

    The writer's row travels as a required record (`work['records']['chapter_outline']`); an older
    or combined dispatch also carries it inline in `payload`. Reading the record first means a
    context change that empties the payload cannot silently turn the drift_check into an empty one.
    """
    payload_row = (work.get('payload') or {}).get('chapter_outline')
    if isinstance(payload_row, dict) and payload_row:
        return payload_row
    name = (work.get('records') or {}).get('chapter_outline')
    if name:
        document = app.repo.read_document(name)
        if isinstance(document, dict):
            return document
    return {}


def drift_check_fixture(app, work, prose, status='kept', deviations=None):
    """`drift_check` for one chapter: exactly one item per planned delta, before-values projected.

    The planned side comes from `result_templates.drift_items(row)` — the same function the blank
    template uses — so the coverage the engine checks and the coverage the writer is asked for are
    one declaration. `actual.from` is the engine's projection of the current state, never the
    writer's guess; on a clean chain it equals `planned.from` because the enter/exit chain already
    proved it. Promises are filed as `kind='hook'` rows (`planned={'action': ...}`) when the chapter
    row declares them and the template does not already pre-fill them.
    """
    book = app.repo.load()
    state = book['state']
    row = chapter_row_of(app, work)
    chapter = row.get('chapter') or work.get('chapter')
    quote = _quote(prose)
    items = []
    for item in drift_items(row):
        planned = copy.deepcopy(item['planned'])
        kind = item['kind']
        if kind == 'clock':
            actual = {'advance_days': planned.get('advance_days')}
        elif kind in ('node', 'thread', 'disclosure'):
            actual = {'after': planned.get('after')}
        elif kind == 'hook':
            actual = {'action': planned.get('action')}
        else:
            actual = {'from': drift.project(state, kind, item['key']), 'to': planned.get('to')}
        items.append({'kind': kind, 'key': item['key'], 'planned': planned, 'actual': actual,
                      'status': status, 'reason': '正文中该变化有明确动作与后果。',
                      'evidence': {'chapter': chapter, 'quote': quote}})
    filed = {(item['kind'], item['key']) for item in items}
    for entry in row.get('hooks') or []:
        if not isinstance(entry, dict) or not entry.get('hook'):
            continue
        coordinate = ('hook', entry['hook'])
        if coordinate in filed:
            continue
        action = entry.get('action')
        items.append({'kind': 'hook', 'key': entry['hook'], 'planned': {'action': action},
                      'actual': {'action': action}, 'status': status,
                      'reason': '正文中该承诺按章纲埋下或兑现。',
                      'evidence': {'chapter': chapter, 'quote': quote}})
    return {'items': items, 'unplanned': list(deviations or []), 'verdict': 'clean'}




def _quote(prose):
    """A verbatim fragment of the prose, used as every item's evidence quote."""
    for marker in ('次日', '封条', '退回'):
        if marker in prose:
            return prose[max(0, prose.index(marker) - 2):prose.index(marker) + 14]
    return prose[:16]


# --------------------------------------------------------------------------------------------------
# The guided opening's world and contract (only used when a test drives the gates)
# --------------------------------------------------------------------------------------------------

# The scope enum's grand end: from these scales on, a world model needs a `cosmology` section
# (opening/5 §2/§5). Read from the engine when it declares the table, with the spec's frozen values as
# the fallback so the fixture works while the implementation is still landing.




def _world_tiers(choices):
    return [row for row in ((choices.get('world') or {}).get('tiers') or [])
            if isinstance(row, dict)]


def _world_resource(choices):
    value = (choices.get('world') or {}).get('resource')
    return value if isinstance(value, dict) else {}


def _ladder_levels(choices):
    return [row for row in ((choices.get('ladder') or {}).get('ladder') or [])
            if isinstance(row, dict) and row.get('stage')]




def _generic_record(section, index, tiers):
    """One placeholder record for a required section the choices did not populate."""
    from novel_ledger import world as world_module
    fields = world_module.SECTIONS[section]
    name = {
        'geography': '仓库后院', 'history': '旧交接制度', 'rules': '夜班退件必须登记负责人。',
        'factions': '夜班班组', 'economy': '车费', 'society': '登记制度',
        'everyday': '夜班交接', 'characters': '沈桐', 'mysteries': '退件来源',
        'mechanisms': '有代价的机制', 'powers': '一阶登记员', 'cosmology': '仓库之界',
    }.get(section, section + str(index))
    row = {'id': '%s%d' % (section[:3], index)}
    for field in fields:
        row[field] = name if field in ('name', 'principle', 'practice', 'institution',
                                       'resource', 'period', 'truth', 'layer') else name + '的' + field
    row.setdefault('name', name)
    row['links'] = []
    return row


def _opening_model(book):
    """A world model that satisfies `world.validate` for the choices already made.

    opening/5 binds the gates to the world: the declared tier ladder must exist verbatim in
    `powers`, the hard currency must exist in `economy` with its allocator named, and every rung of
    the scale ladder must have a same-named record in `geography`/`cosmology`/`factions`/`powers`.
    The fixture therefore mirrors the choices into those sections instead of writing a generic world;
    the section set it fills is what the engine says this tier and these choices require.
    """
    from novel_ledger import contracts, creation, world as world_module
    opening = book.get('creation') or {}
    choices = creation.selected(opening)
    premises = (choices.get('world') or {}).get('world_premise') or '一座仓库的夜班退件纠纷。'
    mechanism = (choices.get('world') or {}).get('mechanism') or {}
    protagonist = choices.get('protagonist') or {}
    ident = protagonist.get('id') or 'shen'
    name = protagonist.get('name') or '沈桐'
    tiers = _world_tiers(choices)
    resource = _world_resource(choices)
    levels = _ladder_levels(choices)
    grand = COSMOLOGY_SCOPES
    model = {'selection_hash': opening.get('selection_hash') or '',
             'premise': premises,
             'story_capacity': '仓库、夜班与签字制度足以承载一次来源核对和一场责任追查。',
             'geography': [_place('office', '值班室'), _place('yard', '仓库后院')],
             'history': [], 'rules': [], 'factions': [], 'economy': [], 'society': [],
             # One written-by-hand everyday record instead of the placeholder the required-section
             # loop would mint: a non-empty section makes that loop skip it, so the fixture world
             # carries real life material a chapter outline can name in `world_refs`.
             'everyday': [{'id': 'nightshift',
                           'practice': '夜班交接时按册核对退件，签字后才放行。',
                           'constraint': '人手不够时交接只能口头顶替，出事由签字人担。',
                           'story_use': '登记册、旧凭据与夜班规矩给日常章质感。',
                           'links': []}],
             'characters': [{'id': ident, 'name': name, 'role': '夜班工人',
                             'desire': protagonist.get('desire') or '查清责任。',
                             'limit': protagonist.get('limit') or '不牵连无关同事。',
                             'knowledge_boundary': '只知自己经手的货物。',
                             'links': []}],
             'mysteries': [], 'mechanisms': [], 'powers': [], 'cosmology': []}
    model['rules'] = [{'id': 'r1', 'principle': '夜班退件必须登记负责人。',
                       'scope': '本仓库夜班退件。', 'limits': '只约束已登记退件。',
                       'consequences': '违反者承担登记责任。', 'links': []}]
    if mechanism.get('mode') == 'bounded':
        model['mechanisms'] = [{'id': 'm1',
                                'principle': mechanism.get('principle') or '特殊机制有代价地生效。',
                                'cost': mechanism.get('cost') or '每次使用都要付出代价。',
                                'limits': '、'.join(mechanism.get('limits') or []) or '限一次。',
                                'failure_condition': '代价无法支付时失效。', 'links': []}]
    # The declared tier ladder, verbatim, as the powers section's records.
    for index, tier in enumerate(tiers, 1):
        model['powers'].append({'id': 'tier%d' % index,
                                'name': tier.get('name', ''), 'condition': tier.get('condition', ''),
                                'gain': tier.get('gain', ''), 'cost': tier.get('cost', ''),
                                'limit': tier.get('limit', ''), 'links': []})
    # The hard currency: an economy row whose resource is the declared name and whose distribution
    # names the declared allocator (the engine checks that the allocator text appears on the record).
    if resource:
        allocator = resource.get('allocator') or '夜班主管'
        model['economy'].append({'id': 'currency', 'resource': resource.get('name', ''),
                                 'production': resource.get('source') or '夜班结余',
                                 'distribution': '由' + allocator + '按班次登记后分配。',
                                 'scarcity': '每班只放行固定份额。',
                                 'conflict': '谁拿到分配权谁定责任。', 'links': []})
    # Every rung of the scale ladder gets a same-named record; a rung at the grand scales lands in
    # cosmology, which is also what makes that section required.
    for index, level in enumerate(levels, 1):
        stage = level.get('stage', '')
        scope = level.get('scope') or ''
        if scope in grand:
            model['cosmology'].append({'id': 'layer%d' % index, 'name': stage,
                                       'inhabitant': '在' + stage + '活动的势力与居民。',
                                       'law': '进入' + stage + '后适用的规则。',
                                       'entry': '沿' + stage + '的入口推进入场。', 'links': []})
        else:
            model['geography'].append(_place('stage%d' % index, stage,
                                             environment=stage + '的空间与环境。'))
    # Whatever the engine still requires gets one concrete placeholder record, so the fixture is
    # accepted on every tier without pretending to be a full world.
    tier_id = ((choices.get('scale') or {}).get('tier')) or None
    for section in world_module.required_sections(tier_id, choices):
        if section == 'mechanisms' or model.get(section):
            continue
        model[section] = [_generic_record(section, 1, tiers)]
    frame = (choices.get('world') or {}).get('architecture') or {}
    for key, _note, section, field in contracts.WORLD_ARCHITECTURE:
        if key in frame:
            row = _generic_record(section, 99, tiers)
            row[field] = frame[key]
            if section == 'geography':
                # Geography names are unique now; the generic placeholder name ('仓库后院')
                # would collide with the yard record the model already declares.
                row['name'] = '世界全貌与通行边界'
            model[section].append(row)
    return model


def _opening_contract(book, model):
    """The contract the combined dispatch hands back: the choices projected onto contract fields."""
    from novel_ledger import creation
    opening = book.get('creation') or {}
    choices = creation.selected(opening)
    creation.opening_version(opening)
    scale = choices.get('scale') or {}
    total = scale.get('chapters') or (scale.get('chapter_window') or [12])[0]
    raw = contract(chapters=total, volumes=scale.get('volume_count') or 1)
    protagonist = choices.get('protagonist') or {}
    ident = protagonist.get('id') or 'shen'
    for row in CONTRACT_FIELDS:
        if row['key'] in DERIVED_FIELDS:
            continue
        source = opening_source(row)
        if not source:
            continue
        gate, key = source
        raw[row['key']] = copy.deepcopy(choices[gate] if key is None else choices[gate][key])
    raw.update(world_premise=(choices.get('world') or {}).get('world_premise') or raw['world_premise'],
               entities=[{'id': ident, 'name': protagonist.get('name') or '沈桐', 'kind': 'person'}],
               initial_resources=[{'holder': ident, 'asset': '车费', 'unit': '元', 'quantity': '4'}],
               placements={ident: 'office'},
               world_rules=[row['principle'] for row in model['rules']],
               red_lines=copy.deepcopy((choices.get('world') or {}).get('red_lines')
                                       or (choices.get('genre') or {}).get('red_lines') or []))
    return raw


# --------------------------------------------------------------------------------------------------
# The receipt
# --------------------------------------------------------------------------------------------------

# Synthetic option texts for the opening gates. They must satisfy the engine's option contract as
# well as the gate's value shape: two options whose drivers do not share a shape, two to three
# concrete scenes of at least twelve characters, and no self-description of the creative method (the
# option text is what the author reads, not a note about how it was generated).
_OPTION_DRIVERS = ('从一张签错的封条入手，逼主管当场对质。',
                   '先被调去守后院，再从交接单上找缺口。',
                   '把退件箱直接寄给承运方，逼对方签字确认。')
_OPTION_TRADEOFFS = ('相比另案，放弃更快的升职路线。',
                     '相比另案，放弃稳定的夜班岗位。',
                     '相比另案，放弃同事的信任。')
_OPTION_SCENES = ('夜班仓库里，他把退件箱推到灯下，翻出封条上的签名。',
                  '凌晨的登记台前，他逐页核对自己经手的那一栏。',
                  '货站卸货口，他拦住要开走的车，要求当场核对凭据。')
# Which leaf of the fixture value the second option changes, so the two options are different
# directions rather than one idea written twice.
_OPTION_ALT = {'genre': 'reader_promise', 'premise': 'novelty', 'origin': 'arrival', 'voice': 'voice',
               'world': 'world_premise', 'ladder': 'scale.opening', 'edge': 'advantage',
               'protagonist': 'identity', 'relationships': 'relationships',
               'opposition': 'opposition', 'payoff': 'ending', 'title': 'title'}
# The first rung must not reuse a place name the fixture world already declares (`值班室` is the
# office): geography names are unique now, and the office record plus a same-named ladder rung is
# exactly the ambiguity the check refuses.
_LADDER_STAGE_NAMES = ('夜班作业区', '货站', '分拨中心', '跨域承运网', '全国承运网', '界门',
                       '界外走廊', '诸天渡口')


def opening_gate_values(book):
    """One valid value per opening gate for the protocol this book was opened under.

    Tier-dependent gates (the world's tier ladder and the scale ladder, plus the theme anchor's
    deadline) read the tier the structural gate already answered, so the generated values stay
    inside the floors the engine declared in `contracts.DEFAULTS['world_ladder']`.
    """
    from novel_ledger import contracts, creation
    opening = book.get('creation') or {}
    choices = creation.selected(opening)
    creation.opening_version(opening)
    scale = choices.get('scale') or {}
    tier = next((row for row in contracts.SCALE_TIERS if row['id'] == scale.get('tier')), None)
    floors = contracts.DEFAULTS['world_ladder']
    tier_count = floors['tier_min'].get(tier['id'], 3) if tier else 3
    stage_count = floors['stage_min'].get(tier['id'], 3) if tier else 3
    limit = floors['anchor_max_chapter'] if tier is None else min(floors['anchor_max_chapter'],
                                                                 tier['chapter_window'][1])
    scopes = contracts.WORLD_SCOPES
    growths = contracts.WORLD_GROWTHS
    tiers = [{'name': '%d阶登记员' % (index + 1),
              'condition': '连续夜班满%d年且无差错' % (index + 1),
              'gain': '可独立开箱核对第%d批退件' % (index + 1),
              'cost': '每次核对耗掉%d夜精力' % (index + 1),
              'limit': '只对本仓库第%d批退件有效' % (index + 1)}
             for index in range(tier_count)]
    levels = [{'stage': _LADDER_STAGE_NAMES[index], 'scope': scopes[index % len(scopes)],
               'growth': growths[index % len(growths)],
               'new_rule': '第%d级起适用的规则：过级要凭证' % (index + 1),
               'cost': '第%d级的代价：欠下守门人的人情' % (index + 1)}
              for index in range(stage_count)]
    values = {
        'genre': {'genre': '都市异能', 'reader_promise': '看他从仓库夜班一路把签字责任查到底。',
                  'tone': '冷硬利落，偶尔留一点暖。'},
        'premise': {'novelty': '这个世界的退件签字会改写责任归属，谁签谁背。',
                    'first_cause': '上一轮签字制度崩过一次，才有了现在的登记规矩。',
                    'stance': '利用', 'dark_side': '制度'},
        'origin': {'family': '魂穿', 'arrival': '车祸后醒在这座仓库的夜班宿舍，带着上一世的核对习惯。',
                   'cost': '原身的旧账跟着他，同事只当他忽然变了一个人。'},
        'voice': {'pov': '第三人称限知，只跟沈桐的所见所知。', 'voice': '短句推进，对白带信息。',
                  'style_traits': ['少解释多动作。', '章末留钩。'], 'style_profile': '市井修仙'},
        'world': {'world_premise': '一座仓库的夜班退件纠纷。',
                  'mechanism': {'mode': 'none', 'principle': '只有普通规章与人情。',
                                'cost': '行动承担现实责任。', 'limits': []},
                  'red_lines': ['没有超自然能力。'], 'allow_special_mechanism': False,
                  'tiers': tiers,
                  'resource': {'name': '车费', 'source': '夜班结余',
                               'allocator': '夜班主管按班次登记后发放'}},
        'ladder': {'scale': {'opening': '开局只看得见仓库这片夜班作业区，读者跟着一间屋子往外看。',
                             'terminal': '体系', 'unchanged': '上层机构与签字制度跨卷不变'},
                   'ladder': levels},
        'edge': {'advantage': '他能读出签字上被压过的第二层笔迹。',
                 'origin': '仓库夜班十年练出来的手感。',
                 'growth': '三层：认笔迹、认印章、认改过的日期。',
                 'cost': '每次细看都要熬掉一夜的精力。',
                 'ceiling': '能读出工具痕迹，读不出签字人的真实身份。'},
        'protagonist': {'id': 'shen', 'name': '沈桐', 'identity': '夜班退件工，背着一笔自己的旧账。',
                        'desire': '查清退件来源并洗掉自己的违规记录。', 'limit': '不牵连无关同事。'},
        'relationships': {'relationships': ['同事互相依赖，却各自担心承担责任。',
                                            '主管是他的旧师父，也是最想压住这件事的人。']},
        'opposition': {'opposition': '第一卷对手是压签的主管，之后每卷抬一级：货站、承运商、写字楼里的签字链。',
                       'story_engine': '核对退件来源，追查签字责任。'},
        'payoff': {'plan': {'ways': ['核对签字打脸推责的人', '拿到被压的第二层笔迹', '把责任按证据落回原位'],
                            'cadence': '三到五章一次小兑现，章末留一个待查的封条。',
                            'hooks': '每卷中段翻出上一层签字链，卷尾落一次责任。'},
                   'ending': '退件来源公开，工人承担违规开箱的后果，压签链条被拆开。',
                   'theme': '责任怎样在人之间传递。',
                   'anchor': {'deliverable': '公开退件来源并把责任按证据落回原位。',
                              'deadline_chapter': str(min(6, limit))}},
        'title': {'title': '夜班退件：我能读出第二层笔迹'},
    }
    values['world']['architecture'] = {'space': '旧大陆与海上城邦靠季节航路相连，远洋断航使各地无法独自存续。', 'history': '上个时代的资源战争留下互保契约，失效的旧承诺正在引发新的饥荒。', 'civilizations': '内陆联邦依赖海上供给，城邦依赖内陆技术，双方为旧契约的解释权冲突。', 'conflict': '各方只能转移灾害而不能消除灾害，越成功自保就越破坏共同生存条件。', 'mystery': '共同灾害来自先民维持航路的选择，揭开真相后仍要决定谁承担修复代价。'}
    narrowed = {}
    for gate, value in values.items():
        if gate not in creation.gate_ids():
            continue
        owned = set(creation.value_fields(gate))
        narrowed[gate] = {key: copy.deepcopy(entry) for key, entry in value.items()
                          if key in owned}
    return narrowed


def _vary_option(value, path):
    """Change one leaf so the second option is a different direction, not a relabelled one."""
    target = value
    parts = path.split('.')
    for part in parts[:-1]:
        target = target[part]
    leaf = parts[-1]
    if isinstance(target[leaf], list):
        target[leaf] = target[leaf] + ['另一种落法：旧师父既护他也压他。']
    else:
        target[leaf] += '（另一种落法）'


def opening_options(work, book=None):
    """A worker-shaped result for one `opening_options` dispatch: two valid options for this gate.

    Every gate is answered by a cold worker except the structural one, so a driven test needs a
    receipt for whichever gate comes next; the option shape is the engine's own contract (distinct
    driver openings, two or three concrete scenes, no self-description of the creative method).
    """
    from novel_ledger import creation
    gate = ((work.get('payload') or {}).get('gate') or {}).get('id')
    values = opening_gate_values(book or {})
    require(gate in values and gate not in creation.SYSTEM_GATES.get(
        creation.opening_version((book or {}).get('creation') or {}), ()), 'opening_gate',
        '没有这一门的夹具值。', {'gate': gate, 'known': sorted(values)})
    first = values[gate]
    second = copy.deepcopy(first)
    _vary_option(second, _OPTION_ALT[gate])
    options = []
    for index, value in enumerate((first, second)):
        options.append({'id': 'AB'[index], 'title': '方案' + 'AB'[index],
                        'premise': '这一版具体怎么走：' + 'AB'[index] + '。',
                        'pitch': '看一眼就想翻开的那句话' + 'AB'[index] + '。',
                        'scene': [_OPTION_SCENES[index], _OPTION_SCENES[index + 1]],
                        'driver': _OPTION_DRIVERS[index], 'tradeoff': _OPTION_TRADEOFFS[index],
                        'fit_reason': '承接已选题材，把推进压在一件具体物件上' + 'AB'[index] + '。',
                        'value': value})
    return {'gate': gate, 'options': options}


def response(app, task_id=None, session=None, claim=None):
    """A protocol-valid receipt for whatever task is pending (or `task_id`)."""
    task = app.repo.task(task_id) if task_id else app.repo.pending()
    work = task['input']
    stage, n = work['stage'], work['chapter']
    session = session or 'test-' + uuid.uuid4().hex
    book = app.repo.load()
    payload = work.get('payload') or {}
    extra = tuple(payload.get('also') or ())
    if stage == 'opening_options':
        data = opening_options(work, book)
    elif stage == 'volume_outline':
        data = volume_outline_fixture(app, work)
    elif stage == 'chapter_outline':
        data = chapter_outline_fixture(app, work)
    elif stage == 'world_model':
        model = _opening_model(book)
        data = {**model, 'contract': _opening_contract(book, model)} if 'opening_contract' in extra else model
    elif stage == 'opening_contract':
        data = _opening_contract(book, book.get('world') or _opening_model(book))
    elif stage in ('write', 'repair', 'redesign'):
        data = template(stage, n, extra=extra, payload=payload,
                        tracking=work.get('narrative_tracking', False))
        prose = data['prose'] if isinstance(data.get('prose'), str) and data['prose'] else prose_stub(n)
        data.update(title='封条' + str(n), prose=prose, summary='沈桐要求核对退件来源。',
                    drift_check=drift_check_fixture(app, work, prose),
                    self_check='工程夹具：逐项按章纲比对，动作与证据均在正文中，无计划外变化。')
    else:
        data = template(stage, n, extra=extra, payload=payload,
                        tracking=work.get('narrative_tracking', False))
    result = {'schema': RESULT, 'task_id': task['id'], 'input_hash': task['input_hash'],
              'session': session, 'data': data}
    if claim:
        result['execution_claim'] = claim
    return result


def prose_stub(n):
    """A short chapter whose prose windows differ per chapter, so the duplication lint stays quiet."""
    mark = '（记%d）' % n
    return ('次日，沈桐把退回的箱子放在桌上，' + mark
            + '指给主管看封条上的签字。' + mark
            + '他翻开夜班登记册，找出自己经手的那一页，' + mark
            + '又把空白的责任栏推到主管面前，' + mark
            + '要求先核对退件人的名字再开箱。')


# --------------------------------------------------------------------------------------------------
# Shared fixtures other test modules import (never from each other)
# --------------------------------------------------------------------------------------------------

def tracked_contract(chapters=6, volumes=1):
    """The contract every tracked-book test writes: narrative tracking on, prose in the cheap band."""
    raw = contract(chapters=chapters, volumes=volumes)
    raw['narrative_tracking'] = True
    return raw


def plan_extras(plan):
    """A chapter-row-shaped fixture carrying the optional scene/pacing blocks.

    v2 keeps scenes and pacing as optional fields on the chapter outline row (the workbench reads
    them), so a long-form fixture can exercise the scene-dependency guards without inventing the
    whole outline chain. The passed fields win; scene ids default to `c<chapter>:s1`.
    """
    chapter = plan.get('chapter', 1)
    row = {
        'chapter': chapter,
        'synopsis': plan.get('goal') or '沈桐核对退件来源。',
        'plot': {'beat': '核对封条与签字。', 'nodes': [], 'threads': []},
        'resources': [], 'places': [], 'knowledge': [], 'characters': [],
        'clock': {'advance_days': 1}, 'enter': [], 'exit': [],
        'disclosures': [], 'world_refs': [], 'new_entities': [],
        'hook_refs': [], 'reader_refs': [], 'history_refs': [],
        'hooks': [],
        'scenes': [{'id': 'scene:fixture-%d-1' % chapter, 'label': '值班室', 'intent': '核对退件来源。',
                    'conflict': '主管以签字制度阻拦。', 'turn': '旧凭据暴露出签字矛盾。',
                    'reads': [], 'depends_on': [], 'present': [], 'speakers': [],
                    'dialogue_intents': [], 'reading_refs': [], 'story_time': '当夜',
                    'expands': []}],
        'pacing': {'role': 'pressure', 'pressure_in': '退件来源不明。',
                   'pressure_out': '有了核对方向，但关系更紧张。',
                   'emotional_aftereffect': '先处理被怀疑后的犹豫，再决定下一步。',
                   'recovery_purpose': '缓和争执，确认谁愿意合作。'},
        'dependency_coverage': 'partial',
    }
    row.update({key: value for key, value in plan.items() if key != 'chapter'})
    return row


def append_history(repo, first, last, prose_han=0, entity='shen'):
    """Populate `repo` with committed chapters that only history/material tests read.

    These are source records, not reviewed novel chapters: the point is a long immutable history
    without paying for the pipeline that would write it.
    """
    previous = repo.chapter('main', first - 1)['chain'] if first > 1 else 'genesis'
    for n in range(first, last + 1):
        prose = '工程第%d章：沈桐查出来源。' % n + '测' * prose_han
        events = [{'op': 'knowledge', 'entity': entity, 'topic': 'source',
                   'evidence': {'chapter': n, 'start': 0, 'quote': '工程第%d章' % n}}]
        row = {'n': n, 'title': '工程夹具', 'prose': repo.document(prose),
               'events': repo.document(events), 'plan': repo.document({}),
               'review': repo.document({}), 'state_hash': digest({'fixture': n}),
               'summary': '工程夹具：核查来源。', 'han': han_count(prose)}
        row['chain'] = facts.chain(previous, row, digest(repo.load()['contract']))
        repo.add_chapter('main', row)
        previous = row['chain']


_MASK = (1 << 64) - 1


def _mix(value):
    """A 64-bit integer mixer (splitmix-style): deterministic, never the same run twice by accident."""
    value = (value * 0x9E3779B97F4A7C15) & _MASK
    value ^= value >> 29
    value = (value * 0xBF58476D1CE4E5B9) & _MASK
    value ^= value >> 32
    value = (value * 0x94D049BB133111EB) & _MASK
    return value ^ (value >> 31)


# A short real sentence at the start of every padded chapter: the receipts' shared evidence anchor
# (`次日` is the time expression a clock event's evidence must quote) while the padded body keeps the
# 25-character windows chapter-unique. `他` keeps the narration in the third person that the default
# fixtures assume; the filler never draws a first/second-person marker.
PADDED_SEED = '次日，他把退回的箱子放在桌上，'
_PERSON_MARKERS = '我咱俺你他她它'


def _padded_char(seed, step):
    """One CJK character for the filler, never a narration-person marker."""
    base = _mix(seed + step * 1009)
    value = chr(0x4E00 + base % 1800)
    bump = 0
    while value in _PERSON_MARKERS:
        bump += 1
        value = chr(0x4E00 + (base + bump * 31) % 1800)
    return value


def padded_prose(chapter, need_han):
    """Deterministic filler prose of at least `need_han` 汉字, safe under the mechanical checks.

    A long-tier chapter needs a real minimum length, and every filler style has a trap: repeating one
    sentence blows the style proxies' in-chapter 4-gram repetition share, while a small word pool
    collides too often for the cross-chapter duplication lint. Characters drawn from a wide CJK range
    by a per-chapter hash are unique four characters at a time, stable across runs (a flaky fixture
    would be worse than a wrong one), and the same body shape for every chapter, so the anchor
    comparison has nothing to compare against. The seed sentence is short enough (well under 25
    characters) that every duplication window still contains hash-derived characters.
    """
    need = max(0, int(need_han))
    prose = PADDED_SEED
    index = 0
    while han_count(prose) < need:
        seed = index * 101 + int(chapter) * 10007
        prose += ''.join(_padded_char(seed, step) for step in range(11)) + '。'
        index += 1
    return prose


def long_prose(n, count=140):
    """A chapter-length prose stub: long enough for the widest tier, clean under the checks.

    The widest contract minimum is 3000 汉字, so the default fills that with `padded_prose`; the
    chapter number seeds the generator, so two chapters never share a 25-character window.
    """
    return padded_prose(n, count * 23)


# --------------------------------------------------------------------------------------------------
# Dispatch invariants and the driver
# --------------------------------------------------------------------------------------------------

def required_material(work):
    """The required records whose content is not already carried by an earlier required name.

    Every dispatch must satisfy this: a worker should never be charged twice for one fact, and two
    names holding byte-identical material also hide which one is authoritative.
    """
    seen, kept = set(), []
    for name in work['required']:
        ident = work['records'][name]
        if ident not in seen:
            seen.add(ident)
            kept.append(name)
    return kept


def check_dispatch(work):
    """Two invariants every frozen dispatch must satisfy, checked wherever a flow is driven."""
    if len(required_material(work)) != len(work['required']):
        raise AssertionError('必读记录里有内容完全相同的两份：' + ','.join(work['required']))
    undeclared = context.undeclared_material(work['stage'], work['required'])
    if undeclared:
        raise AssertionError('阶段 %s 的必读未在 context.STAGE_MATERIAL 里声明：%s'
                             % (work['stage'], ','.join(undeclared)))


def drive(app, owner=None, until=None, limit=300):
    """Advance the book until a boundary or the named stage, submitting fixture receipts.

    The v2 pipeline stops on author decisions and on an outline-only delivery; every other stop is a
    dispatch, so this loop is the whole protocol: pick the first board option, approve the pilot,
    file the fixture receipt, repeat. When a controller lease is held (`run`), the holder is read
    from the store so a test does not have to thread the owner through every call.
    """
    if owner is None:
        lease = app.repo.get(store_keys.CONTROLLER)
        owner = (lease or {}).get('owner')
    for _ in range(limit):
        handoff = app.advance(owner=owner)
        action = handoff['action']
        if action == 'await_choice':
            board = handoff.get('board') or {}
            options = board.get('options') or []
            if not options:                 # a structural gate always carries its board
                raise AssertionError('选择门没有可选项：' + str(board.get('gate')))
            app.opening_choice(options[0]['id'], board['hash'],
                               '工程夹具作者选择当前板面第一案。', owner)
            continue
        if action == 'await_author':
            app.approve(handoff['prose_hash'], '工程夹具作者明确认可当前版本。', owner)
            continue
        if action == 'await_volume_confirm':
            app.confirm_volume(handoff['volumes_hash'], '工程夹具作者认可当前卷纲。', owner)
            continue
        if action != 'task_ready':
            return handoff
        if until and handoff['task']['stage'] == until:
            return handoff
        check_dispatch(app.repo.pending()['input'])
        app.submit(response(app))
    raise AssertionError('工程流程没有在有限步骤内停止')
