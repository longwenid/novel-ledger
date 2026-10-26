"""Activate a reviewed author contract within the application's transaction."""
from __future__ import annotations

import copy
from .contracts import digest
from .ports import Repository
from .verification import VerificationService
from . import store_keys, workflow


class ContractActivation:
    def __init__(self, repo: Repository):
        self.repo = repo

    def activate(self, old):
        proposal = old['pending_contract']
        rows = self.repo.headers(old['branch'])
        self.repo.put(store_keys.branch_book(old['branch']), self.repo.get(store_keys.AMENDMENT_BASE, old))
        book = workflow.new_book(proposal['data'], proposal['source'])
        book['lexical_policy'] = copy.deepcopy(old['lexical_policy'])
        # The volume gate across a re-contract: the author's structural direction and the audit of
        # what was confirmed travel with the book (the lexical-policy treatment); the staged design
        # does not — the volume division may have changed, so it is dropped and journalled, and the
        # round/refusal counters reset with it.
        if old.get('structure_blueprint'):
            book['structure_blueprint'] = copy.deepcopy(old['structure_blueprint'])
        confirmed = (old.get('volume_gate') or {}).get('confirmed')
        if confirmed:
            book['volume_gate']['confirmed'] = copy.deepcopy(confirmed)
        if old.get('pending_design'):
            self.repo.record('volume_gate_reset', {
                'dropped_volumes': list(old['pending_design'].get('volume_ids') or []),
                'reason': '改约重建：卷划分可能已变，暂存卷纲不随行，需重新设计并过认可门。'})
        if old.get('creation'):
            # An answered opening stays answered: the closed choices are what the new contract is
            # an amendment of, so they travel with it whatever phase they were in.
            book['creation'] = copy.deepcopy(old['creation'])
            book['creation']['phase'] = 'ready'
            book['opening_world_only'] = True
        # A re-contract keeps the world that was independently verified. Keying this on the opening
        # phase dropped it on every re-contract after the first activation (which moves that phase to
        # `ready`): a real second amendment silently continued without the world, and the design
        # stages after it bound `world_hash: null` with empty `world_refs`.
        if old.get('world'):
            book['world'] = copy.deepcopy(old['world'])
            book['opening_world_only'] = True
        book['feedback'] = old['feedback'] + [proposal['source']]
        if old.get('repair_cases'):
            book['repair_cases'] = copy.deepcopy(old['repair_cases'])
        if old.get('author_decision_history'):
            book['author_decision_history'] = copy.deepcopy(old['author_decision_history'])
        if old.get('author_block'):
            # An unanswered question must not be lost by re-contracting: it stays pending.
            book['author_block'] = copy.deepcopy(old['author_block'])
        if old.get('remedy_exhausted'):
            book['remedy_exhausted'] = copy.deepcopy(old['remedy_exhausted'])
        book['carry_findings'] = copy.deepcopy(old.get('carry_findings', []))
        if old['draft']:
            # An unsaved candidate demotes to prior_candidate so a fresh write round can reuse
            # its prose instead of losing it.
            book['carry_findings'].extend(copy.deepcopy(old['draft'].get('findings', [])))
            book['carry_findings'] = list({digest(row): row for row in book['carry_findings']}.values())
            book['prior_candidate'] = {k: old['draft'][k] for k in ('chapter', 'title', 'prose')}
        book.update(rework=copy.deepcopy(old['rework']), revision=old['revision'] + 1,
                    target=min(old['target'], book['contract']['volumes'][-1]['end']), finish=old['finish'])
        if rows:
            book['branch'] = self.repo.fork(old['branch'], 1)
            last = min(rows[-1]['n'], book['contract']['volumes'][-1]['end'])
            book.update(target=last, finish=False,
                        revision_run={'parent': old['branch'], 'first': 1, 'last': last, 'reason': proposal['source'],
                                      'target': min(old['target'], book['contract']['volumes'][-1]['end']), 'finish': old['finish']})
        else:
            book['branch'] = old['branch']
            # Replanning does not create new editorial effort. An unanswered budget
            # decision stays actionable; its exact candidate survives the new contract.
            if old.get('draft'):
                book['draft'] = copy.deepcopy(old['draft'])
                book['draft']['stage'] = workflow.draft_exhaustion_stage(book['rework'].get(str(old['draft']['chapter']), {}))
                if book['draft']['stage'] == 'exhausted':
                    book['status'] = 'paused'
                    book['pause_reason'] = old.get('pause_reason') or '原修复额度已经耗尽，须作者决定。'
        if book.get('author_block'):
            book['status'] = 'paused'
            book['pause_reason'] = book['author_block']['question']
        VerificationService(self.repo).head(book)
        self.repo.save(book)
        self.repo.record('contract_activate', {'hash': digest(book['contract']), 'source': proposal['source']})
        return book
