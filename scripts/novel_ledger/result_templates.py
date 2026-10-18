"""Blank worker results. Presentation shapes do not participate in domain decisions."""
from __future__ import annotations

from .contracts import CHECKS_VERSION, checks_for, contract_skeleton
from .world import SECTIONS
from . import stages
from . import scopes, editorial


def template(stage, chapter, sources, obligations=(), extra=(), version=CHECKS_VERSION, payload=None, tracking=False):
    """The blank result for a stage. `extra` carries stages a combined dispatch also answers."""
    stages.require_stage(stage)
    def review(ids, obs=(), challenges=()):
        return {'verdict': '', 'checks_version': version,
                'checks': [dict(id=ident, result='', reason='', evidence=[],
                **({'challenge': {'risk': '', 'disposition': '', 'reason': '', 'evidence': {}}} if ident in challenges else {})) for ident in ids],
                'findings': [], 'obligations': [{'id': o['id'], 'result': '', 'reason': '', 'evidence': []} for o in obs]}
    if stage == 'chapter_review':
        facts = review(checks_for(version, 'fact'), [o for o in obligations if o['category'] == 'facts'], ('time',))
        facts.update(events=[], summary='', elapsed_days=None)
        reader = review(checks_for(version, 'reader'), [o for o in obligations if o['category'] == 'reader'], ('language',))
        if tracking:
            from .narrative import PACE_FIELDS
            reader['pacing'] = {**{k: '' for k in PACE_FIELDS}, 'evidence': {}}
        return {'facts': facts, 'reader': reader,
                **({'understanding': []} if (payload or {}).get('understanding') else {}),
                **({'alignment': {'action': '', 'reason': '', 'realizations': [{'node': n, 'after': '', 'reason': '', 'evidence': {},
                     **({'fulfilled_criteria': [{'id': c['id'], 'actual_effect': '', 'evidence': {}} for c in payload['node_criteria'][n]], 'prior_criteria': []}
                        if (payload or {}).get('node_criteria', {}).get(n) else {})}
                     for n in (payload or {}).get('node_ids', [])]}} if (payload or {}).get('editorial') else {})}
    if stage in ('design_review', 'outline_review', 'contract_review', 'alignment_review'):
        result = review(checks_for(version, 'design'))
        if (payload or {}).get('author_question_hash'):
            result['blocked_resolution'] = {'question_hash': payload['author_question_hash'], 'result': '', 'reason': ''}
        return result
    if stage == 'world_review':
        return review(checks_for(version, 'world'))
    if stage == 'opening_options':
        return {'gate': '', 'options': []}
    if stage == 'world_model':
        skeleton = {'selection_hash': '', 'premise': '', 'story_capacity': '',
                    **{k: [{'id': '', **{field: '' for field in fields}, 'links': []}] for k, fields in SECTIONS.items()}}
        if extra and 'opening_contract' in extra:
            # One dispatch drafts the world and the contract it implies: the contract is a reading
            # of selections plus that world, so it belongs in the same cold session.
            return {**skeleton, 'contract': contract_skeleton()}
        return skeleton
    if stage == 'opening_contract':
        return contract_skeleton()
    if stage in ('scope_review', 'scope_synthesis'):
        result = review(checks_for(version, 'long'))
        if (payload or {}).get('understanding'):
            result['understanding'] = []
        children = (payload or {}).get('children', [])
        result['coverage'] = [{'part_id': ident, 'reason': '', 'evidence': {}} for ident in children] if children else [{'chapter': n, 'reason': '', 'evidence': {}} for n in sources]
        if (payload or {}).get('review_tree'):
            result['handoff'] = {**{k: '' for k in scopes.HANDOFF_FIELDS}, 'evidence': []}
        if (payload or {}).get('closure'):
            result['closure'] = editorial.closure_template(payload['closure'])
        if (payload or {}).get('remedies'):
            result['remedy_review'] = [{**{k: r[k] for k in ('case_id', 'round_id')}, 'result': '', 'reason': '', 'evidence': {}}
                                       for r in payload['remedies']]
        return result
    if stage == 'revision_review':
        return {'reader': review(checks_for(version, 'reader'),
                                [o for o in obligations if o['category'] == 'reader'], ('language',)),
                **({'understanding': []} if (payload or {}).get('understanding') else {})}
    if stage in ('write', 'repair', 'redesign'):
        return {'title': '', 'prose': '', 'summary': '', 'self_check': ''}
    if stage == 'profiles':
        return {'profiles': []}
    if stage == 'alignment_plan':
        return {'reason': '', 'plan': {}, 'designs': []}
    if stage == 'plan':
        return {'plans': []}
    if stage == 'volume_plan' and (payload or {}).get('volume_outline'):
        policy = payload['volume_outline']
        return {'intent': '', 'ending_conditions': '', 'nodes': [], **({'threads': []} if tracking else {}),
                'world_hash': policy['world_hash'],
                'brainstorm': [{'id': 'A', 'premise': '', 'tradeoff': '', 'world_refs': []},
                               {'id': 'B', 'premise': '', 'tradeoff': '', 'world_refs': []}],
                'selected': '', 'selection_reason': ''}
    if stage == 'volume_outline':
        policy = payload['volume_outline']
        return {'world_hash': policy['world_hash'],
                'chapters': [{'chapter': n, 'synopsis': '', 'world_refs': [], 'node_ids': []}
                             for n in range(policy['first'], policy['last'] + 1)]}
    if stage == 'book_plan' and 'volume_outline' in (extra or ()):
        # The merged single-volume dispatch: the skeleton plus the volume's chapter outlines
        # ride in one receipt, the way the world dispatch carries its contract.
        policy = payload['volume_outline']
        return {'intent': '', 'ending_conditions': '', 'nodes': [], **({'threads': []} if tracking else {}),
                'world_hash': policy['world_hash'],
                'chapters': [{'chapter': n, 'synopsis': '', 'world_refs': [], 'node_ids': []}
                             for n in range(policy['first'], policy['last'] + 1)]}
    return {'intent': '', 'ending_conditions': '', 'nodes': [], **({'threads': []} if tracking else {})}
