'use client';
import { useState, useCallback, useRef } from 'react';
import Header from '../../components/Header';
import { api } from '../../lib/api';
import {
  Sparkles, Upload, ClipboardPaste, Loader2, Check, X, ChevronDown,
  ChevronRight, Users, Lightbulb, ListChecks, Clock, RotateCcw,
  AlertCircle, FileUp, Quote,
} from 'lucide-react';

const SAMPLE = `Alice: Good morning everyone. Welcome to our Q2 planning meeting.
Bob: Thanks Alice. I have the revenue numbers ready to present.
Alice: Great, let's start with the revenue review.
Bob: Q1 revenue came in at 2.3 million, which is 12% above forecast. The main driver was enterprise deals.
Carol: That's excellent. I think we should increase our enterprise sales target for Q2.
Alice: Agreed. Let's set the Q2 target at 2.8 million. Bob, can you update the forecast by Friday?
Bob: Will do. I'll also need the updated pipeline data from the sales team.
Carol: I'll send that over by Wednesday.
Alice: Perfect. Next item - the hiring plan. We decided to open 3 new engineering positions.
Bob: I'll draft the job descriptions by next Monday.
Carol: And I need to get budget approval from finance. Should have that sorted by end of week.
Alice: Great. Last item - the product roadmap. Carol, any updates?
Carol: Yes, we've decided to prioritize the API integration feature for Q2. The design is ready.
Alice: Sounds good. Let's wrap up. Thanks everyone.`;

function Section({ title, icon: Icon, count, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-bgcard rounded-xl border border-bdr shadow-sm overflow-hidden">
      <button onClick={() => setOpen(!open)}
        className="w-full px-5 py-3.5 flex items-center justify-between hover:bg-bghover transition-colors cursor-pointer">
        <div className="flex items-center gap-2.5">
          {open ? <ChevronDown className="w-4 h-4 text-txttri" /> : <ChevronRight className="w-4 h-4 text-txttri" />}
          {Icon && <Icon className="w-4 h-4 text-txtsec" />}
          <span className="text-sm font-semibold text-txt">{title}</span>
          {count !== undefined && (
            <span className="text-xs bg-bgelev text-txtsec px-2 py-0.5 rounded-full">{count}</span>
          )}
        </div>
      </button>
      {open && <div className="px-5 pb-5">{children}</div>}
    </div>
  );
}

function ActionItemCard({ item, onConfirm, onDecline, onRestore }) {
  const isDeclined = item.rejected;
  return (
    <div className={`p-3.5 rounded-lg border transition-all ${
      isDeclined ? 'border-red/40 bg-redsoft opacity-70'
        : item.confirmed ? 'border-grn/30 bg-grnsoft'
          : 'border-bdr hover:bg-bghover'
    }`}>
      <div className="flex justify-between items-start gap-3">
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium leading-relaxed text-txt ${isDeclined ? 'line-through' : ''}`}>{item.task}</p>
          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
            {item.owner_name && <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blusoft text-blu">{item.owner_name}</span>}
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
              item.priority === 'high' ? 'bg-redsoft text-red' : item.priority === 'low' ? 'bg-grnsoft text-grn' : 'bg-ambsoft text-amb'
            }`}>{item.priority}</span>
            {item.confirmed && <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-grnsoft text-grn">Confirmed</span>}
            {isDeclined && <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-redsoft text-red">Declined</span>}
            {item.deadline && <span className="text-xs text-txttri">Due: {item.deadline}</span>}
          </div>
          {item.source_quote && (
            <div className="flex items-start gap-1.5 mt-2.5">
              <Quote className="w-4 h-4 text-txttri/30 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-txttri italic leading-relaxed">{item.source_quote}</p>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          {!item.confirmed && !isDeclined && (
            <>
              <button onClick={() => onConfirm(item.id)} title="Confirm"
                className="p-1.5 rounded-md hover:bg-grnsoft text-grn transition-colors">
                <Check className="w-4 h-4" />
              </button>
              <button onClick={() => onDecline(item.id)} title="Decline"
                className="p-1.5 rounded-md hover:bg-redsoft text-red transition-colors">
                <X className="w-4 h-4" />
              </button>
            </>
          )}
          {isDeclined && (
            <button onClick={() => onRestore(item.id)}
              className="px-2.5 py-1 rounded-md border border-bdr bg-bgelev text-xs font-medium text-txtsec hover:text-txt transition-colors">
              Restore
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, iconCls }) {
  return (
    <div className="bg-bgcard rounded-xl border border-bdr shadow-sm px-4 py-3.5 flex-1 min-w-0">
      <div className="flex items-center gap-2 mb-1.5">
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${iconCls}`}>
          <Icon className="w-3.5 h-3.5" />
        </div>
        <span className="text-xs text-txttri font-medium uppercase tracking-wider">{label}</span>
      </div>
      <span className="text-2xl font-bold tracking-tight text-txt">{value}</span>
    </div>
  );
}

function StepDot({ num, label, active, done }) {
  return (
    <div className="flex items-center gap-2">
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
        done ? 'bg-grn text-white' : active ? 'bg-acc text-white ring-4 ring-acc/15' : 'bg-bgelev text-txttri'
      }`}>
        {done ? <Check className="w-3.5 h-3.5" /> : num}
      </div>
      <span className={`text-sm font-medium ${active ? 'text-txt' : done ? 'text-grn' : 'text-txttri'}`}>{label}</span>
    </div>
  );
}

export default function AnalyzePage() {
  const [step, setStep] = useState('input');
  const [mode, setMode] = useState('paste');
  const [text, setText] = useState('');
  const [meetingId, setMeetingId] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

  const handleAnalyze = async (input) => {
    const t = input?.type === 'file' ? null : (input?.text || text);
    const f = input?.type === 'file' ? input.file : null;
    if (!t && !f) return;
    setLoading(true); setError(null); setStep('processing');
    try {
      setStatusText('Creating meeting...');
      const mtg = await api.createMeeting({ title: `Analysis — ${new Date().toLocaleDateString()}` });
      setMeetingId(mtg.id);
      setStatusText('Uploading transcript...');
      if (f) await api.uploadTranscriptFile(mtg.id, f);
      else await api.uploadTranscriptText(mtg.id, t);
      setStatusText('Running AI analysis...');
      const res = await api.analyzeTranscript(mtg.id);
      setAnalysis(res);
      setStatusText('Loading action items...');
      const ai = await api.getActionItems(mtg.id);
      setItems(ai.map(i => ({ ...i, rejected: false })));
      setStep('results');
    } catch (e) { setError(typeof e === 'string' ? e : (e?.message || JSON.stringify(e))); setStep('input'); }
    finally { setLoading(false); setStatusText(''); }
  };

  const handleConfirm = async (id) => { try { await api.updateActionItem(id, { confirmed: true }); setItems(p => p.map(i => i.id === id ? { ...i, confirmed: true, rejected: false } : i)); } catch {} };
  const handleDecline = (id) => setItems(p => p.map(i => i.id === id ? { ...i, rejected: true, confirmed: false } : i));
  const handleRestore = (id) => setItems(p => p.map(i => i.id === id ? { ...i, rejected: false, confirmed: false } : i));

  const handleReanalyze = async () => {
    if (!meetingId) return;
    setLoading(true); setStep('processing'); setStatusText('Re-analyzing...');
    try { const r = await api.analyzeTranscript(meetingId, true); setAnalysis(r); const ai = await api.getActionItems(meetingId); setItems(ai.map(i => ({ ...i, rejected: false }))); setStep('results'); }
    catch (e) { setError(e.message); } finally { setLoading(false); }
  };

  const startOver = () => { setStep('input'); setText(''); setMeetingId(null); setAnalysis(null); setItems([]); setError(null); };
  const handleDrop = useCallback((e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) handleAnalyze({ type: 'file', file: f }); }, []);
  const sn = step === 'input' ? 1 : step === 'processing' ? 2 : 3;

  return (
    <>
      <Header />
      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex items-center gap-6 mb-8">
          <StepDot num={1} label="Upload" active={sn===1} done={sn>1} />
          <div className="h-px w-8 bg-bdr" />
          <StepDot num={2} label="Analyze" active={sn===2} done={sn>2} />
          <div className="h-px w-8 bg-bdr" />
          <StepDot num={3} label="Results" active={sn===3} done={false} />
        </div>

        {error && (
          <div className="mb-6 p-4 bg-redsoft border border-red/20 rounded-xl flex items-start gap-3 animate-fade-in">
            <AlertCircle className="w-5 h-5 text-red flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red">Something went wrong</p>
              <p className="text-sm text-red/80 mt-0.5">{error}</p>
              <button onClick={() => setError(null)} className="text-xs text-red underline mt-2">Dismiss</button>
            </div>
          </div>
        )}

        {step === 'input' && (
          <div className="animate-fade-in">
            <div className="flex gap-1 mb-5 bg-bgelev rounded-xl p-1 w-fit">
              {[{ k: 'paste', icon: ClipboardPaste, l: 'Paste text' }, { k: 'file', icon: FileUp, l: 'Upload file' }].map(({ k, icon: I, l }) => (
                <button key={k} onClick={() => setMode(k)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-1.5 transition-all ${
                    mode === k ? 'bg-bgcard text-txt shadow-sm' : 'text-txtsec'
                  }`}><I className="w-4 h-4" /> {l}</button>
              ))}
            </div>

            {mode === 'paste' ? (
              <div>
                <textarea value={text} onChange={e => setText(e.target.value)}
                  placeholder="Paste your meeting transcript here..."
                  className="w-full h-64 p-4 bg-bgcard border border-bdr rounded-xl text-sm font-mono leading-relaxed text-txt placeholder:text-txttri focus:outline-none focus:ring-2 focus:ring-acc/20 focus:border-acc transition-all resize-none" />
                <div className="flex items-center justify-between mt-4">
                  <button onClick={() => setText(SAMPLE)} className="text-xs text-acc hover:text-acchov underline underline-offset-2 font-medium">Load sample transcript</button>
                  <div className="flex items-center gap-3">
                    {text && <span className="text-xs text-txttri">{text.split('\n').filter(l=>l.trim()).length} lines</span>}
                    <button onClick={() => handleAnalyze()} disabled={!text.trim()||loading}
                      className="px-5 py-2.5 bg-acc text-white rounded-xl font-semibold text-sm hover:bg-acchov transition-all inline-flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
                      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />} Analyze transcript
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div onDragOver={e=>{e.preventDefault();setDragOver(true);}} onDragLeave={()=>setDragOver(false)} onDrop={handleDrop} onClick={()=>fileRef.current?.click()}
                className={`h-52 border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-all ${
                  dragOver ? 'border-acc bg-accsoft' : 'border-bdr hover:border-txttri'
                }`}>
                <Upload className={`w-8 h-8 mb-3 ${dragOver ? 'text-acc' : 'text-txttri'}`} />
                <p className="text-sm font-medium text-txtsec">{dragOver ? 'Drop your file here' : 'Drag & drop or click to upload'}</p>
                <p className="text-xs text-txttri mt-1">SRT, VTT, CSV, JSON, TXT</p>
                <input ref={fileRef} type="file" className="hidden" accept=".srt,.vtt,.csv,.json,.txt,.text"
                  onChange={e=>{const f=e.target.files[0];if(f) handleAnalyze({type:'file',file:f});}} />
              </div>
            )}
          </div>
        )}

        {step === 'processing' && (
          <div className="flex flex-col items-center py-20 animate-fade-in">
            <Loader2 className="w-10 h-10 text-acc animate-spin mb-4" />
            <p className="text-sm font-semibold text-txt">{statusText || 'Processing...'}</p>
            <p className="text-xs text-txttri mt-1">Usually takes a few seconds</p>
          </div>
        )}

        {step === 'results' && analysis && (
          <div className="animate-fade-in space-y-4">
            <div className="flex gap-3">
              <StatCard icon={Users} label="Speakers" value={analysis.summary?.speakers?.length||0} iconCls="bg-blusoft text-blu" />
              <StatCard icon={Lightbulb} label="Decisions" value={analysis.summary?.decisions?.length||0} iconCls="bg-grnsoft text-grn" />
              <StatCard icon={ListChecks} label="Actions" value={items.length} iconCls="bg-accsoft text-acc" />
              <StatCard icon={Clock} label="Topics" value={analysis.summary?.topics?.length||0} iconCls="bg-ambsoft text-amb" />
            </div>

            <Section title="Executive Summary" icon={Sparkles}>
              <p className="font-serif text-[15px] leading-[1.75] text-txtsec whitespace-pre-line">{analysis.summary?.summary_text}</p>
            </Section>

            {analysis.summary?.decisions?.length > 0 && (
              <Section title="Key Decisions" icon={Lightbulb} count={analysis.summary.decisions.length}>
                <div className="space-y-3">
                  {analysis.summary.decisions.map((d,i) => (
                    <div key={i} className="flex gap-3 items-start">
                      <div className="w-6 h-6 rounded-full bg-grnsoft flex items-center justify-center flex-shrink-0 mt-0.5"><Check className="w-3 h-3 text-grn" /></div>
                      <div>
                        <p className="text-sm font-medium text-txt">{d.decision}</p>
                        {d.context && <p className="text-xs text-txttri mt-0.5">{d.context}</p>}
                        {d.made_by && <p className="text-xs text-txtsec mt-0.5 font-medium">Decision by {d.made_by}</p>}
                      </div>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            <Section title="Action Items" icon={ListChecks} count={items.length}>
              {items.length > 0 ? (
                <div className="space-y-2">
                  {items.map(item => <ActionItemCard key={item.id} item={item} onConfirm={handleConfirm} onDecline={handleDecline} onRestore={handleRestore} />)}
                </div>
              ) : <p className="text-sm text-txttri">No action items extracted.</p>}
            </Section>

            {analysis.summary?.topics?.length > 0 && (
              <Section title="Discussion Topics" icon={Clock} count={analysis.summary.topics.length} defaultOpen={false}>
                <div className="space-y-2">
                  {analysis.summary.topics.map((t,i) => (
                    <div key={i} className="flex gap-3 items-start">
                      <span className="font-mono text-xs text-txttri mt-0.5 w-4 text-right">{i+1}</span>
                      <div><p className="text-sm font-semibold text-txt">{t.topic}</p>{t.summary && <p className="text-xs text-txtsec mt-0.5">{t.summary}</p>}</div>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {analysis.summary?.speakers?.length > 0 && (
              <Section title="Speaker Contributions" icon={Users} count={analysis.summary.speakers.length} defaultOpen={false}>
                <div className="grid grid-cols-2 gap-2">
                  {analysis.summary.speakers.map((s,i) => {
                    const c = ['bg-blusoft text-blu','bg-accsoft text-acc','bg-grnsoft text-grn'];
                    return (
                      <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-bgelev">
                        <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold ${c[i%3]}`}>{s.name?.[0]||'?'}</div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-txt truncate">{s.name}</p>
                          <p className="text-xs text-txttri">{s.role||'Participant'} · {s.segment_count} turns</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Section>
            )}

            <div className="flex justify-center gap-3 pt-2">
              <button onClick={handleReanalyze} className="px-4 py-2 bg-bgcard text-txtsec rounded-lg border border-bdr text-xs font-medium hover:bg-bghover transition-all inline-flex items-center gap-1.5">
                <RotateCcw className="w-3.5 h-3.5" /> Re-analyze
              </button>
              <button onClick={startOver} className="px-4 py-2 bg-bgcard text-txtsec rounded-lg border border-bdr text-xs font-medium hover:bg-bghover transition-all">New analysis</button>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
