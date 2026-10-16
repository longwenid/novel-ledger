"""Activate a reviewed author contract within the application's transaction."""
from __future__ import annotations

import copy
from .contracts import digest
from .ports import Repository
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
        book['contract_review'] = {'producer': proposal['producer'],
                                   'reviewer': old.get('pending_contract_reviewer', proposal['producer'])}
        if old.get('creation') and old['creation']['phase'] == 'contract':
            book['creation'] = copy.deepcopy(old['creation'])
            book['creation']['phase'] = 'ready'
            book['world'] = copy.deepcopy(old['world'])
            book['world_review'] = copy.deepcopy(old['world_review'])
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
        book['carry_findings'] = copy.deepcopy(old.get('carry_findings', [])) + copy.deepcopy(old.get('scope_findings', []))
        if old['draft']:
            book['carry_findings'].extend(copy.deepcopy(old['draft'].get('findings', [])))
            book['prior_candidate'] = {k: old['draft'][k] for k in ('chapter', 'title', 'prose')}
        book.update(rework=old['rework'], revision=old['revision'] + 1,
                    target=min(old['target'], book['contract']['volumes'][-1]['end']), finish=old['finish'])
        if rows:
            book['branch'] = self.repo.fork(old['branch'], 1)
            last = min(rows[-1]['n'], book['contract']['volumes'][-1]['end'])
            book.update(target=last, finish=False,
                        revision_run={'parent': old['branch'], 'first': 1, 'last': last, 'reason': proposal['source'],
                                      'target': min(old['target'], book['contract']['volumes'][-1]['end']), 'finish': old['finish']})
        else:
            book['branch'] = old['branch']
        self.repo.save(book)
        self.repo.record('contract_activate', {'hash': digest(book['contract']), 'source': proposal['source']})
        return book
