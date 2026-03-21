/**
 * API client for the Meeting Toolkit backend.
 * Handles all communication with the FastAPI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `API error: ${res.status}`);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Meetings
  createMeeting: (data) => request('/api/meetings', { method: 'POST', body: JSON.stringify(data) }),
  getMeeting: (id) => request(`/api/meetings/${id}`),
  listMeetings: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/api/meetings${query ? '?' + query : ''}`);
  },

  // Transcript upload (JSON body)
  uploadTranscriptText: (meetingId, text, formatHint) =>
    request(`/api/meetings/${meetingId}/transcript/text`, {
      method: 'POST',
      body: JSON.stringify({ text, format_hint: formatHint || undefined }),
    }),

  // Transcript upload (multipart form — for file upload)
  uploadTranscriptFile: async (meetingId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    const url = `${API_BASE}/api/meetings/${meetingId}/transcript`;
    const res = await fetch(url, { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Upload failed: ${res.status}`);
    }
    return res.json();
  },

  // Transcript status and segments
  getTranscriptStatus: (meetingId) => request(`/api/meetings/${meetingId}/transcript/status`),
  getTranscriptSegments: (meetingId) => request(`/api/meetings/${meetingId}/transcript/segments`),
  deleteTranscript: (meetingId) => request(`/api/meetings/${meetingId}/transcript`, { method: 'DELETE' }),

  // Analysis
  analyzeTranscript: (meetingId, reanalyze = false) =>
    request(`/api/meetings/${meetingId}/analyze`, {
      method: 'POST',
      body: JSON.stringify({ reanalyze }),
    }),
  getSummary: (meetingId) => request(`/api/meetings/${meetingId}/summary`),

  // Action items
  extractActionItems: (meetingId, replaceExisting = false) =>
    request(`/api/meetings/${meetingId}/extract-actions`, {
      method: 'POST',
      body: JSON.stringify({ replace_existing: replaceExisting }),
    }),
  getActionItems: (meetingId, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/api/meetings/${meetingId}/action-items${query ? '?' + query : ''}`);
  },
  getActionItemSummary: (meetingId) => request(`/api/meetings/${meetingId}/action-items/summary`),
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
};
