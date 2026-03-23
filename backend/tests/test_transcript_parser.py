"""Tests for the transcript format parsers.

Tests SRT, VTT, CSV, JSON, plain text parsing, format auto-detection,
speaker extraction, and timestamp parsing.
"""

import pytest
from app.parsers.transcript_parser import (
    parse_srt, parse_vtt, parse_csv, parse_json, parse_plain_text,
    detect_format, parse_transcript,
)
from app.schemas.transcript import TranscriptFormat


class TestSRTParser:
    """Test SRT (SubRip) format parsing."""

    def test_basic_srt(self):
        text = """1
00:00:01,000 --> 00:00:04,500
Hello everyone, welcome to the meeting.

2
00:00:05,000 --> 00:00:08,200
Thanks for joining today.

3
00:00:09,000 --> 00:00:15,000
Let's get started with the agenda.
"""
        result = parse_srt(text)
        assert len(result.segments) == 3
        assert result.segments[0].text == "Hello everyone, welcome to the meeting."
        assert result.segments[0].start_time == 1.0
        assert result.segments[0].end_time == 4.5
        assert result.segments[2].end_time == 15.0
        assert result.duration_seconds == 15

    def test_srt_with_speakers(self):
        text = """1
00:00:01,000 --> 00:00:04,500
Alice: Good morning team.

2
00:00:05,000 --> 00:00:08,200
Bob: Thanks Alice, let's begin.
"""
        result = parse_srt(text)
        assert len(result.segments) == 2
        assert result.segments[0].speaker_name == "Alice"
        assert result.segments[0].text == "Good morning team."
        assert result.segments[1].speaker_name == "Bob"
        assert "Alice" in result.speaker_names
        assert "Bob" in result.speaker_names

    def test_srt_with_html_tags(self):
        text = """1
00:00:01,000 --> 00:00:03,000
<b>Important</b> announcement <i>here</i>.
"""
        result = parse_srt(text)
        assert result.segments[0].text == "Important announcement here."


class TestVTTParser:
    """Test WebVTT format parsing."""

    def test_basic_vtt(self):
        text = """WEBVTT

00:00:01.000 --> 00:00:04.500
Hello everyone.

00:00:05.000 --> 00:00:08.200
Welcome to the meeting.
"""
        result = parse_vtt(text)
        assert len(result.segments) == 2
        assert result.segments[0].text == "Hello everyone."
        assert result.segments[0].start_time == 1.0
        assert result.segments[0].end_time == 4.5

    def test_vtt_with_voice_tags(self):
        text = """WEBVTT

00:00:01.000 --> 00:00:04.500
<v Alice>Good morning everyone.</v>

00:00:05.000 --> 00:00:08.200
<v Bob>Thanks for joining.
"""
        result = parse_vtt(text)
        assert len(result.segments) == 2
        assert result.segments[0].speaker_name == "Alice"
        assert result.segments[0].text == "Good morning everyone."
        assert result.segments[1].speaker_name == "Bob"

    def test_vtt_with_cue_ids(self):
        text = """WEBVTT

cue-1
00:00:01.000 --> 00:00:04.500
First segment.

cue-2
00:00:05.000 --> 00:00:08.200
Second segment.
"""
        result = parse_vtt(text)
        assert len(result.segments) == 2

    def test_vtt_with_header_metadata(self):
        text = """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:04.500
Hello world.
"""
        result = parse_vtt(text)
        assert len(result.segments) == 1
        assert result.segments[0].text == "Hello world."


class TestCSVParser:
    """Test CSV transcript parsing with auto column detection."""

    def test_basic_csv(self):
        text = """speaker,timestamp,text
Alice,0,Good morning everyone.
Bob,5.5,Thanks Alice.
Alice,12,Let's review the agenda.
"""
        result = parse_csv(text)
        assert len(result.segments) == 3
        assert result.segments[0].speaker_name == "Alice"
        assert result.segments[0].text == "Good morning everyone."
        assert result.segments[1].speaker_name == "Bob"
        assert result.segments[1].start_time == 5.5

    def test_csv_with_start_end(self):
        text = """speaker,start_time,end_time,text
Alice,0,4.5,Hello team.
Bob,5,8.2,Good morning.
"""
        result = parse_csv(text)
        assert len(result.segments) == 2
        assert result.segments[0].start_time == 0.0
        assert result.segments[0].end_time == 4.5

    def test_csv_alternative_headers(self):
        text = """participant,content,time
Alice,Good morning.,0
Bob,Hello everyone.,5
"""
        result = parse_csv(text)
        assert len(result.segments) == 2
        assert result.segments[0].speaker_name == "Alice"
        assert result.segments[0].text == "Good morning."


class TestJSONParser:
    """Test JSON transcript parsing with various schemas."""

    def test_simple_array(self):
        text = """[
    {"speaker": "Alice", "text": "Good morning.", "start_time": 0, "end_time": 4.5},
    {"speaker": "Bob", "text": "Hello everyone.", "start_time": 5, "end_time": 8}
]"""
        result = parse_json(text)
        assert len(result.segments) == 2
        assert result.segments[0].speaker_name == "Alice"
        assert result.segments[0].start_time == 0
        assert result.segments[1].end_time == 8

    def test_wrapper_object(self):
        text = """{"transcript": [
    {"speaker": "Alice", "text": "Hello."},
    {"speaker": "Bob", "text": "Hi there."}
]}"""
        result = parse_json(text)
        assert len(result.segments) == 2

    def test_fireflies_format(self):
        text = """{"sentences": [
    {"speaker_name": "Alice Johnson", "text": "Welcome.", "startTime": 0, "endTime": 3},
    {"speaker_name": "Bob Smith", "text": "Thanks.", "startTime": 4, "endTime": 6}
]}"""
        result = parse_json(text)
        assert len(result.segments) == 2
        assert result.segments[0].speaker_name == "Alice Johnson"

    def test_invalid_json(self):
        result = parse_json("{not valid json")
        assert len(result.segments) == 0
        assert len(result.errors) > 0


class TestPlainTextParser:
    """Test plain text transcript parsing with speaker heuristics."""

    def test_speaker_colon_format(self):
        text = """Alice: Good morning everyone. Welcome to the Q2 planning meeting.
Bob: Thanks Alice. I have a few items to discuss.
Alice: Great, let's start with the revenue review.
Carol: I can present those numbers.
"""
        result = parse_plain_text(text)
        assert len(result.segments) == 4
        assert result.segments[0].speaker_name == "Alice"
        assert result.segments[1].speaker_name == "Bob"
        assert result.segments[3].speaker_name == "Carol"
        assert "Alice" in result.speaker_names
        assert "Carol" in result.speaker_names

    def test_timestamped_format(self):
        text = """[00:00:05] Alice: Welcome to the meeting.
[00:01:30] Bob: Thanks, let's begin.
[00:03:00] Alice: First item on the agenda.
"""
        result = parse_plain_text(text)
        assert len(result.segments) == 3
        assert result.segments[0].start_time == 5.0
        assert result.segments[1].start_time == 90.0

    def test_unstructured_text(self):
        text = """Welcome to the meeting.
Today we're discussing the Q2 roadmap.
Several key decisions need to be made.
"""
        result = parse_plain_text(text)
        assert len(result.segments) >= 1
        # Should still capture the content even without structure

    def test_empty_input(self):
        result = parse_plain_text("")
        assert len(result.segments) == 0


class TestFormatDetection:
    """Test format auto-detection."""

    def test_detect_by_extension(self):
        assert detect_format("anything", "meeting.srt") == TranscriptFormat.srt
        assert detect_format("anything", "meeting.vtt") == TranscriptFormat.vtt
        assert detect_format("anything", "meeting.csv") == TranscriptFormat.csv
        assert detect_format("anything", "meeting.json") == TranscriptFormat.json
        assert detect_format("anything", "meeting.txt") == TranscriptFormat.txt

    def test_detect_vtt_by_content(self):
        assert detect_format("WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nHello") == TranscriptFormat.vtt

    def test_detect_srt_by_content(self):
        assert detect_format("1\n00:00:01,000 --> 00:00:04,000\nHello") == TranscriptFormat.srt

    def test_detect_json_by_content(self):
        assert detect_format('[{"text": "hello"}]') == TranscriptFormat.json
        assert detect_format('{"transcript": []}') == TranscriptFormat.json

    def test_detect_csv_by_content(self):
        assert detect_format("speaker,timestamp,text\nAlice,0,Hello") == TranscriptFormat.csv

    def test_fallback_to_txt(self):
        assert detect_format("Just some random text here.") == TranscriptFormat.txt


class TestParseTranscript:
    """Test the main parse_transcript entry point."""

    def test_auto_detect_and_parse_srt(self):
        text = """1
00:00:01,000 --> 00:00:04,500
Hello world.
"""
        result = parse_transcript(text, filename="meeting.srt")
        assert result.format_detected == TranscriptFormat.srt
        assert len(result.segments) == 1

    def test_format_hint_overrides_detection(self):
        text = """Alice: Hello everyone.
Bob: Good morning.
"""
        result = parse_transcript(text, format_hint=TranscriptFormat.txt)
        assert result.format_detected == TranscriptFormat.txt
        assert len(result.segments) == 2

    def test_real_world_otter_style(self):
        """Simulate an Otter.ai-style plain text export."""
        text = """Alice Johnson  0:05
Good morning everyone. Welcome to our weekly standup.

Bob Smith  0:15
Thanks Alice. I finished the API integration yesterday.

Carol Davis  0:30
Nice work Bob. I'm still working on the frontend.

Alice Johnson  0:45
Great updates. Any blockers?

Bob Smith  0:55
None from my side.

Carol Davis  1:05
I need access to the staging environment.
"""
        result = parse_transcript(text)
        assert len(result.segments) >= 3
