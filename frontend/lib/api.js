/**
 * API client for the Meeting Toolkit backend.
 *
 * Uses relative URLs (/api/...) so requests go through the Next.js rewrite proxy.
 * This avoids CORS issues since the browser sees all requests as same-origin.
 */

const API_BASE = typeof window !== 'undefined' ? '' : (process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000');

// Direct backend URL for long-running requests (bypasses Next.js proxy timeout)
// Falls back to relative URL if not configured (will use proxy)
const BACKEND_DIRECT = typeof window !== 'undefined'
  ? (process.env.NEXT_PUBLIC_BACKEND_DIRECT || 'http://localhost:8000')
  : 'http://backend:8000';

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const { headers: optHeaders, ...restOptions } = options;
  const res = await fetch(url, {
    ...restOptions,
    headers: { 'Content-Type': 'application/json', ...optHeaders },
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    const detail = errorData.detail;
    const msg = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join('; ')
      : `API error: ${res.status}`;
    throw new Error(msg);
  }

  if (res.status === 204) return null;
  return res.json();
}

// Direct request to backend — bypasses Next.js proxy for long-running calls
async function directRequest(path, options = {}) {
  const url = `${BACKEND_DIRECT}${path}`;
  const { headers: optHeaders, ...restOptions } = options;
  const res = await fetch(url, {
    ...restOptions,
    headers: { 'Content-Type': 'application/json', ...optHeaders },
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    const detail = errorData.detail;
    const msg = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join('; ')
      : `API error: ${res.status}`;
    throw new Error(msg);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Meetings
  createMeeting: (data) => request('/api/meetings', { method: 'POST', body: JSON.stringify(data) }),
  getMeeting: (id) => request(`/api/meetings/${id}`),

  // Transcript upload
  uploadTranscriptText: (meetingId, text, formatHint) =>
    request(`/api/meetings/${meetingId}/transcript/text`, {
      method: 'POST',
      body: JSON.stringify({ text, format_hint: formatHint || undefined }),
    }),
  uploadTranscriptFile: async (meetingId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    const url = `${API_BASE}/api/meetings/${meetingId}/transcript`;
    const res = await fetch(url, { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const detail = err.detail;
      const msg = typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join('; ')
        : `Upload failed: ${res.status}`;
      throw new Error(msg);
    }
    return res.json();
  },

  // Quick Analyze (file) - creates meeting, uploads file, analyzes in sequence
  quickAnalyzeFile: async (file) => {
    // Step 1: Create meeting
    const meeting = await request('/api/meetings', {
      method: 'POST',
      body: JSON.stringify({ title: `Quick Analysis — ${new Date().toLocaleDateString()}` }),
    });

    // Step 2: Upload file
    const formData = new FormData();
    formData.append('file', file);
    const url = `${API_BASE}/api/meetings/${meeting.id}/transcript`;
    const uploadRes = await fetch(url, { method: 'POST', body: formData });
    if (!uploadRes.ok) {
      const err = await uploadRes.json().catch(() => ({}));
      throw new Error(typeof err.detail === 'string' ? err.detail : `Upload failed: ${uploadRes.status}`);
    }

    // Step 3: Analyze (direct to backend — bypasses proxy timeout)
    const analysis = await directRequest(`/api/meetings/${meeting.id}/analyze`, {
      method: 'POST',
      body: JSON.stringify({ reanalyze: false }),
    });

    // Step 4: Get action items
    const items = await request(`/api/meetings/${meeting.id}/action-items`);

    // Step 5: Get summary for the quick-analyze response format
    let summary = null;
    try { summary = await request(`/api/meetings/${meeting.id}/summary`); } catch {}

    return {
      meeting_id: meeting.id,
      status: analysis.status || 'completed',
      transcript_info: { format: 'file', segments: 0, speakers: 0 },
      summary: summary ? { text: summary.summary_text } : null,
      decisions: summary?.decisions || [],
      action_items: items.map(i => ({ ...i, owner: i.owner_name })),
      topics: summary?.topics || [],
      speakers: summary?.speakers || [],
      llm_provider: analysis.llm_provider,
      llm_model: analysis.llm_model,
    };
  },

  // Analysis (direct to backend — bypasses proxy timeout for long LLM calls)
  analyzeTranscript: (meetingId, reanalyze = false) =>
    directRequest(`/api/meetings/${meetingId}/analyze`, {
      method: 'POST',
      body: JSON.stringify({ reanalyze }),
    }),
  getSummary: (meetingId) => request(`/api/meetings/${meetingId}/summary`),

  // Quick Analyze (direct — LLM call can take 60+ seconds)
  quickAnalyze: (text, title, formatHint) =>
    directRequest('/api/quick-analyze', {
      method: 'POST',
      body: JSON.stringify({ text, title, format_hint: formatHint || undefined }),
    }),

  // Action items
  getActionItems: (meetingId, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/api/meetings/${meetingId}/action-items${query ? '?' + query : ''}`);
  },
  updateActionItem: (itemId, data) =>
    request(`/api/action-items/${itemId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  batchConfirm: (meetingId, itemIds) =>
    request(`/api/meetings/${meetingId}/action-items/batch-confirm`, {
      method: 'POST',
      body: JSON.stringify({ item_ids: itemIds }),
    }),
  batchReject: (meetingId, itemIds) =>
    request(`/api/meetings/${meetingId}/action-items/batch-reject`, {
      method: 'POST',
      body: JSON.stringify({ item_ids: itemIds }),
    }),

  // Settings
  getSetupStatus: () => request('/api/settings/setup-status'),
  getSettingsStatus: (token) =>
    request('/api/settings/status', { headers: { Authorization: `Bearer ${token}` } }),
  updateSettings: (token, data) =>
    request('/api/settings/update', {
      method: 'PUT',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    }),
  testKeys: (token) =>
    request('/api/settings/test-keys', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }),

  // Health
  checkKeys: () => request('/health/check-keys'),
  diagnostics: () => request('/health/diagnostics'),

  // Calendar
  getCalendarEvents: (daysAhead = 14) => request(`/api/calendar/events?days_ahead=${daysAhead}`),
  importCalendarEvent: (eventId) => directRequest(`/api/calendar/events/${eventId}/import`, { method: 'POST' }),
  getGoogleAuthStatus: () => request('/api/auth/google/status'),
  getGoogleAuthUrl: () => request('/api/auth/google'),

  // Documents
  suggestDocuments: (meetingId) => request(`/api/meetings/${meetingId}/documents/suggest`),
  approveDocuments: (meetingId, documents) =>
    request(`/api/meetings/${meetingId}/documents/approve-with-metadata`, {
      method: 'POST',
      body: JSON.stringify(documents),
    }),
  getMeetingDocuments: (meetingId) => request(`/api/meetings/${meetingId}/documents`),
  removeDocument: (meetingId, docId) =>
    request(`/api/meetings/${meetingId}/documents/${docId}`, { method: 'DELETE' }),

  // Briefing
  generateBriefing: (meetingId, format = 'json') =>
    request(`/api/meetings/${meetingId}/briefing`, {
      method: 'POST',
      body: JSON.stringify({ format }),
    }),

  // Minutes
  generateMinutes: (meetingId, format = 'json') =>
    directRequest(`/api/meetings/${meetingId}/minutes?format=${format}`, { method: 'POST' }),

  // Meeting list
  listMeetings: (page = 1, perPage = 50) => request(`/api/meetings?page=${page}&per_page=${perPage}`),
  getMeeting: (meetingId) => request(`/api/meetings/${meetingId}`),
};
