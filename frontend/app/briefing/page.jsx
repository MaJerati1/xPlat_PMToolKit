'use client';
import { useState, useEffect } from 'react';
import Header from '../../components/Header';
import { api } from '../../lib/api';
import { FolderOpen, Loader2, Download, FileText, Users, ListChecks, Calendar, ChevronDown, ChevronRight, AlertCircle } from 'lucide-react';

function BriefingSection({ section }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="bg-bgcard rounded-xl border border-bdr shadow-sm overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full px-5 py-3.5 flex items-center gap-2.5 hover:bg-bghover transition-colors cursor-pointer">
        {open ? <ChevronDown className="w-4 h-4 text-txttri" /> : <ChevronRight className="w-4 h-4 text-txttri" />}
        <span className="text-sm font-semibold text-txt">{section.title}</span>
      </button>
      {open && (
        <div className="px-5 pb-5">
          {section.content && <p className="text-sm text-txtsec mb-3">{section.content}</p>}
          {section.items?.length > 0 && (
            <ul className="space-y-1.5">
              {section.items.map((item, i) => (
                <li key={i} className="text-sm text-txt flex items-start gap-2">
                  <span className="text-txttri mt-1">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export default function BriefingPage() {
  const [meetings, setMeetings] = useState([]);
  const [selectedMeeting, setSelectedMeeting] = useState(null);
  const [briefing, setBriefing] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listNamedMeetings(1, 50).then(data => {
      setMeetings(data.meetings || []);
    }).catch(() => {});
  }, []);

  const handleGenerate = async () => {
    if (!selectedMeeting) return;
    setLoading(true); setError(null); setBriefing(null);
    try {
      const data = await api.generateBriefing(selectedMeeting, 'json');
      setBriefing(data);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleDownloadDocx = async () => {
    if (!selectedMeeting) return;
    try {
      const resp = await fetch(`http://localhost:8000/api/meetings/${selectedMeeting}/briefing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format: 'docx' }),
      });
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `briefing_${selectedMeeting}.docx`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setError(`Download failed: ${e.message}`); }
  };

  return (
    <><Header />
      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-txt mb-2">Briefing Package</h1>
          <p className="text-sm text-txtsec">Generate a pre-meeting briefing with agenda, attendees, documents, and outstanding action items.</p>
        </div>

        <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 mb-6">
          <label className="block text-sm font-semibold text-txt mb-2">Select a meeting</label>
          <select value={selectedMeeting || ''} onChange={e => { setSelectedMeeting(e.target.value); setBriefing(null); }}
            className="w-full px-3.5 py-2.5 bg-bgcard border border-bdr rounded-lg text-sm text-txt focus:outline-none focus:ring-2 focus:ring-acc/20 focus:border-acc">
            <option value="">Choose a meeting...</option>
            {meetings.map(m => (
              <option key={m.id} value={m.id}>
                {m.title}{m.date ? ` — ${m.date}` : ''}
              </option>
            ))}
          </select>
          <div className="flex gap-3 mt-4">
            <button onClick={handleGenerate} disabled={!selectedMeeting || loading}
              className="px-5 py-2.5 bg-acc text-white rounded-xl font-semibold text-sm hover:bg-acchov transition-all inline-flex items-center gap-2 disabled:opacity-50">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FolderOpen className="w-4 h-4" />}
              Generate Briefing
            </button>
            {briefing && (
              <button onClick={handleDownloadDocx}
                className="px-5 py-2.5 bg-bgcard text-txt rounded-xl font-semibold text-sm border border-bdr hover:bg-bghover transition-all inline-flex items-center gap-2">
                <Download className="w-4 h-4" /> Download .docx
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-redsoft border border-red/20 rounded-lg text-sm text-red flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" /> {error}
          </div>
        )}

        {briefing && (
          <div className="space-y-3 animate-fade-in">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-serif text-xl font-semibold text-txt">{briefing.meeting_title}</h2>
              <span className="text-xs text-txttri">Generated: {new Date(briefing.generated_at).toLocaleString()}</span>
            </div>
            {briefing.sections?.map((section, i) => (
              <BriefingSection key={i} section={section} />
            ))}
            {briefing.metadata && (
              <div className="flex gap-3 justify-center pt-2 text-xs text-txttri">
                <span>{briefing.metadata.agenda_items_count} agenda items</span>
                <span>·</span>
                <span>{briefing.metadata.attendees_count} attendees</span>
                <span>·</span>
                <span>{briefing.metadata.documents_count} documents</span>
                <span>·</span>
                <span>{briefing.metadata.outstanding_actions_count} outstanding actions</span>
              </div>
            )}
          </div>
        )}
      </main>
    </>
  );
}
