"""Google Drive Document Gathering Service.

Searches Google Drive using metadata-only matching against agenda item keywords.
Uses file names, folder paths, tags, and modification dates — never reads document content.
Returns a list of suggested documents for user review and approval.
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.config import settings

logger = logging.getLogger(__name__)


class DriveSearchResult:
    """A document found by the Drive search engine."""
    def __init__(self, file_id: str, name: str, mime_type: str,
                 web_view_link: str = None, icon_link: str = None,
                 modified_time: str = None, owners: list = None,
                 parent_folder: str = None, size: int = None,
                 matched_keyword: str = None, relevance_score: float = 0.0):
        self.file_id = file_id
        self.name = name
        self.mime_type = mime_type
        self.web_view_link = web_view_link
        self.icon_link = icon_link
        self.modified_time = modified_time
        self.owners = owners or []
        self.parent_folder = parent_folder
        self.size = size
        self.matched_keyword = matched_keyword
        self.relevance_score = relevance_score

    def to_dict(self):
        return {
            "file_id": self.file_id,
            "name": self.name,
            "mime_type": self.mime_type,
            "web_view_link": self.web_view_link,
            "icon_link": self.icon_link,
            "modified_time": self.modified_time,
            "owners": [o.get("displayName", o.get("emailAddress", "")) for o in self.owners],
            "parent_folder": self.parent_folder,
            "size": self.size,
            "matched_keyword": self.matched_keyword,
            "relevance_score": self.relevance_score,
        }


class GoogleDriveService:
    """Searches Google Drive for documents relevant to meeting agenda items.

    Uses metadata-only matching — never reads document content.
    Requires valid Google OAuth credentials with Drive read scope.
    """

    # File types we consider relevant for meeting prep
    RELEVANT_MIME_TYPES = [
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.google-apps.presentation",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
    ]

    FIELDS = "files(id, name, mimeType, webViewLink, iconLink, modifiedTime, owners, parents, size)"

    def __init__(self, access_token: str):
        """Initialize with an OAuth2 access token."""
        creds = Credentials(token=access_token)
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)

    async def search_for_agenda(
        self,
        agenda_titles: List[str],
        max_results_per_item: int = 5,
        recency_days: int = 90,
    ) -> List[DriveSearchResult]:
        """Search Drive for documents matching agenda item titles.

        Searches each keyword individually and combines results.
        Uses both name matching and fullText matching for broader coverage.
        """
        all_results = []
        seen_ids = set()

        for title in agenda_titles:
            keywords = self._extract_keywords(title)
            if not keywords:
                continue

            logger.info(f"Document search for agenda '{title}' → keywords: {keywords}")

            # Search each keyword individually for better results
            for keyword in keywords:
                try:
                    results = self._search_files(keyword, max_results_per_item, recency_days)
                    for result in results:
                        if result.file_id not in seen_ids:
                            result.matched_keyword = title
                            seen_ids.add(result.file_id)
                            all_results.append(result)
                except Exception as e:
                    logger.warning(f"Drive search failed for keyword '{keyword}' (from '{title}'): {e}")

            # Also try the full meaningful phrase as a single query
            if len(keywords) > 1:
                phrase = " ".join(keywords[:3])
                try:
                    results = self._search_files(phrase, max_results_per_item, recency_days)
                    for result in results:
                        if result.file_id not in seen_ids:
                            result.matched_keyword = title
                            seen_ids.add(result.file_id)
                            all_results.append(result)
                except Exception as e:
                    logger.warning(f"Drive phrase search failed for '{phrase}': {e}")

        # Sort by relevance (most recent first as a proxy)
        all_results.sort(key=lambda r: r.modified_time or "", reverse=True)
        return all_results

    def _search_files(
        self, keyword: str, max_results: int, recency_days: int
    ) -> List[DriveSearchResult]:
        """Execute a Drive files.list query for a single keyword.

        Searches both file name and full text (metadata) for the keyword.
        """
        from datetime import timedelta

        # Escape single quotes in the keyword
        safe_keyword = keyword.replace("'", "\\'")

        # Search by name OR fullText — catches files with the keyword in name or description
        query_parts = [
            f"(name contains '{safe_keyword}' or fullText contains '{safe_keyword}')",
            "trashed = false",
        ]

        # Recency filter
        if recency_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=recency_days)
            query_parts.append(f"modifiedTime > '{cutoff.isoformat()}'")

        query = " and ".join(query_parts)

        try:
            response = self._service.files().list(
                q=query,
                pageSize=max_results,
                fields=self.FIELDS,
                orderBy="modifiedTime desc",
                spaces="drive",
            ).execute()
        except Exception as e:
            logger.error(f"Google Drive API error: {e}")
            raise

        results = []
        for file_data in response.get("files", []):
            results.append(DriveSearchResult(
                file_id=file_data["id"],
                name=file_data["name"],
                mime_type=file_data.get("mimeType", ""),
                web_view_link=file_data.get("webViewLink"),
                icon_link=file_data.get("iconLink"),
                modified_time=file_data.get("modifiedTime"),
                owners=file_data.get("owners", []),
                size=int(file_data.get("size", 0)) if file_data.get("size") else None,
            ))

        return results

    def _extract_keywords(self, title: str) -> List[str]:
        """Extract meaningful search keywords from an agenda item title.

        Returns a list of individual keywords (not joined).
        Removes common filler words to improve search precision.
        """
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "is", "are", "was", "were",
            "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might", "shall",
            "this", "that", "these", "those", "it", "its",
            "update", "review", "discuss", "item", "topic", "agenda",
            "meeting", "follow", "up", "status", "next", "steps",
            "decision", "need", "new", "add", "decide", "about",
        }

        words = title.strip().split()
        meaningful = [w for w in words if w.lower() not in stopwords and len(w) > 2]

        if not meaningful:
            # Fall back to splitting the title into words
            meaningful = [w for w in words if len(w) > 2]

        if not meaningful:
            return [title.strip()] if title.strip() else []

        # Return up to 5 individual keywords
        return meaningful[:5]


class DocumentGatheringService:
    """Orchestrates document gathering across storage providers.

    Currently supports Google Drive. Designed for extension to
    OneDrive/SharePoint via the same interface.
    """

    def __init__(self, db):
        self.db = db

    async def gather_documents(
        self,
        meeting_id,
        agenda_titles: List[str],
        access_token: Optional[str] = None,
        max_per_item: int = 5,
        recency_days: int = 90,
    ) -> List[dict]:
        """Search connected storage for documents matching agenda items.

        Args:
            meeting_id: Meeting UUID.
            agenda_titles: List of agenda item titles.
            access_token: Google OAuth access token. If None, returns empty.
            max_per_item: Max results per agenda item.
            recency_days: Only include files modified within this many days.

        Returns:
            List of document suggestion dicts ready for the API response.
        """
        suggestions = []

        if access_token:
            try:
                drive = GoogleDriveService(access_token)
                results = await drive.search_for_agenda(
                    agenda_titles, max_per_item, recency_days
                )
                for r in results:
                    suggestions.append(r.to_dict())
                logger.info(f"Drive search returned {len(suggestions)} results for meeting {meeting_id}")
            except Exception as e:
                logger.warning(f"Google Drive search failed: {e}")

        return suggestions
