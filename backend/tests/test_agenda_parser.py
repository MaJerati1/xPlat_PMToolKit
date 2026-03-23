"""Tests for the agenda text parser.

Tests all supported input formats: numbered lists, bullets, time-stamped,
inline metadata (presenter, time allocation), sub-items, and edge cases.
"""

import pytest
from app.parsers.agenda_parser import parse_agenda_text


class TestNumberedLists:
    """Test parsing numbered list formats."""

    def test_basic_numbered_list(self):
        text = """
1. Revenue Review
2. Hiring Plan
3. Product Roadmap
        """
        items = parse_agenda_text(text)
        assert len(items) == 3
        assert items[0].title == "Revenue Review"
        assert items[1].title == "Hiring Plan"
        assert items[2].title == "Product Roadmap"
        assert items[0].item_order == 0
        assert items[1].item_order == 1
        assert items[2].item_order == 2

    def test_parenthesis_numbered_list(self):
        text = """
1) Opening Remarks
2) Budget Discussion
3) Next Steps
        """
        items = parse_agenda_text(text)
        assert len(items) == 3
        assert items[0].title == "Opening Remarks"

    def test_numbered_with_description(self):
        text = """
1. Revenue Review - Discuss Q1 actuals vs forecast
2. Hiring Plan: Review open headcount across teams
        """
        items = parse_agenda_text(text)
        assert len(items) == 2
        assert items[0].title == "Revenue Review"
        assert items[0].description == "Discuss Q1 actuals vs forecast"
        assert items[1].title == "Hiring Plan"
        assert items[1].description == "Review open headcount across teams"


class TestBulletLists:
    """Test parsing bullet list formats."""

    def test_dash_bullets(self):
        text = """
- Welcome and Introductions
- Project Status Update
- Open Discussion
        """
        items = parse_agenda_text(text)
        assert len(items) == 3
        assert items[0].title == "Welcome and Introductions"

    def test_asterisk_bullets(self):
        text = """
* Design Review
* Code Walkthrough
* Sprint Planning
        """
        items = parse_agenda_text(text)
        assert len(items) == 3
        assert items[0].title == "Design Review"

    def test_unicode_bullets(self):
        text = """
• Team Updates
• Client Feedback
• Action Items
        """
        items = parse_agenda_text(text)
        assert len(items) == 3
        assert items[0].title == "Team Updates"


class TestTimeStampedFormats:
    """Test parsing time-stamped agenda items."""

    def test_time_range(self):
        text = """
9:00-9:15 Opening Remarks
9:15-9:45 Revenue Review
9:45-10:00 Q&A
        """
        items = parse_agenda_text(text)
        assert len(items) == 3
        assert items[0].title == "Opening Remarks"
        assert items[0].time_allocation_minutes == 15
        assert items[1].title == "Revenue Review"
        assert items[1].time_allocation_minutes == 30

    def test_single_time(self):
        text = """
9:00 AM - Welcome
10:00 AM - Keynote
11:30 AM - Break
        """
        items = parse_agenda_text(text)
        assert len(items) == 3
        assert items[0].title == "Welcome"
        assert items[1].title == "Keynote"


class TestInlineMetadata:
    """Test extraction of time allocation and presenter from inline text."""

    def test_time_allocation_parentheses(self):
        text = """
1. Revenue Review (15 min)
2. Hiring Plan (20 minutes)
3. Quick Update (~5m)
        """
        items = parse_agenda_text(text)
        assert items[0].time_allocation_minutes == 15
        assert items[1].time_allocation_minutes == 20
        assert items[2].time_allocation_minutes == 5

    def test_time_allocation_brackets(self):
        text = """
- Design Review [30 min]
- Sprint Retro [15 min]
        """
        items = parse_agenda_text(text)
        assert items[0].time_allocation_minutes == 30
        assert items[1].time_allocation_minutes == 15

    def test_presenter_brackets(self):
        text = """
1. Revenue Review [Alice Johnson]
2. Hiring Plan [Bob Smith]
        """
        items = parse_agenda_text(text)
        assert len(items) == 2
        # Presenter name extracted but not mapped to user ID (no DB lookup in parser)
        assert "Alice Johnson" not in items[0].title
        assert "Bob Smith" not in items[1].title

    def test_presenter_keyword(self):
        text = """
1. Revenue Review (Presenter: Alice Johnson)
2. Hiring Plan (Lead: Bob Smith)
        """
        items = parse_agenda_text(text)
        assert len(items) == 2


class TestSubItems:
    """Test sub-item merging into parent description."""

    def test_sub_items_merged(self):
        text = """
1. Hiring Plan
   - Engineering team needs
   - Sales expansion
   - Marketing roles
2. Budget Review
        """
        items = parse_agenda_text(text)
        assert len(items) == 2
        assert items[0].title == "Hiring Plan"
        assert "Engineering team needs" in items[0].description
        assert "Sales expansion" in items[0].description
        assert "Marketing roles" in items[0].description
        assert items[1].title == "Budget Review"


class TestEdgeCases:
    """Test edge cases and unusual input."""

    def test_empty_input(self):
        items = parse_agenda_text("")
        assert len(items) == 0

    def test_only_header(self):
        text = "Meeting Agenda"
        items = parse_agenda_text(text)
        assert len(items) == 0

    def test_skip_common_headers(self):
        text = """
Agenda:
1. First Item
2. Second Item
        """
        items = parse_agenda_text(text)
        assert len(items) == 2
        assert items[0].title == "First Item"

    def test_mixed_formats(self):
        text = """
Agenda
1. Opening Remarks (5 min)
- Project Alpha Update (15 min)
  - Timeline review
  - Risk assessment
2. Budget Discussion (20 min) [Jane Doe]
* Closing and Next Steps
        """
        items = parse_agenda_text(text)
        assert len(items) >= 4
        assert items[0].title == "Opening Remarks"
        assert items[0].time_allocation_minutes == 5

    def test_blank_lines_between_items(self):
        text = """
1. First Item

2. Second Item

3. Third Item
        """
        items = parse_agenda_text(text)
        assert len(items) == 3

    def test_sequential_ordering(self):
        text = """
- Alpha
- Beta
- Gamma
- Delta
        """
        items = parse_agenda_text(text)
        for i, item in enumerate(items):
            assert item.item_order == i

    def test_real_world_email_paste(self):
        """Test with a realistic email-pasted agenda."""
        text = """
Meeting Agenda:

1. Welcome and Introductions (5 min)
2. Q1 Financial Review - Present Q1 results against budget (20 min) [CFO]
   - Revenue breakdown by region
   - Operating expenses
   - Cash flow update
3. Product Roadmap Update (15 min) (Presenter: VP Product)
   - Feature prioritization
   - Release timeline
4. Engineering Hiring Status (10 min)
5. Open Discussion / Q&A (10 min)
        """
        items = parse_agenda_text(text)
        assert len(items) == 5
        assert items[0].title == "Welcome and Introductions"
        assert items[0].time_allocation_minutes == 5
        assert items[1].time_allocation_minutes == 20
        assert "Revenue breakdown by region" in items[1].description
        assert items[2].time_allocation_minutes == 15
        assert items[3].time_allocation_minutes == 10
        total_time = sum(i.time_allocation_minutes for i in items if i.time_allocation_minutes)
        assert total_time == 60
