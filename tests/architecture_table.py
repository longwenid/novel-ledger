"""Single source for executable layer boundaries; imported by architecture tests.

Keeping the table here (rather than inside one test module) prevents a second,
narrower copy from drifting: every module is either a core rule module with an
external-import whitelist or an explicit adapter, and nothing may be missing
from both sets.
"""

# A new module or dependency requires an explicit architectural decision here.
# In particular, two modules can remain acyclic while still crossing a layer.
ALLOWED = {
    '__init__': set(),
    'contracts': set(),
    # catalog is the content menu layer the opening boards and briefs render (genre catalog,
    # lenses, volume turns, opening directions, cliche watch lists, board copy): pure data with
    # no dependencies, so the protocol in contracts stays free of creative content.
    'catalog': set(),
    'store_keys': set(),
    'stages': {'contracts'},
    'envelope': {'contracts'},
    'ports': {'contracts'},
    'book_state': {'contracts'},
    'craft': {'contracts'},
    # lint judges mechanical prose defects (verbatim reuse, quote family, foreign residue) against
    # text the caller supplies; it is pure arithmetic on strings, like book_state's invariants.
    'lint': {'contracts'},
    # ledger validates the optional structured account blocks a design or plan may declare; pure
    # arithmetic over declared rows, same layer as lint.
    'ledger': {'contracts'},
    'creation': {'contracts', 'catalog'},
    'design_queries': set(),
    'editorial': {'contracts'},
    'entities': {'contracts'},
    'evidence': {'contracts'},
    'facts': {'contracts', 'entities', 'evidence', 'narrative', 'spatial'},
    'narrative': {'contracts'},
    'planning': {'contracts', 'entities', 'narrative', 'craft', 'story_memory', 'drift_validation'},
    # style judges mechanical prose shape (sentence/paragraph rhythm, dialogue share, in-chapter
    # repetition, narration person) against the approved first chapter: same layer as lint, pure
    # arithmetic on strings, and the only half of literary quality a program can actually check.
    'style': {'contracts'},
    # The drift family is one judgment split by phase: `drift` keeps the shared vocabulary
    # (field tables, world/projection helpers, chapter deltas, the reducer both phases walk,
    # plan_rows); `drift_simulation` walks the design-time state chain (registries, apply,
    # closure, and the event builders both phases emit); `drift_validation` mechanically
    # validates volume/chapter outlines before any prose exists; `drift_reconcile` settles
    # the writer's drift_check at submission. All read the same tables the checks do (world
    # sections, nodes, spatial rules), which is what lets a whole volume be checked before
    # a word is written.
    'drift': {'contracts', 'facts', 'narrative', 'spatial', 'world'},
    'drift_simulation': {'contracts', 'drift', 'evidence', 'facts', 'world'},
    'drift_validation': {'contracts', 'drift', 'drift_simulation', 'entities', 'world'},
    'drift_reconcile': {'contracts', 'drift', 'drift_simulation', 'evidence', 'world'},
    'result_templates': {'contracts', 'world', 'editorial', 'narrative', 'stages', 'drift'},
    'revision_impact': {'contracts', 'story_memory'},
    'spatial': {'contracts'},
    'story_memory': {'contracts'},
    'understanding': {'contracts'},
    'world': {'contracts'},
    # briefs renders what a stage must produce, so it reads the same declarations the checks do:
    # the stage registry, the world section table and the drift field table. Keeping the
    # requirement and its check on one declaration is the point — a brief asking for a small world
    # while the validator demanded ten domains is what a real micro project paid four repair
    # rounds for.
    'briefs': {'contracts', 'catalog', 'creation', 'stages', 'world', 'drift'},
    'workflow': {'contracts', 'creation', 'drift', 'drift_simulation', 'drift_reconcile', 'facts', 'narrative', 'planning',
                 'world', 'craft', 'editorial', 'understanding',
                 'design_queries', 'evidence', 'lint', 'ledger', 'style'},
    # book_state declares the four-partition field ownership and the invariants between those fields,
    # so the application reads it to check the state it owns (the same way it reads store_keys for the
    # key space). book_state stays a pure declaration module: it imports nothing but contracts.
    'application': {'contracts', 'ports', 'store_keys', 'book_state', 'creation', 'facts', 'narrative', 'planning',
                    'workflow', 'world', 'craft', 'editorial',
                    'story_memory', 'understanding', 'revision_service', 'contract_activation', 'opening_service', 'verification', 'lint', 'writing_service'},
    'writing_service': {'contracts', 'ports', 'store_keys', 'editorial', 'planning', 'workflow'},
    'revision_service': {'contracts', 'ports', 'store_keys', 'editorial', 'facts', 'narrative', 'revision_impact',
                         'story_memory', 'understanding', 'workflow', 'verification'},
    'contract_activation': {'contracts', 'ports', 'store_keys', 'workflow', 'verification'},
    'opening_service': {'contracts', 'ports', 'creation', 'planning'},
    'context': {'contracts', 'ports', 'envelope', 'briefs', 'creation', 'narrative', 'drift',
                'world', 'editorial', 'story_memory', 'understanding', 'planning', 'style',
                'design_queries'},
    'publication': {'ports', 'verification'},
    'verification': {'contracts', 'ports', 'book_state', 'creation', 'drift_reconcile', 'editorial', 'facts', 'lint', 'narrative', 'planning', 'understanding', 'world'},
    'workspace': {'contracts'},
    'delivery': {'contracts', 'catalog', 'ports', 'store_keys', 'envelope', 'result_templates', 'publication', 'workspace'},
    'bookpage': {'contracts', 'catalog', 'ports', 'publication', 'workspace', 'planning',
                 'world', 'creation', 'understanding', 'briefs'},
    'presentation': {'ports', 'bookpage', 'delivery', 'workspace'},
    'sqlite_store': {'contracts', 'book_state', 'store_keys'},
    'host': {'contracts', 'ports'},
    # unattended owns the wait between dispatch and external submission; like host it sees only
    # the public application protocol, so the loop stays an adapter even though it runs long.
    'unattended': {'contracts', 'ports'},
    'bootstrap': {'contracts', 'application', 'context', 'presentation', 'sqlite_store',
                  'workspace', 'workflow', 'host', 'unattended', 'delivery', 'bookpage'},
    'novel': {'contracts', 'bootstrap'},
}

# These modules can evaluate values and invoke injected capabilities, but cannot
# discover files, databases, environment variables, processes or dynamic code.
CORE_EXTERNAL = {
    '__init__': set(),
    'contracts': {'__future__', 'copy', 'hashlib', 'json', 'dataclasses', 'typing'},
    'store_keys': {'__future__'},
    'stages': {'__future__', 'contracts'},
    'envelope': {'__future__', 'contracts'},
    'ports': {'__future__', 'typing'},
    'book_state': {'__future__', 'copy'},
    'craft': {'__future__', 'copy'},
    'lint': {'__future__', 're'},
    'ledger': {'__future__'},
    'creation': {'__future__', 'copy'},
    'catalog': set(),
    'design_queries': {'__future__'},
    'editorial': {'__future__', 'copy'},
    'entities': {'__future__', 'copy'},
    'evidence': {'__future__'},
    'facts': {'__future__', 'copy', 'decimal'},
    'narrative': {'__future__', 'copy', 'decimal'},
    'planning': {'__future__', 'copy', 'math'},
    'drift': {'__future__', 'copy', 'decimal'},
    'drift_simulation': {'__future__', 'copy', 'decimal'},
    'drift_validation': {'__future__', 'copy'},
    'drift_reconcile': {'__future__', 'copy'},
    'style': {'__future__', 're'},
    'result_templates': {'__future__'},
    'revision_impact': {'__future__'},
    'spatial': {'__future__', 'copy'},
    'story_memory': {'__future__', 'copy'},
    'understanding': {'__future__', 'copy'},
    'world': {'__future__', 'copy'},
    'briefs': {'__future__'},
    'workflow': {'__future__', 'copy'},
    'application': {'__future__', 'copy'},
    'writing_service': {'__future__'},
    'revision_service': {'__future__', 'copy'},
    'contract_activation': {'__future__', 'copy'},
    'opening_service': {'__future__'},
    'context': {'__future__', 'copy', 'json'},
    'publication': {'__future__'},
    'verification': {'__future__'},
}

# Every remaining module is an adapter by explicit decision: it may perform I/O,
# discover resources or start processes, but only through the injected surface.
ADAPTERS = {
    'workspace', 'delivery', 'bookpage', 'presentation',
    'sqlite_store', 'host', 'unattended', 'bootstrap', 'novel',
}

FORBIDDEN_CORE_NAMES = {'open', '__import__', 'eval', 'exec', 'Path',
                        'getattr', '__builtins__', '__globals__'}


def allowed_edges():
    """Return the allowed edge set as (caller, dependency) pairs."""
    return {(name, dependency) for name, dependencies in ALLOWED.items()
            for dependency in dependencies}
