-- Meeting Toolkit - Database Schema
-- Based on System Architecture Document v1.0

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- CORE TABLES
-- ============================================

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    llm_tier_default INTEGER NOT NULL DEFAULT 1 CHECK (llm_tier_default IN (1, 2, 3)),
    settings_json JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    auth_provider VARCHAR(50) NOT NULL DEFAULT 'auth0',
    auth_provider_id VARCHAR(255),
    org_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE meetings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    date DATE,
    time TIME,
    duration_minutes INTEGER,
    organizer_id UUID REFERENCES users(id) ON DELETE SET NULL,
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    calendar_event_id VARCHAR(255),
    calendar_provider VARCHAR(50),
    status VARCHAR(50) NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'in_progress', 'completed', 'cancelled')),
    llm_tier INTEGER DEFAULT NULL CHECK (llm_tier IS NULL OR llm_tier IN (1, 2, 3)),
    meeting_link VARCHAR(1000),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE agenda_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    time_allocation_minutes INTEGER,
    item_order INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending'
        CHECK (status IN ('pending', 'discussed', 'deferred', 'skipped')),
    presenter_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE meeting_attendees (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    email VARCHAR(255),
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'attendee'
        CHECK (role IN ('organizer', 'facilitator', 'note_taker', 'decision_maker', 'attendee')),
    rsvp_status VARCHAR(50) DEFAULT 'pending'
        CHECK (rsvp_status IN ('pending', 'accepted', 'declined', 'tentative')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(meeting_id, email)
);

-- ============================================
-- DOCUMENT TABLES
-- ============================================

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    agenda_item_id UUID REFERENCES agenda_items(id) ON DELETE SET NULL,
    source VARCHAR(50) NOT NULL DEFAULT 'google_drive'
        CHECK (source IN ('google_drive', 'onedrive', 'upload', 'manual')),
    source_file_id VARCHAR(500),
    file_name VARCHAR(500) NOT NULL,
    file_path VARCHAR(1000),
    file_url VARCHAR(2000),
    mime_type VARCHAR(100),
    approved BOOLEAN DEFAULT FALSE,
    approved_at TIMESTAMP WITH TIME ZONE,
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- TRANSCRIPT TABLES
-- ============================================

CREATE TABLE transcripts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    raw_text TEXT,
    original_format VARCHAR(20) NOT NULL DEFAULT 'txt'
        CHECK (original_format IN ('txt', 'srt', 'vtt', 'csv', 'json')),
    original_filename VARCHAR(500),
    file_size_bytes INTEGER,
    parsed_status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (parsed_status IN ('pending', 'parsing', 'parsed', 'failed')),
    parse_error TEXT,
    segment_count INTEGER DEFAULT 0,
    speaker_count INTEGER DEFAULT 0,
    duration_seconds INTEGER,
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    parsed_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(meeting_id)
);

CREATE TABLE transcript_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transcript_id UUID NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    segment_order INTEGER NOT NULL,
    speaker_id VARCHAR(255),
    speaker_name VARCHAR(255),
    start_time FLOAT,
    end_time FLOAT,
    text TEXT NOT NULL,
    agenda_item_id UUID REFERENCES agenda_items(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- ACTION ITEM TABLES
-- ============================================

CREATE TABLE action_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    task TEXT NOT NULL,
    owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
    owner_name VARCHAR(255),
    deadline DATE,
    priority VARCHAR(10) DEFAULT 'medium'
        CHECK (priority IN ('high', 'medium', 'low')),
    status VARCHAR(50) DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    confirmed BOOLEAN DEFAULT FALSE,
    confirmed_at TIMESTAMP WITH TIME ZONE,
    source_segment_id UUID REFERENCES transcript_segments(id) ON DELETE SET NULL,
    source_quote TEXT,
    dependencies TEXT,
    completed_at TIMESTAMP WITH TIME ZONE,
    reminder_sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- OUTPUT TABLES
-- ============================================

CREATE TABLE meeting_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    summary_text TEXT,
    decisions_json JSONB DEFAULT '[]',
    topics_json JSONB DEFAULT '[]',
    speakers_json JSONB DEFAULT '[]',
    llm_provider VARCHAR(50),
    llm_model VARCHAR(100),
    llm_tier INTEGER,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(meeting_id)
);

CREATE TABLE generated_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    doc_type VARCHAR(50) NOT NULL
        CHECK (doc_type IN ('minutes', 'briefing', 'agenda_draft', 'summary_email')),
    file_path VARCHAR(1000) NOT NULL,
    file_format VARCHAR(10) NOT NULL DEFAULT 'docx'
        CHECK (file_format IN ('docx', 'pdf', 'html', 'txt')),
    file_size_bytes INTEGER,
    template_id UUID REFERENCES templates(id) ON DELETE SET NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    doc_type VARCHAR(50) NOT NULL
        CHECK (doc_type IN ('minutes', 'briefing', 'agenda_draft', 'summary_email')),
    template_json JSONB NOT NULL DEFAULT '{}',
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX idx_meetings_org_id ON meetings(org_id);
CREATE INDEX idx_meetings_organizer_id ON meetings(organizer_id);
CREATE INDEX idx_meetings_date ON meetings(date DESC);
CREATE INDEX idx_meetings_status ON meetings(status);
CREATE INDEX idx_agenda_items_meeting_id ON agenda_items(meeting_id);
CREATE INDEX idx_meeting_attendees_meeting_id ON meeting_attendees(meeting_id);
CREATE INDEX idx_documents_meeting_id ON documents(meeting_id);
CREATE INDEX idx_transcripts_meeting_id ON transcripts(meeting_id);
CREATE INDEX idx_transcript_segments_transcript_id ON transcript_segments(transcript_id);
CREATE INDEX idx_transcript_segments_agenda_item_id ON transcript_segments(agenda_item_id);
CREATE INDEX idx_action_items_meeting_id ON action_items(meeting_id);
CREATE INDEX idx_action_items_owner_id ON action_items(owner_id);
CREATE INDEX idx_action_items_status ON action_items(status);
CREATE INDEX idx_action_items_deadline ON action_items(deadline);
CREATE INDEX idx_generated_documents_meeting_id ON generated_documents(meeting_id);
CREATE INDEX idx_templates_org_id ON templates(org_id);
