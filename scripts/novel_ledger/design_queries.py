"""Read-only design queries shared by scheduling and context assembly."""
from __future__ import annotations

# A dispatch reads a bounded causal neighbourhood, never the whole ancestry: an unbounded
# walk grows the material with book length and exhausts the interpreter stack on a long
# dependency chain (a thousand-node chain used to abort dispatch with RecursionError).
TRACKED_DEPTH = 1
BASIC_DEPTH = 6
NODE_LIMIT = 24


def node_map(designs):
    """Index nodes from design values without a workflow or full-book dependency."""
    return {node['id']: node for design in designs.values() for node in design['nodes']}


def frontier(nodes, seeds, depth=BASIC_DEPTH, limit=NODE_LIMIT):
    """Seeds plus their ancestors, breadth first and bounded.

    Iterative on purpose: recursion was the failure mode, and a bounded walk keeps the
    dispatch material independent of how deep the book's causal chain has grown.
    """
    selected, seen, pending = [], set(), [(ident, 0) for ident in seeds]
    while pending and len(selected) < limit:
        ident, level = pending.pop(0)
        if ident in seen:
            continue
        seen.add(ident)
        selected.append(ident)
        if level >= depth:
            continue
        pending.extend((parent, level + 1) for parent in nodes[ident].get('depends_on', ()))
    return selected
