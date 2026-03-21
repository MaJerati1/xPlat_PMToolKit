'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  FileText, Loader2, CheckCircle2, Users, Lightbulb, ListChecks,
  Clock, Check, X, Sparkles, ArrowLeft, Copy, ChevronDown, ChevronRight,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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

function Section({ title, icon: Icon, color, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-ink-200/60 rounded-xl bg-white overflow-hidden">
      <button onClick={() => setOpen(!open)}
        className="w-full px-5 py-3 flex items-center gap-2.5 hover:bg-ink-50/50 transition-colors">
        {open ? <ChevronDown className="w-4 h-4 text-ink-400" /> : <ChevronRight className="w-4 h-4 text-ink-400" />}
        <Icon className={`w-4 h-4 text-${color}-500`} />
        <span className="text-sm font-semibold text-ink-800">{title}</span>
      </button>
      {open && <div className="px-5 pb-4">{children}</div>}
    </div>
  );
}

export default function QuickPage() {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const analyze = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/quick-analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error: ${res.status}`);
      }
      setResult(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => { setResult(null); setText(''); setError(null); };

  return (
    <div className="min-h-screen bg-ink-50">
      {/* Header */}
      <header className="border-b border-ink-200/60 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-ocean-600 rounded-lg flex items-center justify-center">
              <FileText className="w-4 h-4 text-white" />
            </div>
            <span className="font-display text-xl text-ink-900">Quick Analyze</span>
          </Link>
          <Link href="/analyze" className="text-xs text-ink-500 hover:text-ink-700 flex items-center gap-1">
            <ArrowLeft className="w-3 h-3" /> Full toolkit
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        {!result ? (
          /* ===== INPUT VIEW ===== */
          <div className="animate-fade-in">
            <div className="text-center mb-8">
              <h1 className="font-display text-3xl text-ink-950 mb-2">
                Paste a transcript, get <span className="text-ocean-600 italic">instant insights</span>
              </h1>
              <p className="text-sm text-ink-500">No setup, no accounts, no meeting context needed.</p>
            </div>

            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste your meeting transcript here..."
              className="w-full h-72 p-5 bg-white border border-ink-200 rounded-xl text-sm font-mono leading-relaxed
                         placeholder:text-ink-300 focus:outline-none focus:ring-2 focus:ring-ocean-200 focus:border-ocean-400
                         resize-none transition-all shadow-sm"
            />

            <div className="flex items-center justify-between mt-4">
              <button onClick={() => setText(SAMPLE)}
                className="text-xs text-ocean-600 hover:text-ocean-700 underline underline-offset-2">
                Load sample transcript
              </button>
              <div className="flex items-center gap-3">
                {text.length > 0 && (
                  <span className="text-xs text-ink-400">
                    {text.split('\n').filter(l => l.trim()).length} lines
                  </span>
                )}
                <button onClick={analyze} disabled={!text.trim() || loading}
                  className="btn-primary inline-flex items-center gap-2">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  {loading ? 'Analyzing...' : 'Analyze'}
                </button>
              </div>
            </div>

            {error && (
              <div className="mt-4 p-3 bg-ember-50 border border-ember-200 rounded-lg text-sm text-ember-700">
                {error}
              </div>
            )}

            <div className="mt-10 text-center">
              <p className="text-xs text-ink-400">
                Supports plain text, SRT, VTT, CSV, and JSON transcript formats.
                Format is auto-detected.
              </p>
            </div>
          </div>
        ) : (
          /* ===== RESULTS VIEW ===== */
          <div className="animate-fade-in">
            {/* Status bar */}
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-sage-500" />
                <span className="text-sm font-medium text-ink-700">Analysis complete</span>
                <span className="text-xs text-ink-400">
                  {result.transcript_info?.segments} segments, {result.transcript_info?.speakers} speakers
                  {result.llm_provider && ` · ${result.llm_provider}`}
                </span>
              </div>
              <button onClick={reset} className="btn-secondary text-xs">New analysis</button>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-4 gap-3 mb-5">
              {[
                { label: 'Speakers', value: result.speakers?.length || 0, icon: Users, color: 'ocean' },
                { label: 'Decisions', value: result.decisions?.length || 0, icon: Lightbulb, color: 'sage' },
                { label: 'Action items', value: result.action_items?.length || 0, icon: ListChecks, color: 'ember' },
                { label: 'Topics', value: result.topics?.length || 0, icon: Clock, color: 'ink' },
              ].map(({ label, value, icon: Icon, color }) => (
                <div key={label} className="bg-white rounded-xl border border-ink-200/60 px-4 py-3 shadow-sm">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Icon className={`w-3.5 h-3.5 text-${color}-500`} />
                    <span className="text-xs text-ink-400">{label}</span>
                  </div>
                  <span className="text-xl font-semibold text-ink-900">{value}</span>
                </div>
              ))}
            </div>

            <div className="space-y-4">
              {/* Summary */}
              {result.summary?.text && (
                <Section title="Executive summary" icon={FileText} color="ocean">
                  <p className="text-sm text-ink-700 leading-relaxed whitespace-pre-line">
                    {result.summary.text}
                  </p>
                </Section>
              )}

              {/* Decisions */}
              {result.decisions?.length > 0 && (
                <Section title={`Key decisions (${result.decisions.length})`} icon={Lightbulb} color="sage">
                  <div className="space-y-2.5">
                    {result.decisions.map((d, i) => (
                      <div key={i} className="flex gap-3">
                        <div className="w-5 h-5 bg-sage-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                          <Check className="w-3 h-3 text-sage-600" />
                        </div>
                        <div>
                          <p className="text-sm text-ink-800">{d.decision}</p>
                          {d.made_by && <p className="text-xs text-ink-400 mt-0.5">By: {d.made_by}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {/* Action Items */}
              {result.action_items?.length > 0 && (
                <Section title={`Action items (${result.action_items.length})`} icon={ListChecks} color="ember">
                  <div className="space-y-2">
                    {result.action_items.map((item, i) => (
                      <div key={i} className="p-3 rounded-lg border border-ink-200 bg-ink-50/30">
                        <p className="text-sm text-ink-800">{item.task}</p>
                        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                          {item.owner && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-ink-100 text-ink-600">
                              {item.owner}
                            </span>
                          )}
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                            item.priority === 'high' ? 'bg-ember-50 text-ember-700' :
                            item.priority === 'low' ? 'bg-sage-50 text-sage-700' :
                            'bg-ocean-50 text-ocean-700'
                          }`}>{item.priority}</span>
                          {item.deadline && (
                            <span className="text-xs text-ink-400">Due: {item.deadline}</span>
                          )}
                        </div>
                        {item.source_quote && (
                          <p className="text-xs text-ink-400 mt-1.5 italic">"{item.source_quote}"</p>
                        )}
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {/* Topics */}
              {result.topics?.length > 0 && (
                <Section title={`Discussion topics (${result.topics.length})`} icon={Clock} color="ink" defaultOpen={false}>
                  <div className="space-y-2">
                    {result.topics.map((t, i) => (
                      <div key={i} className="flex gap-2.5">
                        <span className="text-xs text-ink-300 font-mono mt-0.5 w-4 text-right">{i + 1}</span>
                        <div>
                          <p className="text-sm font-medium text-ink-800">{t.topic}</p>
                          {t.summary && <p className="text-xs text-ink-500">{t.summary}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {/* Speakers */}
              {result.speakers?.length > 0 && (
                <Section title={`Speakers (${result.speakers.length})`} icon={Users} color="ocean" defaultOpen={false}>
                  <div className="grid grid-cols-2 gap-2">
                    {result.speakers.map((s, i) => (
                      <div key={i} className="flex items-center gap-2.5 p-2.5 rounded-lg bg-ink-50/50">
                        <div className="w-7 h-7 rounded-full bg-ocean-100 flex items-center justify-center text-xs font-semibold text-ocean-700">
                          {s.name?.charAt(0) || '?'}
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-ink-800 truncate">{s.name}</p>
                          <p className="text-xs text-ink-400">{s.role || 'Participant'}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </Section>
              )}
            </div>

            {/* Follow-up note */}
            <div className="mt-8 p-4 bg-ocean-50/50 border border-ocean-200/50 rounded-xl text-center">
              <p className="text-xs text-ocean-700">
                Want to manage action items, re-analyze, or generate minutes?{' '}
                <Link href={`/analyze`} className="underline underline-offset-2 font-medium">
                  Use the full toolkit
                </Link>
                {' '}with meeting ID: <code className="bg-ocean-100 px-1.5 py-0.5 rounded text-xs font-mono">{result.meeting_id}</code>
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
