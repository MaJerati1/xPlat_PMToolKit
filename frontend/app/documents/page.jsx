'use client';
import { useState, useEffect } from 'react';
import Header from '../../components/Header';
import { api } from '../../lib/api';
import { FileSearch, Loader2, Check, X, File, ExternalLink, AlertCircle, ChevronDown, Search } from 'lucide-react';

export default function DocumentsPage() {
  const [meetings, setMeetings] = useState([]);
  const [selectedMeeting, setSelectedMeeting] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [approved, setApproved] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listNamedMeetings(1, 50).then(data => {
      setMeetings(data.meetings?.filter(m => m.agenda_items?.length > 0) || []);
    }).catch(() => {});
  }, []);

  const handleSearch = async () => {
    if (!selectedMeeting) return;
    setSearching(true); setError(null); setSuggestions([]);
    try {
      const data = await api.suggestDocuments(selectedMeeting);
      setSuggestions(data.suggestions || []);
      setMessage(data.message);
      // Load existing approved docs
      const existing = await api.getMeetingDocuments(selectedMeeting);
      setApproved(existing.documents?.map(d => d.source_file_id) || []);
    } catch (e) { setError(e.message); }
    finally { setSearching(false); }
  };

  const handleApprove = async (doc) => {
    try {
      await api.approveDocuments(selectedMeeting, [doc]);
      setApproved(prev => [...prev, doc.file_id]);
    } catch (e) { setError(e.message); }
  };

  const mtg = meetings.find(m => m.id === selectedMeeting);

  return (
    <><Header />
      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-txt mb-2">Document Gathering</h1>
          <p className="text-sm text-txtsec">Search Google Drive for documents matching your meeting's agenda items.</p>
        </div>

        {/* Meeting Selector */}
        <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 mb-6">
          <label className="block text-sm font-semibold text-txt mb-2">Select a meeting</label>
          <select value={selectedMeeting || ''} onChange={e => { setSelectedMeeting(e.target.value); setSuggestions([]); }}
            className="w-full px-3.5 py-2.5 bg-bgcard border border-bdr rounded-lg text-sm text-txt focus:outline-none focus:ring-2 focus:ring-acc/20 focus:border-acc">
            <option value="">Choose a meeting with agenda items...</option>
            {meetings.map(m => (
              <option key={m.id} value={m.id}>
                {m.title}{m.date ? ` — ${m.date}` : ''} ({m.agenda_items?.length || 0} agenda items)
              </option>
            ))}
          </select>
          {mtg && (
            <div className="mt-3 text-xs text-txttri">
              Agenda: {mtg.agenda_items?.map(a => a.title).join(' · ')}
            </div>
          )}
          <button onClick={handleSearch} disabled={!selectedMeeting || searching}
            className="mt-4 px-5 py-2.5 bg-acc text-white rounded-xl font-semibold text-sm hover:bg-acchov transition-all inline-flex items-center gap-2 disabled:opacity-50">
            {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Search Google Drive
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-redsoft border border-red/20 rounded-lg text-sm text-red flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" /> {error}
          </div>
        )}

        {message && suggestions.length === 0 && !searching && (
          <div className="bg-bgcard rounded-xl border border-bdr p-8 text-center">
            <FileSearch className="w-8 h-8 text-txttri mx-auto mb-3" />
            <p className="text-sm text-txtsec">{message}</p>
          </div>
        )}

        {suggestions.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-txt mb-3">{suggestions.length} document(s) found</h3>
            <div className="space-y-2">
              {suggestions.map(doc => {
                const isApproved = approved.includes(doc.file_id);
                return (
                  <div key={doc.file_id} className={`bg-bgcard rounded-xl border shadow-sm p-4 flex items-center justify-between gap-4 transition-all ${
                    isApproved ? 'border-grn/30 bg-grnsoft' : 'border-bdr hover:shadow-md'
                  }`}>
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <File className="w-5 h-5 text-txtsec flex-shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-txt truncate">{doc.name}</p>
                        <div className="flex items-center gap-2 text-xs text-txttri mt-0.5 flex-wrap">
                          {doc.mime_type && <span>{doc.mime_type.split('.').pop()}</span>}
                          {doc.modified_time && <span>Modified: {doc.modified_time.split('T')[0]}</span>}
                          {doc.owners?.length > 0 && <span>By: {doc.owners[0]}</span>}
                          {doc.matched_keyword && <span className="px-1.5 py-0.5 bg-accsoft text-acc rounded text-[10px] font-medium">Matched: {doc.matched_keyword}</span>}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {doc.web_view_link && (
                        <a href={doc.web_view_link} target="_blank" rel="noopener noreferrer"
                          className="p-1.5 rounded-md text-txtsec hover:text-txt transition-colors" title="Open in Drive">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      )}
                      {isApproved ? (
                        <span className="px-3 py-1.5 bg-grnsoft text-grn rounded-lg text-xs font-semibold inline-flex items-center gap-1">
                          <Check className="w-3 h-3" /> Approved
                        </span>
                      ) : (
                        <button onClick={() => handleApprove(doc)}
                          className="px-3 py-1.5 bg-acc text-white rounded-lg text-xs font-semibold hover:bg-acchov transition-all">
                          Approve
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>
    </>
  );
}
