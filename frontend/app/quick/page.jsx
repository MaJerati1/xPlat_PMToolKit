'use client';
import { useState, useRef } from 'react';
import Header from '../../components/Header';
import { api } from '../../lib/api';
import { Sparkles, Loader2, CheckCircle2, Users, Lightbulb, ListChecks, Clock, Check, ChevronDown, ChevronRight, Quote, Upload, ClipboardPaste, FileUp, Download } from 'lucide-react';

const SAMPLE = `Alice: Good morning everyone. Welcome to our Q2 planning meeting.
Bob: Thanks Alice. I have the revenue numbers ready to present.
Alice: Great, let's start with the revenue review.
Bob: Q1 revenue came in at 2.3 million, which is 12% above forecast.
Carol: That's excellent. I think we should increase our target for Q2.
Alice: Agreed. Bob, can you update the forecast by Friday?
Bob: Will do. I'll need the pipeline data from sales.
Carol: I'll send that by Wednesday.
Alice: Next - hiring. We decided to open 3 engineering positions.
Bob: I'll draft job descriptions by Monday.
Carol: I need budget approval from finance by end of week.
Alice: Sounds good. Let's wrap up. Thanks everyone.`;

function Section({ title, icon: Icon, count, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-bgcard rounded-xl border border-bdr shadow-sm overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full px-5 py-3.5 flex items-center gap-2.5 hover:bg-bghover transition-colors cursor-pointer">
        {open ? <ChevronDown className="w-4 h-4 text-txttri" /> : <ChevronRight className="w-4 h-4 text-txttri" />}
        {Icon && <Icon className="w-4 h-4 text-txtsec" />}
        <span className="text-sm font-semibold text-txt">{title}</span>
        {count !== undefined && <span className="text-xs bg-bgelev text-txtsec px-2 py-0.5 rounded-full">{count}</span>}
      </button>
      {open && <div className="px-5 pb-5">{children}</div>}
    </div>
  );
}

export default function QuickPage() {
  const [text, setText] = useState('');
  const [mode, setMode] = useState('paste');
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

  const analyzeText = async () => {
    if (!text.trim()) return;
    setLoading(true); setError(null); setResult(null);
    setStatusText('Analyzing transcript...');
    try { setResult(await api.quickAnalyze(text)); }
    catch (e) { setError(typeof e === 'string' ? e : (e?.message || JSON.stringify(e))); }
    finally { setLoading(false); setStatusText(''); }
  };

  const analyzeFile = async (file) => {
    setLoading(true); setError(null); setResult(null);
    setStatusText(`Uploading ${file.name}...`);
    try { setResult(await api.quickAnalyzeFile(file)); }
    catch (e) { setError(typeof e === 'string' ? e : (e?.message || JSON.stringify(e))); }
    finally { setLoading(false); setStatusText(''); }
  };

  const handleDrop = (e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) analyzeFile(f); };
  const reset = () => { setResult(null); setText(''); setError(null); };

  const handleDownload = async (format) => {
    if (!result?.meeting_id) return;
    try {
      const resp = await fetch(`http://localhost:8000/api/meetings/${result.meeting_id}/minutes?format=${format}`, { method: 'POST' });
      if (!resp.ok) throw new Error(`Download failed: ${resp.status}`);
      const blob = await resp.blob();
      const ext = format === 'docx' ? 'docx' : 'pdf';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `quick_analysis.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setError(`Download failed: ${e.message}`); }
  };

  if (loading) {
    return (
      <><Header />
        <div className="flex flex-col items-center justify-center py-32 animate-fade-in">
          <Loader2 className="w-10 h-10 text-acc animate-spin mb-4" />
          <p className="text-sm font-semibold text-txt">{statusText || 'Processing...'}</p>
          <p className="text-xs text-txttri mt-1">Usually takes a few seconds</p>
        </div>
      </>
    );
  }

  return (
    <>
      <Header />
      <main className="max-w-3xl mx-auto px-6 py-8">
        {!result ? (
          <div className="animate-fade-in">
            <div className="text-center mb-8">
              <h1 className="font-serif text-3xl font-semibold tracking-tight text-txt mb-2">Paste a transcript, get <span className="text-acc italic">instant insights</span></h1>
              <p className="text-sm text-txtsec">No setup, no accounts, no meeting context needed.</p>
            </div>

            {/* Mode tabs */}
            <div className="flex gap-1 mb-5 bg-bgelev rounded-xl p-1 w-fit mx-auto">
              {[{ k: 'paste', icon: ClipboardPaste, l: 'Paste text' }, { k: 'file', icon: FileUp, l: 'Upload file' }].map(({ k, icon: I, l }) => (
                <button key={k} onClick={() => setMode(k)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-1.5 transition-all ${
                    mode === k ? 'bg-bgcard text-txt shadow-sm' : 'text-txtsec'
                  }`}><I className="w-4 h-4" /> {l}</button>
              ))}
            </div>

            {mode === 'paste' ? (
              <>
                <textarea value={text} onChange={e => setText(e.target.value)} placeholder="Paste your meeting transcript here..."
                  className="w-full h-72 p-5 bg-bgcard border border-bdr rounded-xl text-sm font-mono leading-relaxed text-txt placeholder:text-txttri focus:outline-none focus:ring-2 focus:ring-acc/20 focus:border-acc transition-all resize-none shadow-sm" />
                <div className="flex items-center justify-between mt-4">
                  <button onClick={() => setText(SAMPLE)} className="text-xs text-acc hover:text-acchov underline underline-offset-2 font-medium">Load sample transcript</button>
                  <div className="flex items-center gap-3">
                    {text && <span className="text-xs text-txttri">{text.split('\n').filter(l=>l.trim()).length} lines</span>}
                    <button onClick={analyzeText} disabled={!text.trim()}
                      className="px-5 py-2.5 bg-acc text-white rounded-xl font-semibold text-sm hover:bg-acchov transition-all inline-flex items-center gap-2 disabled:opacity-50">
                      <Sparkles className="w-4 h-4" /> Analyze
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
                className={`h-52 border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-all ${
                  dragOver ? 'border-acc bg-accsoft' : 'border-bdr hover:border-txttri'
                }`}>
                <Upload className={`w-8 h-8 mb-3 ${dragOver ? 'text-acc' : 'text-txttri'}`} />
                <p className="text-sm font-medium text-txtsec">{dragOver ? 'Drop your file here' : 'Drag & drop or click to upload'}</p>
                <p className="text-xs text-txttri mt-1">SRT, VTT, CSV, JSON, TXT</p>
                <input ref={fileRef} type="file" className="hidden" accept=".srt,.vtt,.csv,.json,.txt,.text"
                  onChange={e => { const f = e.target.files[0]; if (f) analyzeFile(f); }} />
              </div>
            )}

            {error && <div className="mt-4 p-3 bg-redsoft border border-red/20 rounded-lg text-sm text-red">{error}</div>}
            <p className="mt-10 text-center text-xs text-txttri">Supports plain text, SRT, VTT, CSV, and JSON. Format is auto-detected.</p>
          </div>
        ) : (
          <div className="animate-fade-in space-y-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-grn" />
                <span className="text-sm font-medium text-txt">Analysis complete</span>
                <span className="text-xs text-txttri">{result.transcript_info?.segments} segments · {result.llm_provider||'mock'}</span>
              </div>
              <button onClick={reset} className="px-4 py-2 bg-bgcard text-txtsec rounded-lg border border-bdr text-xs font-medium hover:bg-bghover transition-all">New analysis</button>
            </div>
            <div className="grid grid-cols-4 gap-3">
              {[{i:Users,l:'Speakers',v:result.speakers?.length||0,c:'bg-blusoft text-blu'},{i:Lightbulb,l:'Decisions',v:result.decisions?.length||0,c:'bg-grnsoft text-grn'},{i:ListChecks,l:'Actions',v:result.action_items?.length||0,c:'bg-accsoft text-acc'},{i:Clock,l:'Topics',v:result.topics?.length||0,c:'bg-ambsoft text-amb'}].map(({i:I,l,v,c})=>(
                <div key={l} className="bg-bgcard rounded-xl border border-bdr shadow-sm px-4 py-3">
                  <div className="flex items-center gap-1.5 mb-1"><div className={`w-6 h-6 rounded-md flex items-center justify-center ${c}`}><I className="w-3 h-3" /></div><span className="text-xs text-txttri">{l}</span></div>
                  <span className="text-xl font-bold text-txt">{v}</span>
                </div>
              ))}
            </div>
            {/* Export buttons */}
            <div className="flex items-center gap-2">
              <button onClick={() => handleDownload('docx')}
                className="px-3.5 py-1.5 bg-bgcard text-txt rounded-lg text-xs font-semibold border border-bdr hover:bg-bghover transition-all inline-flex items-center gap-1.5">
                <Download className="w-3.5 h-3.5" /> Save as Word
              </button>
              <button onClick={() => handleDownload('pdf')}
                className="px-3.5 py-1.5 bg-bgcard text-txt rounded-lg text-xs font-semibold border border-bdr hover:bg-bghover transition-all inline-flex items-center gap-1.5">
                <Download className="w-3.5 h-3.5" /> Save as PDF
              </button>
            </div>
            {result.summary?.text && <Section title="Executive Summary" icon={Sparkles}><p className="font-serif text-[15px] leading-[1.75] text-txtsec whitespace-pre-line">{result.summary.text}</p></Section>}
            {result.decisions?.length > 0 && (
              <Section title="Key Decisions" icon={Lightbulb} count={result.decisions.length}>
                <div className="space-y-2.5">{result.decisions.map((d,i)=>(
                  <div key={i} className="flex gap-3"><div className="w-5 h-5 rounded-full bg-grnsoft flex items-center justify-center flex-shrink-0 mt-0.5"><Check className="w-3 h-3 text-grn" /></div><div><p className="text-sm font-medium text-txt">{d.decision}</p>{d.made_by && <p className="text-xs text-txttri mt-0.5">By: {d.made_by}</p>}</div></div>
                ))}</div>
              </Section>
            )}
            {result.action_items?.length > 0 && (
              <Section title="Action Items" icon={ListChecks} count={result.action_items.length}>
                <div className="space-y-2">{result.action_items.map((item,i)=>(
                  <div key={i} className="p-3 rounded-lg border border-bdr bg-bgelev/30">
                    <p className="text-sm font-medium text-txt">{item.task}</p>
                    <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                      {(item.owner||item.owner_name) && <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blusoft text-blu">{item.owner||item.owner_name}</span>}
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${item.priority==='high'?'bg-redsoft text-red':item.priority==='low'?'bg-grnsoft text-grn':'bg-ambsoft text-amb'}`}>{item.priority}</span>
                    </div>
                    {item.source_quote && <div className="flex items-start gap-1.5 mt-2"><Quote className="w-3.5 h-3.5 text-txttri/30 flex-shrink-0 mt-0.5" /><p className="text-xs text-txttri italic">{item.source_quote}</p></div>}
                  </div>
                ))}</div>
              </Section>
            )}
            {result.topics?.length > 0 && <Section title="Topics" icon={Clock} count={result.topics.length} defaultOpen={false}><div className="space-y-2">{result.topics.map((t,i)=>(<div key={i} className="flex gap-2.5"><span className="font-mono text-xs text-txttri mt-0.5 w-4 text-right">{i+1}</span><div><p className="text-sm font-semibold text-txt">{t.topic}</p>{t.summary&&<p className="text-xs text-txtsec">{t.summary}</p>}</div></div>))}</div></Section>}
            {result.speakers?.length > 0 && <Section title="Speakers" icon={Users} count={result.speakers.length} defaultOpen={false}><div className="grid grid-cols-2 gap-2">{result.speakers.map((s,i)=>(<div key={i} className="flex items-center gap-2.5 p-2.5 rounded-lg bg-bgelev"><div className="w-7 h-7 rounded-full bg-blusoft flex items-center justify-center text-xs font-bold text-blu">{s.name?.[0]||'?'}</div><div className="min-w-0"><p className="text-sm font-medium text-txt truncate">{s.name}</p><p className="text-xs text-txttri">{s.role||'Participant'}</p></div></div>))}</div></Section>}
            <div className="mt-6 p-4 bg-blusoft border border-blu/10 rounded-xl text-center">
              <p className="text-xs text-blu">Want to manage action items or re-analyze? <a href="/analyze" className="underline underline-offset-2 font-medium">Use the full toolkit</a></p>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
