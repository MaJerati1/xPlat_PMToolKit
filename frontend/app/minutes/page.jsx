'use client';
import { useState, useEffect } from 'react';
import Header from '../../components/Header';
import { api } from '../../lib/api';
import { ClipboardList, Loader2, Download, FileText, ChevronDown, ChevronRight, AlertCircle, Sparkles, Users, ListChecks, Lightbulb, Clock } from 'lucide-react';

function MinutesSection({ section }) {
  const [open, setOpen] = useState(true);
  const iconMap = {
    'Meeting Details': Clock,
    'Attendees': Users,
    'Executive Summary': Sparkles,
    'Key Decisions': Lightbulb,
    'Discussion Topics': Clock,
    'Action Items': ListChecks,
    'Speaker Contributions': Users,
    'Next Steps': ClipboardList,
  };
  const Icon = iconMap[section.title] || FileText;

  return (
    <div className="bg-bgcard rounded-xl border border-bdr shadow-sm overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full px-5 py-3.5 flex items-center gap-2.5 hover:bg-bghover transition-colors cursor-pointer">
        {open ? <ChevronDown className="w-4 h-4 text-txttri" /> : <ChevronRight className="w-4 h-4 text-txttri" />}
        <Icon className="w-4 h-4 text-txtsec" />
        <span className="text-sm font-semibold text-txt">{section.title}</span>
      </button>
      {open && (
        <div className="px-5 pb-5">
          {section.content && <p className="text-sm text-txtsec mb-3 whitespace-pre-wrap leading-relaxed">{section.content}</p>}
          {section.table ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="bg-bgelev">
                    <th className="text-left p-2 font-semibold text-txt border border-bdr">Task</th>
                    <th className="text-left p-2 font-semibold text-txt border border-bdr">Owner</th>
                    <th className="text-left p-2 font-semibold text-txt border border-bdr">Deadline</th>
                    <th className="text-left p-2 font-semibold text-txt border border-bdr">Priority</th>
                    <th className="text-left p-2 font-semibold text-txt border border-bdr">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {section.table.map((row, i) => (
                    <tr key={i} className="hover:bg-bghover">
                      <td className="p-2 text-txt border border-bdr">{row.task}</td>
                      <td className="p-2 text-txtsec border border-bdr">{row.owner}</td>
                      <td className="p-2 text-txtsec border border-bdr">{row.deadline}</td>
                      <td className={`p-2 font-semibold border border-bdr ${row.priority==='high'?'text-red':row.priority==='low'?'text-grn':'text-amb'}`}>{row.priority}</td>
                      <td className="p-2 text-txtsec border border-bdr">{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : section.items?.length > 0 ? (
            <ul className="space-y-1.5">
              {section.items.map((item, i) => (
                <li key={i} className="text-sm text-txt flex items-start gap-2">
                  <span className="text-txttri mt-1">•</span>
                  <span className="leading-relaxed">{item}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      )}
    </div>
  );
}

export default function MinutesPage() {
  const [meetings, setMeetings] = useState([]);
  const [selectedMeeting, setSelectedMeeting] = useState(null);
  const [minutes, setMinutes] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listNamedMeetings(1, 50).then(data => setMeetings(data.meetings || [])).catch(() => {});
  }, []);

  const handleGenerate = async () => {
    if (!selectedMeeting) return;
    setLoading(true); setError(null); setMinutes(null);
    try {
      const data = await api.generateMinutes(selectedMeeting, 'json');
      setMinutes(data);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleDownload = async (format) => {
    if (!selectedMeeting) return;
    try {
      const resp = await fetch(`http://localhost:8000/api/meetings/${selectedMeeting}/minutes?format=${format}`, { method: 'POST' });
      const blob = await resp.blob();
      const ext = format === 'docx' ? 'docx' : 'pdf';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `minutes_${selectedMeeting}.${ext}`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setError(`Download failed: ${e.message}`); }
  };

  return (
    <><Header />
      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-txt mb-2">Meeting Minutes</h1>
          <p className="text-sm text-txtsec">Generate formal meeting minutes from analyzed transcripts. Export as Word or PDF.</p>
        </div>

        <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 mb-6">
          <label className="block text-sm font-semibold text-txt mb-2">Select an analyzed meeting</label>
          <select value={selectedMeeting || ''} onChange={e => { setSelectedMeeting(e.target.value); setMinutes(null); }}
            className="w-full px-3.5 py-2.5 bg-bgcard border border-bdr rounded-lg text-sm text-txt focus:outline-none focus:ring-2 focus:ring-acc/20 focus:border-acc">
            <option value="">Choose a meeting...</option>
            {meetings.map(m => (
              <option key={m.id} value={m.id}>{m.title}{m.date ? ` — ${m.date}` : ''}</option>
            ))}
          </select>
          <p className="text-xs text-txttri mt-2">The meeting must have been analyzed first (upload a transcript and run AI analysis).</p>
          <div className="flex gap-3 mt-4">
            <button onClick={handleGenerate} disabled={!selectedMeeting || loading}
              className="px-5 py-2.5 bg-acc text-white rounded-xl font-semibold text-sm hover:bg-acchov transition-all inline-flex items-center gap-2 disabled:opacity-50">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ClipboardList className="w-4 h-4" />}
              Generate Minutes
            </button>
            {minutes && (
              <>
                <button onClick={() => handleDownload('docx')}
                  className="px-4 py-2.5 bg-bgcard text-txt rounded-xl font-semibold text-sm border border-bdr hover:bg-bghover transition-all inline-flex items-center gap-2">
                  <Download className="w-4 h-4" /> Word
                </button>
                <button onClick={() => handleDownload('pdf')}
                  className="px-4 py-2.5 bg-bgcard text-txt rounded-xl font-semibold text-sm border border-bdr hover:bg-bghover transition-all inline-flex items-center gap-2">
                  <Download className="w-4 h-4" /> PDF
                </button>
              </>
            )}
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-redsoft border border-red/20 rounded-lg text-sm text-red flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" /> {error}
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center py-16">
            <Loader2 className="w-8 h-8 text-acc animate-spin mb-3" />
            <p className="text-sm text-txtsec">Generating minutes...</p>
          </div>
        )}

        {minutes && (
          <div className="space-y-3 animate-fade-in">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-serif text-xl font-semibold text-txt">{minutes.title}</h2>
              <span className="text-xs text-txttri">{new Date(minutes.generated_at).toLocaleString()}</span>
            </div>
            {minutes.sections?.map((section, i) => (
              <MinutesSection key={i} section={section} />
            ))}
            {minutes.metadata && (
              <div className="flex gap-3 justify-center pt-2 text-xs text-txttri flex-wrap">
                {minutes.metadata.llm_provider && <span>AI: {minutes.metadata.llm_provider}/{minutes.metadata.llm_model}</span>}
                {minutes.metadata.transcript_segments > 0 && <span>· {minutes.metadata.transcript_segments} transcript segments</span>}
                {minutes.metadata.decisions_count > 0 && <span>· {minutes.metadata.decisions_count} decisions</span>}
                {minutes.metadata.action_items_total > 0 && <span>· {minutes.metadata.action_items_total} action items ({minutes.metadata.action_items_confirmed} confirmed)</span>}
              </div>
            )}
          </div>
        )}
      </main>
    </>
  );
}
