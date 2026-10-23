"""Execution observations and controller handoffs; never infer a live model from a lease."""
from __future__ import annotations


CONTINUE_ACTIONS = {
    'task_ready': 'dispatch_worker',
    'wait_for_submit': 'supervise_worker',
    'wait_for_batch': 'supervise_worker',
    'review_required': 'dispatch_observer',
    'review_complete': 'resubmit_reviewed_candidate',
    'resync': 'advance',
    'revision_ready': 'process_authorized_revision',
    'ready_to_complete': 'complete',
    'completed': 'deliver',
}


def controller_handoff(response):
    action = response.get('action')
    proceed = action in CONTINUE_ACTIONS
    return {**response, 'controller': {
        'must_continue': proceed,
        'action': CONTINUE_ACTIONS.get(action, 'handle_boundary'),
        'stop_reason': None if proceed else action,
        'worker_finished_ends_controller': False,
    }}


def presence(lease, delivered, now):
    """Authenticated activity is observable; current process liveness is host-owned."""
    registered = bool(lease)
    valid = bool(registered and lease['until'] > now)
    observed = bool(delivered or (lease or {}).get('activity_at'))
    return {'identity_registered': registered, 'lease_valid': valid,
            'lease_until': lease.get('until') if lease else None,
            'activity_observed': observed, 'worker_running': None,
            'host_identity_verified': bool(((lease or {}).get('provenance') or {}).get('verified')),
            'phase': ('lease_expired' if registered and not valid else
                      'activity_observed' if observed else
                      'await_worker_start' if registered else 'await_worker_identity')}


def submission_handoff(boundary, needs_author):
    return {'actor': 'author' if needs_author else 'worker' if boundary == 'continue' else 'controller',
            'action': 'answer' if needs_author else 'worker-next' if boundary == 'continue' else 'advance',
            'must_continue': not needs_author, 'worker_finished_ends_controller': False}
