"""Google Calendar Integration Service.

Reads calendar events and imports them as meetings in the toolkit.
Extracts attendees, agenda descriptions, meeting links, and event metadata.
"""

import logging
import re
import uuid
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


class CalendarEvent:
    """A Google Calendar event parsed into toolkit-friendly format."""

    def __init__(self, event_data: dict):
        self.raw = event_data
        self.google_event_id = event_data.get("id", "")
        self.title = event_data.get("summary", "Untitled Event")
        self.description = event_data.get("description", "")
        self.location = event_data.get("location", "")
        self.html_link = event_data.get("htmlLink", "")

        # Parse dates
        start = event_data.get("start", {})
        end = event_data.get("end", {})
        self.start_datetime = start.get("dateTime") or start.get("date")
        self.end_datetime = end.get("dateTime") or end.get("date")
        self.is_all_day = "date" in start and "dateTime" not in start

        # Parse date and time separately
        self.date = None
        self.time = None
        self.duration_minutes = None
        if self.start_datetime:
            try:
                if "T" in self.start_datetime:
                    dt = datetime.fromisoformat(self.start_datetime.replace("Z", "+00:00"))
                    self.date = dt.date().isoformat()
                    self.time = dt.time().isoformat()
                    if self.end_datetime and "T" in self.end_datetime:
                        end_dt = datetime.fromisoformat(self.end_datetime.replace("Z", "+00:00"))
                        self.duration_minutes = int((end_dt - dt).total_seconds() / 60)
                else:
                    self.date = self.start_datetime
            except (ValueError, TypeError):
                pass

        # Meeting link (Google Meet, Zoom, Teams, etc.)
        self.meeting_link = None
        conference = event_data.get("conferenceData", {})
        entry_points = conference.get("entryPoints", [])
        for ep in entry_points:
            if ep.get("entryPointType") == "video":
                self.meeting_link = ep.get("uri")
                break
        # Also check hangoutLink
        if not self.meeting_link:
            self.meeting_link = event_data.get("hangoutLink")

        # Attendees
        self.attendees = []
        for att in event_data.get("attendees", []):
            self.attendees.append({
                "email": att.get("email", ""),
                "name": att.get("displayName", att.get("email", "").split("@")[0]),
                "rsvp_status": self._map_rsvp(att.get("responseStatus", "needsAction")),
                "is_organizer": att.get("organizer", False),
            })

        # Organizer
        organizer = event_data.get("organizer", {})
        self.organizer_email = organizer.get("email", "")
        self.organizer_name = organizer.get("displayName", "")

        # Recurrence
        self.is_recurring = bool(event_data.get("recurringEventId"))

        # Status
        self.status = event_data.get("status", "confirmed")

    def _map_rsvp(self, google_status: str) -> str:
        """Map Google Calendar response status to toolkit RSVP status."""
        mapping = {
            "accepted": "accepted",
            "declined": "declined",
            "tentative": "tentative",
            "needsAction": "pending",
        }
        return mapping.get(google_status, "pending")

    def extract_agenda_items(self) -> List[dict]:
        """Extract agenda items from the event description.

        Looks for bullet points, numbered lists, or line-separated items
        in the description text.
        """
        if not self.description:
            return []

        # Strip HTML tags if present
        clean = re.sub(r"<[^>]+>", "\n", self.description)
        clean = re.sub(r"&nbsp;", " ", clean)
        clean = re.sub(r"&amp;", "&", clean)
        clean = re.sub(r"&#?\w+;", " ", clean)

        items = []
        lines = clean.strip().splitlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove bullet markers
            cleaned = re.sub(r"^[\-\*•·▪►]\s*", "", line)
            # Remove numbered list markers
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", cleaned)
            cleaned = cleaned.strip()

            if cleaned and len(cleaned) > 3:
                items.append({"title": cleaned})

        return items

    def to_dict(self) -> dict:
        """Convert to API response format."""
        return {
            "google_event_id": self.google_event_id,
            "title": self.title,
            "date": self.date,
            "time": self.time,
            "duration_minutes": self.duration_minutes,
            "description": self.description,
            "location": self.location,
            "meeting_link": self.meeting_link,
            "html_link": self.html_link,
            "is_all_day": self.is_all_day,
            "is_recurring": self.is_recurring,
            "status": self.status,
            "organizer": {
                "email": self.organizer_email,
                "name": self.organizer_name,
            },
            "attendees": self.attendees,
            "agenda_items": self.extract_agenda_items(),
            "attendee_count": len(self.attendees),
        }


class GoogleCalendarService:
    """Reads events from Google Calendar API."""

    def __init__(self, access_token: str):
        creds = Credentials(token=access_token)
        self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    def list_upcoming_events(
        self,
        max_results: int = 20,
        days_ahead: int = 14,
        calendar_id: str = "primary",
    ) -> List[CalendarEvent]:
        """Fetch upcoming events from the user's calendar.

        Args:
            max_results: Maximum number of events to return.
            days_ahead: How many days ahead to look.
            calendar_id: Calendar to query (default: primary).

        Returns:
            List of CalendarEvent objects.
        """
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days_ahead)

        try:
            response = self._service.events().list(
                calendarId=calendar_id,
                timeMin=now.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
        except Exception as e:
            logger.error(f"Google Calendar API error: {e}")
            raise

        events = []
        for event_data in response.get("items", []):
            # Skip cancelled events
            if event_data.get("status") == "cancelled":
                continue
            events.append(CalendarEvent(event_data))

        logger.info(f"Fetched {len(events)} upcoming events from Google Calendar")
        return events

    def get_event(self, event_id: str, calendar_id: str = "primary") -> CalendarEvent:
        """Fetch a single event by ID."""
        event_data = self._service.events().get(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()
        return CalendarEvent(event_data)
