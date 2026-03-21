'use client';

import { useState, useCallback, useRef } from 'react';
import Link from 'next/link';
import {
  FileText, Upload, ClipboardPaste, Loader2, CheckCircle2, XCircle,
  ChevronDown, ChevronRight, Users, Lightbulb, ListChecks, Clock,
  Check, X, ArrowRight, RotateCcw, AlertCircle, Sparkles, FileUp,
} from 'lucide-react';
import { api } from '../../lib/api';

// ============================================
// STEP INDICATOR
// ============================================
function StepIndicator({ step, currentStep, label }) {
  const done = currentStep > step;
  const active = currentStep === step;
  return (
    <div className="flex items-center gap-2.5">
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-all duration-300 ${
        done ? 'bg-sage-500 text-white' :
        active ? 'bg-ocean-600 text-white ring-4 ring-ocean-100' :
        'bg-ink-100 text-ink-400'
      }`}>
        {done ? <Check className="w-3.5 h-3.5" /> : step}
      </div>
      <span className={`text-sm font-medium transition-colors ${
        active ? 'text-ink-900' : done ? 'text-sage-700' : 'text-ink-400'
      }`}>{label}</span>
    </div>
  );
}

// ============================================
// UPLOAD STEP
// ============================================
function UploadStep({ onUpload, loading }) {
  const [mode, setMode] = useState('paste'); // 'paste' or 'file'
  const [text, setText] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onUpload({ type: 'file', file });
  }, [onUpload]);

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) onUpload({ type: 'file', file });
  };

  const handlePaste = () => {
    if (text.trim()) onUpload({ type: 'text', text });
  };

  const sampleTranscript = `Alice: Good morning everyone. Welcome to our Q2 planning meeting.
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

  return (
    <div className="animate-fade-in">
      {/* Mode tabs */}
      <div className="flex gap-1 mb-5 bg-ink-100 rounded-lg p-1 w-fit">
        <button onClick={() => setMode('paste')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            mode === 'paste' ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-500 hover:text-ink-700'
          }`}>
          <ClipboardPaste className="w-4 h-4 inline mr-1.5 -mt-0.5" /> Paste text
        </button>
        <button onClick={() => setMode('file')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            mode === 'file' ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-500 hover:text-ink-700'
          }`}>
          <FileUp className="w-4 h-4 inline mr-1.5 -mt-0.5" /> Upload file
        </button>
      </div>

      {mode === 'paste' ? (
        <div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste your meeting transcript here..."
            className="w-full h-64 p-4 bg-white border border-ink-200 rounded-xl text-sm font-mono leading-relaxed
                       placeholder:text-ink-300 focus:outline-none focus:ring-2 focus:ring-ocean-200 focus:border-ocean-400
                       resize-none transition-all"
          />
          <div className="flex items-center justify-between mt-4">
            <button onClick={() => setText(sampleTranscript)}
              className="text-xs text-ocean-600 hover:text-ocean-700 underline underline-offset-2">
              Load sample transcript
            </button>
            <div className="flex items-center gap-3">
              <span className="text-xs text-ink-400">
                {text.length > 0 ? `${text.split('\n').length} lines, ${text.length.toLocaleString()} chars` : ''}
              </span>
              <button onClick={handlePaste} disabled={!text.trim() || loading} className="btn-primary inline-flex items-center gap-2">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                Analyze transcript
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
          className={`h-52 border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer
                     transition-all duration-200 ${
            dragOver ? 'border-ocean-400 bg-ocean-50' : 'border-ink-200 hover:border-ink-300 hover:bg-ink-50/50'
          }`}>
          <Upload className={`w-8 h-8 mb-3 ${dragOver ? 'text-ocean-500' : 'text-ink-300'}`} />
          <p className="text-sm font-medium text-ink-600">
            {dragOver ? 'Drop your file here' : 'Drag & drop or click to upload'}
          </p>
          <p className="text-xs text-ink-400 mt-1">Supports SRT, VTT, CSV, JSON, TXT</p>
          <input ref={fileRef} type="file" className="hidden"
            accept=".srt,.vtt,.csv,.json,.txt,.text" onChange={handleFileSelect} />
        </div>
      )}
    </div>
  );
}

// ============================================
// RESULTS DASHBOARD
// ============================================
function ResultsDashboard({ analysis, actionItems, meetingId, onReanalyze, onActionUpdate }) {
  const [expandedSections, setExpandedSections] = useState({
    summary: true, decisions: true, actions: true, topics: false, speakers: false,
  });

  const toggle = (section) => setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));

  const summary = analysis?.summary;
  if (!summary) return null;

  const handleConfirm = async (itemId) => {
    await api.updateActionItem(itemId, { confirmed: true });
    onActionUpdate();
  };

  const handleReject = async (itemId) => {
    await api.batchReject(meetingId, [itemId]);
    onActionUpdate();
  };

  const handleStatusChange = async (itemId, status) => {
    await api.updateActionItem(itemId, { status });
    onActionUpdate();
  };

  return (
    <div className="animate-fade-in space-y-4">
      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Speakers', value: summary.speakers?.length || 0, icon: Users, color: 'ocean' },
          { label: 'Decisions', value: summary.decisions?.length || 0, icon: Lightbulb, color: 'sage' },
          { label: 'Action items', value: actionItems?.length || 0, icon: ListChecks, color: 'ember' },
          { label: 'Topics', value: summary.topics?.length || 0, icon: Clock, color: 'ink' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <Icon className={`w-4 h-4 text-${color}-500`} />
              <span className="text-xs text-ink-400 font-medium">{label}</span>
            </div>
            <span className="text-2xl font-semibold text-ink-900">{value}</span>
          </div>
        ))}
      </div>

      {/* Summary section */}
      <Section title="Executive summary" expanded={expandedSections.summary}
        onToggle={() => toggle('summary')} badge={analysis.llm_provider}>
        <p className="text-sm text-ink-700 leading-relaxed whitespace-pre-line">{summary.summary_text}</p>
      </Section>

      {/* Decisions section */}
      {summary.decisions?.length > 0 && (
        <Section title="Key decisions" expanded={expandedSections.decisions}
          onToggle={() => toggle('decisions')} count={summary.decisions.length}>
          <div className="space-y-3">
            {summary.decisions.map((d, i) => (
              <div key={i} className="flex gap-3">
                <div className="w-6 h-6 bg-sage-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Lightbulb className="w-3.5 h-3.5 text-sage-600" />
                </div>
                <div>
                  <p className="text-sm text-ink-800 font-medium">{d.decision}</p>
                  {d.context && <p className="text-xs text-ink-400 mt-0.5">{d.context}</p>}
                  {d.made_by && <p className="text-xs text-ink-500 mt-0.5">Decision by: {d.made_by}</p>}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Action items section */}
      <Section title="Action items" expanded={expandedSections.actions}
        onToggle={() => toggle('actions')} count={actionItems?.length || 0}>
        {actionItems?.length > 0 ? (
          <div className="space-y-2">
            {actionItems.map((item) => (
              <div key={item.id} className={`p-3 rounded-lg border transition-all ${
                item.confirmed ? 'bg-sage-50/50 border-sage-200' : 'bg-white border-ink-200'
              }`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-ink-800">{item.task}</p>
                    <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                      {item.owner_name && (
                        <span className="badge bg-ink-100 text-ink-600">{item.owner_name}</span>
                      )}
                      <span className={`badge badge-${item.priority}`}>{item.priority}</span>
                      {item.confirmed && <span className="badge badge-confirmed">Confirmed</span>}
                      {item.status !== 'pending' && <span className={`badge badge-${item.status}`}>{item.status.replace('_', ' ')}</span>}
                    </div>
                    {item.source_quote && (
                      <p className="text-xs text-ink-400 mt-1.5 italic">"{item.source_quote}"</p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {!item.confirmed && (
                      <>
                        <button onClick={() => handleConfirm(item.id)}
                          title="Confirm"
                          className="p-1.5 rounded-md hover:bg-sage-100 text-sage-600 transition-colors">
                          <Check className="w-4 h-4" />
                        </button>
                        <button onClick={() => handleReject(item.id)}
                          title="Reject"
                          className="p-1.5 rounded-md hover:bg-ember-100 text-ember-500 transition-colors">
                          <X className="w-4 h-4" />
                        </button>
                      </>
                    )}
                    {item.confirmed && item.status === 'pending' && (
                      <button onClick={() => handleStatusChange(item.id, 'in_progress')}
                        className="text-xs text-ocean-600 hover:underline">
                        Start
                      </button>
                    )}
                    {item.status === 'in_progress' && (
                      <button onClick={() => handleStatusChange(item.id, 'completed')}
                        className="text-xs text-sage-600 hover:underline">
                        Complete
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-400">No action items extracted.</p>
        )}
      </Section>

      {/* Topics section */}
      {summary.topics?.length > 0 && (
        <Section title="Discussion topics" expanded={expandedSections.topics}
          onToggle={() => toggle('topics')} count={summary.topics.length}>
          <div className="space-y-2">
            {summary.topics.map((t, i) => (
              <div key={i} className="flex gap-3 items-start">
                <span className="text-xs text-ink-300 font-mono mt-0.5 w-4 text-right">{i + 1}</span>
                <div>
                  <p className="text-sm font-medium text-ink-800">{t.topic}</p>
                  {t.summary && <p className="text-xs text-ink-500 mt-0.5">{t.summary}</p>}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Speakers section */}
      {summary.speakers?.length > 0 && (
        <Section title="Speaker contributions" expanded={expandedSections.speakers}
          onToggle={() => toggle('speakers')} count={summary.speakers.length}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {summary.speakers.map((s, i) => (
              <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-ink-50/50">
                <div className="w-8 h-8 rounded-full bg-ocean-100 flex items-center justify-center text-xs font-semibold text-ocean-700">
                  {s.name?.charAt(0) || '?'}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-ink-800 truncate">{s.name}</p>
                  <p className="text-xs text-ink-400 truncate">{s.role || 'Participant'}</p>
                </div>
                {s.segment_count && (
                  <span className="text-xs text-ink-400">{s.segment_count} turns</span>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Re-analyze button */}
      <div className="flex justify-center pt-2">
        <button onClick={onReanalyze} className="btn-secondary inline-flex items-center gap-2 text-xs">
          <RotateCcw className="w-3.5 h-3.5" /> Re-analyze transcript
        </button>
      </div>
    </div>
  );
}

// ============================================
// COLLAPSIBLE SECTION
// ============================================
function Section({ title, children, expanded, onToggle, badge, count }) {
  return (
    <div className="card overflow-hidden">
      <button onClick={onToggle}
        className="w-full px-5 py-3.5 flex items-center justify-between hover:bg-ink-50/50 transition-colors">
        <div className="flex items-center gap-2.5">
          {expanded ? <ChevronDown className="w-4 h-4 text-ink-400" /> : <ChevronRight className="w-4 h-4 text-ink-400" />}
          <span className="text-sm font-semibold text-ink-800">{title}</span>
          {count !== undefined && (
            <span className="text-xs bg-ink-100 text-ink-500 px-2 py-0.5 rounded-full">{count}</span>
          )}
        </div>
        {badge && <span className="text-xs text-ink-400">{badge}</span>}
      </button>
      {expanded && <div className="px-5 pb-4">{children}</div>}
    </div>
  );
}

// ============================================
// MAIN PAGE
// ============================================
export default function AnalyzePage() {
  const [step, setStep] = useState(1); // 1=upload, 2=processing, 3=results
  const [meetingId, setMeetingId] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [actionItems, setActionItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('');

  const handleUpload = async (input) => {
    setLoading(true);
    setError(null);
    setStep(2);

    try {
      // Step 1: Create a meeting
      setStatusText('Creating meeting...');
      const meeting = await api.createMeeting({ title: `Transcript Analysis — ${new Date().toLocaleDateString()}` });
      setMeetingId(meeting.id);

      // Step 2: Upload transcript
      setStatusText('Uploading transcript...');
      if (input.type === 'file') {
        await api.uploadTranscriptFile(meeting.id, input.file);
      } else {
        await api.uploadTranscriptText(meeting.id, input.text);
      }

      // Step 3: Run analysis
      setStatusText('Analyzing with AI...');
      const result = await api.analyzeTranscript(meeting.id);
      setAnalysis(result);

      // Step 4: Get action items
      setStatusText('Extracting action items...');
      const items = await api.getActionItems(meeting.id);
      setActionItems(items);

      setStep(3);
    } catch (err) {
      setError(err.message);
      setStep(1);
    } finally {
      setLoading(false);
      setStatusText('');
    }
  };

  const refreshActionItems = async () => {
    if (!meetingId) return;
    const items = await api.getActionItems(meetingId);
    setActionItems(items);
  };

  const handleReanalyze = async () => {
    if (!meetingId) return;
    setLoading(true);
    setStep(2);
    setStatusText('Re-analyzing...');
    try {
      const result = await api.analyzeTranscript(meetingId, true);
      setAnalysis(result);
      const items = await api.getActionItems(meetingId);
      setActionItems(items);
      setStep(3);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setStatusText('');
    }
  };

  const handleStartOver = () => {
    setStep(1);
    setMeetingId(null);
    setAnalysis(null);
    setActionItems([]);
    setError(null);
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-ink-200/60 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-ocean-600 rounded-lg flex items-center justify-center">
              <FileText className="w-4 h-4 text-white" />
            </div>
            <span className="font-display text-xl text-ink-900">Meeting Toolkit</span>
          </Link>
          {step === 3 && (
            <button onClick={handleStartOver} className="btn-secondary text-xs">
              New analysis
            </button>
          )}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        {/* Step indicator */}
        <div className="flex items-center gap-6 mb-8">
          <StepIndicator step={1} currentStep={step} label="Upload" />
          <div className="h-px w-8 bg-ink-200" />
          <StepIndicator step={2} currentStep={step} label="Analyze" />
          <div className="h-px w-8 bg-ink-200" />
          <StepIndicator step={3} currentStep={step} label="Results" />
        </div>

        {/* Error banner */}
        {error && (
          <div className="mb-6 p-4 bg-ember-50 border border-ember-200 rounded-xl flex items-start gap-3 animate-fade-in">
            <AlertCircle className="w-5 h-5 text-ember-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-ember-800">Something went wrong</p>
              <p className="text-sm text-ember-600 mt-0.5">{error}</p>
              <button onClick={() => setError(null)} className="text-xs text-ember-700 underline mt-2">Dismiss</button>
            </div>
          </div>
        )}

        {/* Step content */}
        {step === 1 && <UploadStep onUpload={handleUpload} loading={loading} />}

        {step === 2 && (
          <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
            <Loader2 className="w-10 h-10 text-ocean-500 animate-spin mb-4" />
            <p className="text-sm font-medium text-ink-700">{statusText || 'Processing...'}</p>
            <p className="text-xs text-ink-400 mt-1">This usually takes a few seconds</p>
          </div>
        )}

        {step === 3 && (
          <ResultsDashboard
            analysis={analysis}
            actionItems={actionItems}
            meetingId={meetingId}
            onReanalyze={handleReanalyze}
            onActionUpdate={refreshActionItems}
          />
        )}
      </main>
    </div>
  );
}
