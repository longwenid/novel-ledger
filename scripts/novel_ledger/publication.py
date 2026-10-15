"""Read-only publication queries shared by derived views and exports."""
from __future__ import annotations

from .ports import PublicationReader


def publication(repo: PublicationReader):
    book = repo.load()
    if book['status'] == 'completed' and book.get('completion_snapshot'):
        snapshot = repo.read_document(book['completion_snapshot'])
        frozen = snapshot.get('book', book)
        # Older snapshots predate the final status update. Content remains frozen;
        # only completion metadata can be filled from the live book.
        frozen = {**frozen, 'status': 'completed'}
        if 'completed_at' not in frozen and book.get('completed_at') is not None:
            frozen['completed_at'] = book['completed_at']
        return frozen, snapshot['chapters']
    return book, repo.headers(book['branch'])
