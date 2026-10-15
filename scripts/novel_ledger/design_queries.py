"""Read-only design queries shared by scheduling and context assembly."""
from __future__ import annotations


def node_map(designs):
    """Index nodes from design values without a workflow or full-book dependency."""
    return {node['id']: node for design in designs.values() for node in design['nodes']}
