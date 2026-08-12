"""Lifecycle-state layer for the Execution Engine.

The spec requires a coarse anti-reprocess status per job:
    NEW, ANALYZED, REVIEW_PENDING, APPLIED, SKIPPED, FAILED, EXPIRED

The legacy database uses a finer `applications.status` (DRAFT_READY_EMAIL,
EMAIL_SENT, PORTAL_SUBMITTED, REVIEW_CV, ...) that the Gmail/portal delivery
flow depends on. Rather than rename those, we map them ADDITIVELY to the coarse
lifecycle states below and store the result in `applications.lifecycle_state`.
The original `status` is never mutated by this layer.
"""

from __future__ import annotations

# Coarse lifecycle states (the public contract from the spec).
NEW = "NEW"
ANALYZED = "ANALYZED"
REVIEW_PENDING = "REVIEW_PENDING"
APPLIED = "APPLIED"
SKIPPED = "SKIPPED"
FAILED = "FAILED"
EXPIRED = "EXPIRED"

LIFECYCLE_STATES = (
    NEW,
    ANALYZED,
    REVIEW_PENDING,
    APPLIED,
    SKIPPED,
    FAILED,
    EXPIRED,
)

# States that mean "work is done — do not analyse or rebuild this job again".
TERMINAL_STATES = frozenset({APPLIED, SKIPPED, EXPIRED})

# Fine-grained applications.status → coarse lifecycle state.
_STATUS_MAP: dict[str, str] = {
    # Sent / submitted → APPLIED
    "EMAIL_SENT": APPLIED,
    "PORTAL_SUBMITTED": APPLIED,
    "APPLIED": APPLIED,
    "EXPIRED": EXPIRED,
    # Draft built and waiting for a human → REVIEW_PENDING
    "DRAFT_READY_EMAIL": REVIEW_PENDING,
    "DRAFT_READY_PORTAL": REVIEW_PENDING,
    "DRAFT_READY": REVIEW_PENDING,
    "REVIEW_CV": REVIEW_PENDING,
    "REVIEW_MULTIPLE_CV": REVIEW_PENDING,
    "REVIEW_DOCUMENT": REVIEW_PENDING,
    "REVIEW_ATTACHMENT_SIZE": REVIEW_PENDING,
    "PENDING_APPROVAL": REVIEW_PENDING,
    "GMAIL_DRAFT_CREATED": REVIEW_PENDING,
    "EMAIL_APPROVAL_PENDING": REVIEW_PENDING,
    "PORTAL_REVIEW_REQUIRED": REVIEW_PENDING,
    "REVIEW": REVIEW_PENDING,
    # Blocked / errored → FAILED
    "BLOCKED_CV_MISSING": FAILED,
    "BLOCKED_CV_LIBRARY": FAILED,
    "BLOCKED_INVALID_FILE": FAILED,
    "BLOCKED_DESTINATION": FAILED,
    "SEND_FAILED": FAILED,
    "GMAIL_DRAFT_FAILED": FAILED,
    "PORTAL_ASSIST_FAILED": FAILED,
    "ERROR": FAILED,
    "FAILED": FAILED,
    # Explicit invalidation / expiry
    "INVALIDATED_BY_REANALYSIS": ANALYZED,
    "SKIP": SKIPPED,
    "SKIPPED": SKIPPED,
    "NEW": NEW,
    "ANALYZED": ANALYZED,
}


def lifecycle_for_status(status: str) -> str:
    """Map a fine-grained applications.status to a coarse lifecycle state."""
    if not status:
        return NEW
    return _STATUS_MAP.get(status.strip().upper(), ANALYZED)


def lifecycle_for_decision(decision: str) -> str:
    """Coarse state implied by an analysis decision when no package is built."""
    decision = (decision or "").strip().upper()
    if decision == "SKIP":
        return SKIPPED
    if decision == "REVIEW":
        return REVIEW_PENDING
    if decision == "APPLY":
        return REVIEW_PENDING  # package still needs delivery to become APPLIED
    return ANALYZED


def is_terminal(state: str) -> bool:
    """True when a job in this lifecycle state must not be reprocessed."""
    return (state or "").strip().upper() in TERMINAL_STATES
