"""Transcript Format Parsers - multi-format ingestion engine.

Parses transcripts from various external tools into a normalized segment model.
Each parser extracts: speaker identification, timestamps, and text content.

Supported formats:
  - SRT (SubRip): Numbered blocks with timestamps (HH:MM:SS,mmm --> HH:MM:SS,mmm)
  - VTT (WebVTT): WEBVTT header, optional cue IDs, timestamps (HH:MM:SS.mmm --> HH:MM:SS.mmm)
  - CSV: Columns for speaker, timestamp, text (auto-detects column mapping)
  - JSON: Array of objects or tool-specific schemas (Otter, Fireflies, etc.)
  - TXT: Plain text with speaker label heuristics (e.g., "Speaker Name: text")

Format auto-detection uses file extension (if available) + content heuristics.
"""

import re
import csv
import json
import io
from typing import List, Optional, Tuple

from app.schemas.transcript import ParsedSegment, ParseResult, TranscriptFormat


# ============================================
# TIMESTAMP UTILITIES
# ============================================

def _parse_srt_timestamp(ts: str) -> float:
    """Parse SRT timestamp (HH:MM:SS,mmm) to seconds."""
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return 0.0


def _parse_vtt_timestamp(ts: str) -> float:
    """Parse VTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) to seconds."""
    ts = ts.strip()
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return 0.0


def _extract_speaker_from_text(text: str) -> Tuple[Optional[str], str]:
    """Extract speaker label from the beginning of text.

    Handles common patterns:
      - "Speaker Name: text..."
      - "<v Speaker Name>text</v>"  (VTT voice tag)
      - "[Speaker Name] text..."
      - "SPEAKER NAME: text..."
    """
    # VTT voice tag: <v Speaker Name>text</v>
    m = re.match(r"<v\s+([^>]+)>(.+?)(?:</v>)?$", text, re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Bracket prefix: [Speaker Name] text
    m = re.match(r"\[([^\]]{1,60})\]\s*(.+)$", text, re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Colon prefix: Speaker Name: text (name must be 1-4 words, < 60 chars)
    m = re.match(r"^([A-Za-z][A-Za-z0-9 '.,-]{0,58}):\s+(.+)$", text, re.DOTALL)
    if m:
        name_candidate = m.group(1).strip()
        # Reject if "name" looks like a sentence or contains too many words
        words = name_candidate.split()
        if len(words) <= 4 and not any(w.lower() in ("the", "and", "but", "this", "that", "with") for w in words):
            return name_candidate, m.group(2).strip()

    return None, text


# ============================================
# FORMAT-SPECIFIC PARSERS
# ============================================

def parse_srt(text: str) -> ParseResult:
    """Parse SRT (SubRip) subtitle format.

    Format:
        1
        00:00:01,000 --> 00:00:04,500
        Speaker text here

        2
        00:00:05,000 --> 00:00:08,200
        More text here
    """
    segments: List[ParsedSegment] = []
    errors: List[str] = []
    speakers_seen: set = set()

    # Split into blocks by double newline
    blocks = re.split(r"\n\s*\n", text.strip())

    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue

        # First line should be sequence number (skip it)
        # Find the timestamp line
        ts_line = None
        text_start = 0
        for i, line in enumerate(lines):
            if "-->" in line:
                ts_line = line
                text_start = i + 1
                break

        if not ts_line:
            continue

        # Parse timestamps
        try:
            parts = re.split(r"\s*-->\s*", ts_line)
            start = _parse_srt_timestamp(parts[0])
            end = _parse_srt_timestamp(parts[1].split()[0])  # strip position info
        except (IndexError, ValueError) as e:
            errors.append(f"Failed to parse timestamp: {ts_line}")
            start, end = None, None

        # Join remaining lines as text
        content = " ".join(line.strip() for line in lines[text_start:] if line.strip())
        if not content:
            continue

        # Strip HTML tags (common in SRT)
        content = re.sub(r"<[^>]+>", "", content)

        # Try to extract speaker
        speaker, clean_text = _extract_speaker_from_text(content)
        if speaker:
            speakers_seen.add(speaker)

        segments.append(ParsedSegment(
            speaker_name=speaker,
            speaker_id=speaker,
            start_time=start,
            end_time=end,
            text=clean_text,
        ))

    duration = None
    if segments:
        end_times = [s.end_time for s in segments if s.end_time is not None]
        if end_times:
            duration = int(max(end_times))

    return ParseResult(
        segments=segments,
        format_detected=TranscriptFormat.srt,
        duration_seconds=duration,
        speaker_names=sorted(speakers_seen),
        errors=errors,
    )


def parse_vtt(text: str) -> ParseResult:
    """Parse WebVTT format.

    Format:
        WEBVTT

        00:00:01.000 --> 00:00:04.500
        <v Speaker Name>Text here</v>

        00:00:05.000 --> 00:00:08.200
        More text here
    """
    segments: List[ParsedSegment] = []
    errors: List[str] = []
    speakers_seen: set = set()

    # Strip WEBVTT header and metadata
    lines = text.strip().splitlines()
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("WEBVTT"):
            start_idx = i + 1
            break

    # Skip header metadata (lines before first empty line after WEBVTT)
    while start_idx < len(lines) and lines[start_idx].strip():
        start_idx += 1

    content = "\n".join(lines[start_idx:])
    blocks = re.split(r"\n\s*\n", content.strip())

    for block in blocks:
        block_lines = block.strip().splitlines()
        if not block_lines:
            continue

        # Find timestamp line
        ts_line = None
        text_start = 0
        for i, line in enumerate(block_lines):
            if "-->" in line:
                ts_line = line
                text_start = i + 1
                break

        if not ts_line:
            continue

        # Parse timestamps
        try:
            parts = re.split(r"\s*-->\s*", ts_line)
            start = _parse_vtt_timestamp(parts[0])
            end_part = parts[1].split()[0] if parts[1] else ""
            end = _parse_vtt_timestamp(end_part)
        except (IndexError, ValueError):
            errors.append(f"Failed to parse timestamp: {ts_line}")
            start, end = None, None

        content_text = " ".join(
            line.strip() for line in block_lines[text_start:] if line.strip()
        )
        if not content_text:
            continue

        speaker, clean_text = _extract_speaker_from_text(content_text)
        if speaker:
            speakers_seen.add(speaker)

        segments.append(ParsedSegment(
            speaker_name=speaker,
            speaker_id=speaker,
            start_time=start,
            end_time=end,
            text=clean_text,
        ))

    duration = None
    if segments:
        end_times = [s.end_time for s in segments if s.end_time is not None]
        if end_times:
            duration = int(max(end_times))

    return ParseResult(
        segments=segments,
        format_detected=TranscriptFormat.vtt,
        duration_seconds=duration,
        speaker_names=sorted(speakers_seen),
        errors=errors,
    )


def parse_csv(text: str) -> ParseResult:
    """Parse CSV transcript format.

    Auto-detects column mapping by header names. Supports common patterns:
      - speaker,timestamp,text
      - speaker,start_time,end_time,text
      - name,time,content
      - Otter.ai exports, Fireflies exports, etc.
    """
    segments: List[ParsedSegment] = []
    errors: List[str] = []
    speakers_seen: set = set()

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return ParseResult(
            segments=[], format_detected=TranscriptFormat.csv,
            errors=["No CSV headers found"],
        )

    # Normalize header names for matching
    headers = {h.strip().lower().replace(" ", "_"): h for h in reader.fieldnames}

    # Map columns
    speaker_col = None
    text_col = None
    start_col = None
    end_col = None

    for key, original in headers.items():
        if key in ("speaker", "speaker_name", "name", "participant", "who"):
            speaker_col = original
        elif key in ("text", "content", "transcript", "message", "utterance", "body"):
            text_col = original
        elif key in ("start_time", "start", "timestamp", "time", "start_seconds"):
            start_col = original
        elif key in ("end_time", "end", "end_seconds"):
            end_col = original

    if not text_col:
        return ParseResult(
            segments=[], format_detected=TranscriptFormat.csv,
            errors=[f"Could not identify text column. Headers: {list(reader.fieldnames)}"],
        )

    for i, row in enumerate(reader):
        content = row.get(text_col, "").strip()
        if not content:
            continue

        speaker = row.get(speaker_col, "").strip() if speaker_col else None
        if speaker:
            speakers_seen.add(speaker)

        start_time = None
        end_time = None
        if start_col:
            try:
                val = row.get(start_col, "").strip()
                start_time = float(val) if val else None
            except ValueError:
                # Try parsing as timestamp string
                start_time = _try_parse_any_timestamp(val)
        if end_col:
            try:
                val = row.get(end_col, "").strip()
                end_time = float(val) if val else None
            except ValueError:
                end_time = _try_parse_any_timestamp(val)

        segments.append(ParsedSegment(
            speaker_name=speaker,
            speaker_id=speaker,
            start_time=start_time,
            end_time=end_time,
            text=content,
        ))

    duration = None
    if segments:
        end_times = [s.end_time for s in segments if s.end_time is not None]
        if end_times:
            duration = int(max(end_times))

    return ParseResult(
        segments=segments,
        format_detected=TranscriptFormat.csv,
        duration_seconds=duration,
        speaker_names=sorted(speakers_seen),
        errors=errors,
    )


def parse_json(text: str) -> ParseResult:
    """Parse JSON transcript format.

    Supports:
      - Array of segment objects: [{"speaker": "...", "text": "...", ...}]
      - Otter.ai export: {"transcript": [{"speaker": ..., "text": ...}]}
      - Fireflies export: {"sentences": [{"speaker_name": ..., "text": ...}]}
      - Generic wrapper: {"segments": [...]} or {"data": [...]}
    """
    errors: List[str] = []
    speakers_seen: set = set()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return ParseResult(
            segments=[], format_detected=TranscriptFormat.json,
            errors=[f"Invalid JSON: {str(e)}"],
        )

    # Find the array of segments
    items = None
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        # Try common wrapper keys
        for key in ("transcript", "segments", "sentences", "data", "results", "utterances"):
            if key in data and isinstance(data[key], list):
                items = data[key]
                break

    if not items:
        return ParseResult(
            segments=[], format_detected=TranscriptFormat.json,
            errors=["Could not find segment array in JSON structure"],
        )

    segments: List[ParsedSegment] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        # Extract text (try multiple key names)
        content = None
        for key in ("text", "content", "transcript", "message", "body", "utterance"):
            if key in item and item[key]:
                content = str(item[key]).strip()
                break
        if not content:
            continue

        # Extract speaker
        speaker = None
        for key in ("speaker", "speaker_name", "name", "participant", "who", "speakerName"):
            if key in item and item[key]:
                speaker = str(item[key]).strip()
                break
        if speaker:
            speakers_seen.add(speaker)

        # Extract timestamps
        start_time = None
        end_time = None
        for key in ("start_time", "start", "startTime", "start_seconds", "timestamp"):
            if key in item and item[key] is not None:
                try:
                    start_time = float(item[key])
                except (ValueError, TypeError):
                    pass
                break
        for key in ("end_time", "end", "endTime", "end_seconds"):
            if key in item and item[key] is not None:
                try:
                    end_time = float(item[key])
                except (ValueError, TypeError):
                    pass
                break

        segments.append(ParsedSegment(
            speaker_name=speaker,
            speaker_id=speaker,
            start_time=start_time,
            end_time=end_time,
            text=content,
        ))

    duration = None
    if segments:
        end_times = [s.end_time for s in segments if s.end_time is not None]
        if end_times:
            duration = int(max(end_times))

    return ParseResult(
        segments=segments,
        format_detected=TranscriptFormat.json,
        duration_seconds=duration,
        speaker_names=sorted(speakers_seen),
        errors=errors,
    )


def parse_plain_text(text: str) -> ParseResult:
    """Parse plain text transcript with speaker label heuristics.

    Handles common patterns from copy-paste:
      - "Speaker Name: text here..."  (colon-delimited)
      - "[00:05:30] Speaker: text"    (timestamped)
      - Multi-line blocks per speaker
      - Raw text with no structure (single segment)
    """
    segments: List[ParsedSegment] = []
    speakers_seen: set = set()

    lines = text.strip().splitlines()
    if not lines:
        return ParseResult(segments=[], format_detected=TranscriptFormat.txt)

    # Try timestamped pattern: [00:05:30] Speaker: text
    timestamped_pattern = re.compile(
        r"^\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*[-–]?\s*(.+)$"
    )

    # Try speaker-colon pattern: Speaker Name: text
    speaker_pattern = re.compile(
        r"^([A-Za-z][A-Za-z0-9 '.,-]{0,58}):\s+(.+)$"
    )

    current_speaker = None
    current_text_parts: List[str] = []
    current_start: Optional[float] = None

    def _flush():
        nonlocal current_speaker, current_text_parts, current_start
        if current_text_parts:
            full_text = " ".join(current_text_parts)
            if full_text.strip():
                segments.append(ParsedSegment(
                    speaker_name=current_speaker,
                    speaker_id=current_speaker,
                    start_time=current_start,
                    end_time=None,
                    text=full_text.strip(),
                ))
            current_text_parts = []
            current_start = None

    has_any_speakers = False
    has_any_timestamps = False

    # First pass: check if the text has structure
    for line in lines[:20]:  # Check first 20 lines
        stripped = line.strip()
        if not stripped:
            continue
        if timestamped_pattern.match(stripped):
            has_any_timestamps = True
        if speaker_pattern.match(stripped):
            words = speaker_pattern.match(stripped).group(1).split()
            if len(words) <= 4:
                has_any_speakers = True

    # Parse based on detected structure
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        timestamp = None

        # Try to extract timestamp
        ts_match = timestamped_pattern.match(stripped)
        if ts_match and has_any_timestamps:
            ts_str = ts_match.group(1)
            timestamp = _try_parse_any_timestamp(ts_str)
            stripped = ts_match.group(2).strip()

        # Try to extract speaker
        sp_match = speaker_pattern.match(stripped)
        if sp_match and has_any_speakers:
            candidate = sp_match.group(1).strip()
            words = candidate.split()
            if len(words) <= 4 and not any(
                w.lower() in ("the", "and", "but", "this", "that", "with", "from") for w in words
            ):
                # New speaker turn — flush previous
                _flush()
                current_speaker = candidate
                current_start = timestamp
                current_text_parts.append(sp_match.group(2).strip())
                speakers_seen.add(candidate)
                continue

        # Continuation of current speaker or unstructured text
        if has_any_speakers and current_speaker:
            current_text_parts.append(stripped)
        else:
            # No speaker structure — each line or paragraph is a segment
            _flush()
            current_start = timestamp
            current_text_parts.append(stripped)

    _flush()

    # If no structure detected and we only got one huge segment, that's fine —
    # the LLM analysis pipeline will handle unstructured text

    duration = None
    if segments:
        end_times = [s.start_time for s in segments if s.start_time is not None]
        if end_times:
            duration = int(max(end_times))

    return ParseResult(
        segments=segments,
        format_detected=TranscriptFormat.txt,
        duration_seconds=duration,
        speaker_names=sorted(speakers_seen),
    )


# ============================================
# FORMAT AUTO-DETECTION
# ============================================

def detect_format(text: str, filename: Optional[str] = None) -> TranscriptFormat:
    """Auto-detect transcript format from content and optional filename.

    Detection priority:
      1. File extension (if provided)
      2. Content signature (WEBVTT header, SRT numbering, JSON brackets, CSV headers)
      3. Default to plain text
    """
    # 1. File extension
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        ext_map = {"srt": TranscriptFormat.srt, "vtt": TranscriptFormat.vtt,
                   "csv": TranscriptFormat.csv, "json": TranscriptFormat.json,
                   "txt": TranscriptFormat.txt}
        if ext in ext_map:
            return ext_map[ext]

    stripped = text.strip()

    # 2. Content signatures
    if stripped.startswith("WEBVTT"):
        return TranscriptFormat.vtt

    # SRT: starts with "1\n00:..." pattern
    if re.match(r"^\d+\s*\n\d{1,2}:\d{2}:\d{2}[,.]", stripped):
        return TranscriptFormat.srt

    # JSON: starts with [ or {
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            json.loads(stripped)
            return TranscriptFormat.json
        except json.JSONDecodeError:
            pass

    # CSV: first line looks like headers with commas
    first_line = stripped.split("\n")[0]
    if "," in first_line and any(
        kw in first_line.lower() for kw in ("speaker", "text", "timestamp", "content", "time")
    ):
        return TranscriptFormat.csv

    return TranscriptFormat.txt


def parse_transcript(text: str, filename: Optional[str] = None,
                     format_hint: Optional[TranscriptFormat] = None) -> ParseResult:
    """Parse transcript text using auto-detection or explicit format hint.

    This is the main entry point for transcript parsing.

    Args:
        text: Raw transcript content.
        filename: Original filename (used for format detection).
        format_hint: Explicit format override (skips auto-detection).

    Returns:
        ParseResult with normalized segments and metadata.
    """
    fmt = format_hint or detect_format(text, filename)

    parser_map = {
        TranscriptFormat.srt: parse_srt,
        TranscriptFormat.vtt: parse_vtt,
        TranscriptFormat.csv: parse_csv,
        TranscriptFormat.json: parse_json,
        TranscriptFormat.txt: parse_plain_text,
    }

    parser = parser_map.get(fmt, parse_plain_text)
    return parser(text)


# ============================================
# HELPERS
# ============================================

def _try_parse_any_timestamp(ts: str) -> Optional[float]:
    """Try to parse a timestamp string in any common format to seconds."""
    if not ts:
        return None
    ts = ts.strip()

    # HH:MM:SS or MM:SS
    parts = ts.replace(",", ".").split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        else:
            return float(ts)
    except ValueError:
        return None
