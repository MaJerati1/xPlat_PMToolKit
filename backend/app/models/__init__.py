"""ORM model registry - import all models so Base.metadata.create_all() finds them."""

from app.models.meeting import Organization, User, Meeting, AgendaItem, MeetingAttendee, Document  # noqa: F401
from app.models.transcript import Transcript, TranscriptSegment  # noqa: F401
from app.models.analysis import MeetingSummary, ActionItem  # noqa: F401