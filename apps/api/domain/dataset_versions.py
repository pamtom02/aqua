from enum import Enum


class VersionState(str, Enum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


ALLOWED_STATE_TRANSITIONS: dict[VersionState, list[VersionState]] = {
    VersionState.DRAFT: [VersionState.IN_REVIEW, VersionState.ARCHIVED],
    VersionState.IN_REVIEW: [
        VersionState.APPROVED,
        VersionState.DRAFT,
        VersionState.ARCHIVED,
    ],
    VersionState.APPROVED: [
        VersionState.PUBLISHED,
        VersionState.DRAFT,
        VersionState.ARCHIVED,
    ],
    VersionState.PUBLISHED: [VersionState.ARCHIVED],
    VersionState.ARCHIVED: [],
}


def can_transition(current: VersionState, target: VersionState) -> bool:
    return target in ALLOWED_STATE_TRANSITIONS.get(current, ())
