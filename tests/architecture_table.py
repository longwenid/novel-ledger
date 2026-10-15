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
    'store_keys': set(),
    'stages': {'contracts'},
    'ports': {'contracts'},
    'book_state': {'contracts'},
    'craft': {'contracts'},
    'creation': {'contracts'},
    'design_queries': set(),
    'editorial': {'contracts'},
    'entities': {'contracts'},
    'evidence': {'contracts'},
    'facts': {'contracts', 'entities', 'evidence', 'narrative', 'spatial'},
    'narrative': {'contracts'},
    'planning': {'contracts', 'entities', 'narrative', 'craft', 'story_memory'},
    'quality': {'contracts', 'evidence'},
    'result_templates': {'contracts', 'world', 'scopes', 'editorial', 'narrative', 'stages'},
    'revision_impact': {'contracts', 'story_memory'},
    'scopes': {'contracts'},
    'spatial': {'contracts'},
    'story_memory': {'contracts'},
    'understanding': {'contracts'},
    'world': {'contracts'},
    'briefs': {'contracts', 'creation', 'stages'},
    'workflow': {'contracts', 'creation', 'facts', 'narrative', 'planning', 'quality',
                 'scopes', 'world', 'craft', 'editorial', 'understanding',
                 'design_queries', 'evidence'},
    'application': {'contracts', 'ports', 'store_keys', 'creation', 'facts', 'narrative', 'planning',
                    'quality', 'workflow', 'world', 'craft', 'editorial',
                    'story_memory', 'understanding', 'revision_service', 'contract_activation'},
    'revision_service': {'contracts', 'ports', 'store_keys', 'editorial', 'facts', 'narrative', 'revision_impact',
                         'story_memory', 'understanding', 'workflow'},
    'contract_activation': {'contracts', 'ports', 'store_keys', 'workflow'},
    'context': {'contracts', 'ports', 'briefs', 'creation', 'narrative', 'scopes',
                'world', 'editorial', 'story_memory', 'understanding', 'planning',
                'design_queries'},
    'publication': {'ports'},
    'workspace': {'contracts'},
    'delivery': {'contracts', 'ports', 'store_keys', 'result_templates', 'publication', 'workspace'},
    'bookpage': {'contracts', 'ports', 'publication', 'workspace', 'planning',
                 'world', 'creation', 'understanding', 'briefs'},
    'presentation': {'ports', 'bookpage', 'delivery', 'workspace'},
    'sqlite_store': {'contracts', 'book_state', 'store_keys'},
    'host': {'contracts', 'ports'},
    'bootstrap': {'contracts', 'application', 'context', 'presentation', 'sqlite_store',
                  'workspace', 'workflow', 'host', 'delivery', 'bookpage'},
    'novel': {'contracts', 'bootstrap'},
}

# These modules can evaluate values and invoke injected capabilities, but cannot
# discover files, databases, environment variables, processes or dynamic code.
CORE_EXTERNAL = {
    '__init__': set(),
    'contracts': {'__future__', 'copy', 'hashlib', 'json', 'dataclasses', 'typing'},
    'store_keys': {'__future__'},
    'stages': {'__future__', 'contracts'},
    'ports': {'__future__', 'typing'},
    'book_state': {'__future__', 'copy'},
    'craft': {'__future__', 'copy'},
    'creation': {'__future__', 'copy'},
    'design_queries': {'__future__'},
    'editorial': {'__future__', 'copy'},
    'entities': {'__future__', 'copy'},
    'evidence': {'__future__'},
    'facts': {'__future__', 'copy', 'decimal'},
    'narrative': {'__future__', 'copy'},
    'planning': {'__future__', 'copy', 'math'},
    'quality': {'__future__', 'copy'},
    'result_templates': {'__future__'},
    'revision_impact': {'__future__'},
    'scopes': {'__future__'},
    'spatial': {'__future__', 'copy'},
    'story_memory': {'__future__', 'copy'},
    'understanding': {'__future__', 'copy'},
    'world': {'__future__', 'copy'},
    'briefs': {'__future__'},
    'workflow': {'__future__', 'copy'},
    'application': {'__future__', 'copy'},
    'revision_service': {'__future__', 'copy'},
    'contract_activation': {'__future__', 'copy'},
    'context': {'__future__', 'copy', 'json'},
    'publication': {'__future__'},
}

# Every remaining module is an adapter by explicit decision: it may perform I/O,
# discover resources or start processes, but only through the injected surface.
ADAPTERS = {
    'workspace', 'delivery', 'bookpage', 'presentation',
    'sqlite_store', 'host', 'bootstrap', 'novel',
}

FORBIDDEN_CORE_NAMES = {'open', '__import__', 'eval', 'exec', 'Path',
                        'getattr', '__builtins__', '__globals__'}


def allowed_edges():
    """Return the allowed edge set as (caller, dependency) pairs."""
    return {(name, dependency) for name, dependencies in ALLOWED.items()
            for dependency in dependencies}
