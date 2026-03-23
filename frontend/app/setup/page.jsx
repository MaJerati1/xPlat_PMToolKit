'use client';
import { useState, useEffect } from 'react';
import Header from '../../components/Header';
import { api } from '../../lib/api';
import { Sparkles, Loader2, Check, Key, Server, Calendar, Shield, AlertTriangle, Copy, CheckCircle2, XCircle, Minus, ArrowRight, Cpu } from 'lucide-react';

function StatusDot({ status, detail }) {
  if (!status) return null;
  const map = { valid: { icon: CheckCircle2, cls: 'text-grn' }, invalid: { icon: XCircle, cls: 'text-red' }, error: { icon: XCircle, cls: 'text-red' }, not_configured: { icon: Minus, cls: 'text-txttri' }, unreachable: { icon: XCircle, cls: 'text-amb' } };
  const { icon: Icon, cls } = map[status] || map.not_configured;
  const labels = { valid: 'Connected', invalid: 'Invalid key', error: 'Error', not_configured: 'Not set', unreachable: 'Unreachable' };
  return <span className={`flex items-center gap-1.5 mt-1 text-xs font-semibold ${cls}`}><Icon className="w-3.5 h-3.5" />{labels[status]||status}{detail && <span className="font-normal text-txttri"> — {detail}</span>}</span>;
}

function KeyInput({ label, value, onChange, placeholder, hint, status, statusDetail, type = 'password' }) {
  return (
    <div>
      <label className="block text-sm font-semibold text-txt mb-1.5">{label}</label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className="w-full px-3.5 py-2.5 bg-bgcard border border-bdr rounded-lg font-mono text-sm text-txt placeholder:text-txttri focus:outline-none focus:ring-2 focus:ring-acc/20 focus:border-acc transition-all" />
      {hint && <p className="text-xs text-txttri mt-1 leading-relaxed">{hint}</p>}
      <StatusDot status={status} detail={statusDetail} />
    </div>
  );
}

export default function SetupPage() {
  // State
  const [firstRun, setFirstRun] = useState(null); // null=loading, true/false
  const [setupStep, setSetupStep] = useState('loading'); // loading | generate-token | enter-token | configure
  const [authToken, setAuthToken] = useState('');
  const [generatedToken, setGeneratedToken] = useState(null);
  const [tokenCopied, setTokenCopied] = useState(false);
  const [tokenInput, setTokenInput] = useState('');
  const [generating, setGenerating] = useState(false);

  const [keys, setKeys] = useState({ ANTHROPIC_API_KEY: '', OPENAI_API_KEY: '', GOOGLE_CLIENT_ID: '', GOOGLE_CLIENT_SECRET: '', OLLAMA_BASE_URL: '', LLM_PRIMARY_MODEL: '', LLM_BUDGET_MODEL: '', LLM_PREFERRED_PROVIDER: '' });
  const [statuses, setStatuses] = useState({});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState(null);

  // Check first-run status on mount
  useEffect(() => {
    api.getSetupStatus()
      .then(d => {
        setFirstRun(d.first_run);
        setSetupStep(d.first_run ? 'generate-token' : 'enter-token');
      })
      .catch(() => {
        setFirstRun(true);
        setSetupStep('generate-token');
      });
  }, []);

  // Generate setup token (first-run step 1)
  const handleGenerateToken = async () => {
    setGenerating(true);
    try {
      // Call save with empty keys — just generates the token
      const d = await api.updateSettings('', {});
      if (d.generated_token) {
        setGeneratedToken(d.generated_token);
        setAuthToken(d.generated_token);
      }
    } catch (e) {
      setMessage({ type: 'error', text: typeof e === 'string' ? e : (e?.message || JSON.stringify(e)) });
    } finally {
      setGenerating(false);
    }
  };

  // Proceed to configuration after copying token
  const handleProceedToConfigure = () => {
    setSetupStep('configure');
    setFirstRun(false);
  };

  // Enter existing token (returning user)
  const [authError, setAuthError] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);

  const handleAuth = async () => {
    if (!tokenInput.trim()) return;
    setAuthLoading(true);
    setAuthError(null);
    try {
      // Validate the token by making a real API call that requires auth
      await api.getSettingsStatus(tokenInput.trim());
      // If we get here, the token is valid
      setAuthToken(tokenInput.trim());
      setSetupStep('configure');
    } catch (e) {
      const msg = typeof e === 'string' ? e : (e?.message || '');
      if (msg.includes('403') || msg.includes('Invalid')) {
        setAuthError('Invalid setup token. Please check and try again.');
      } else if (msg.includes('401')) {
        setAuthError('Setup token required.');
      } else {
        setAuthError(msg || 'Failed to verify token. Is the backend running?');
      }
    } finally {
      setAuthLoading(false);
    }
  };

  // Save keys
  const handleSave = async () => {
    setSaving(true); setMessage(null);
    try {
      const d = await api.updateSettings(authToken, keys);
      setMessage({ type: 'success', text: d.message || 'Settings saved successfully.' });
      return true;
    } catch (e) {
      setMessage({ type: 'error', text: typeof e === 'string' ? e : (e?.message || JSON.stringify(e)) });
      return false;
    } finally { setSaving(false); }
  };

  // Test keys
  const handleTest = async () => {
    setTesting(true);
    try {
      const results = await api.testKeys(authToken);
      if (Array.isArray(results)) {
        const s = {};
        for (const r of results) { s[r.key] = r.status; if (r.detail) s[r.key + '_detail'] = r.detail; }
        setStatuses(s);
      }
    } catch (e) {
      setMessage({ type: 'error', text: `Test failed: ${typeof e === 'string' ? e : (e?.message || JSON.stringify(e))}` });
    } finally { setTesting(false); }
  };

  const handleSaveAndTest = async () => {
    const saved = await handleSave();
    if (saved) await handleTest();
  };

  const setKey = (k, v) => setKeys(p => ({ ...p, [k]: v }));
  const copyToken = () => {
    navigator.clipboard?.writeText(generatedToken || '');
    setTokenCopied(true);
    setTimeout(() => setTokenCopied(false), 2000);
  };

  // ========== LOADING ==========
  if (setupStep === 'loading') {
    return <><Header /><div className="flex justify-center py-32"><Loader2 className="w-7 h-7 text-acc animate-spin" /></div></>;
  }

  // ========== STEP 1: GENERATE TOKEN (first-run only) ==========
  if (setupStep === 'generate-token') {
    return (
      <><Header />
        <div className="max-w-lg mx-auto px-6 py-16 text-center">
          <div className="w-16 h-16 rounded-2xl bg-accsoft flex items-center justify-center mx-auto mb-6">
            <Sparkles className="w-7 h-7 text-acc" />
          </div>
          <h1 className="font-serif text-3xl font-semibold text-txt mb-3 tracking-tight">Welcome to Meeting Toolkit</h1>
          <p className="text-sm text-txtsec leading-relaxed mb-8 max-w-md mx-auto">
            Before configuring your API keys, let's secure your settings with a setup token.
            This token will be required to access this page in the future.
          </p>

          {!generatedToken ? (
            <>
              <button onClick={handleGenerateToken} disabled={generating}
                className="px-6 py-3 bg-acc text-white rounded-xl font-semibold text-sm hover:bg-acchov transition-all inline-flex items-center gap-2 disabled:opacity-50 shadow-lg shadow-acc/20 mx-auto">
                {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Key className="w-4 h-4" /> Generate Setup Token</>}
              </button>
              {message && (
                <div className={`mt-4 p-3 rounded-lg text-sm font-medium ${message.type === 'error' ? 'bg-redsoft text-red' : 'bg-grnsoft text-grn'}`}>{message.text}</div>
              )}
            </>
          ) : (
            <div className="text-left">
              <div className="p-5 rounded-xl bg-ambsoft border border-amb/20 mb-6">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-amb" />
                  <span className="text-sm font-semibold text-amb">Your Setup Token</span>
                </div>
                <p className="text-sm text-txtsec mb-3 leading-relaxed">
                  <strong>Copy and save this token now.</strong> It will not be shown again. You'll need it to access settings in the future.
                </p>
                <div className="flex gap-2 items-center">
                  <code className="flex-1 p-3 font-mono text-sm bg-bgcard border border-bdr rounded-lg break-all leading-relaxed text-txt">{generatedToken}</code>
                  <button onClick={copyToken}
                    className="px-4 py-2.5 bg-bgcard text-txt rounded-lg border border-bdr text-sm font-medium hover:bg-bghover transition-all inline-flex items-center gap-1.5 whitespace-nowrap">
                    {tokenCopied ? <><Check className="w-3.5 h-3.5 text-grn" /> Copied!</> : <><Copy className="w-3.5 h-3.5" /> Copy</>}
                  </button>
                </div>
              </div>

              <button onClick={handleProceedToConfigure} disabled={!tokenCopied}
                className={`w-full py-3 rounded-xl font-semibold text-sm transition-all inline-flex items-center justify-center gap-2 ${
                  tokenCopied
                    ? 'bg-acc text-white hover:bg-acchov shadow-lg shadow-acc/20'
                    : 'bg-bgelev text-txttri cursor-not-allowed'
                }`}>
                {tokenCopied ? <><ArrowRight className="w-4 h-4" /> Continue to API Key Setup</> : 'Copy your token to continue'}
              </button>
            </div>
          )}
        </div>
      </>
    );
  }

  // ========== ENTER TOKEN (returning user) ==========
  if (setupStep === 'enter-token') {
    return (
      <><Header />
        <div className="max-w-md mx-auto px-6 py-20 text-center">
          <div className="w-14 h-14 rounded-2xl bg-accsoft flex items-center justify-center mx-auto mb-5">
            <Shield className="w-6 h-6 text-acc" />
          </div>
          <h2 className="font-serif text-2xl font-semibold text-txt mb-2">Welcome back</h2>
          <p className="text-sm text-txtsec mb-7 leading-relaxed">Enter your setup token to access settings.</p>
          <div className="flex gap-2">
            <input type="password" value={tokenInput} onChange={e => setTokenInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !authLoading && handleAuth()}
              placeholder="Enter setup token..."
              disabled={authLoading}
              className="flex-1 px-3.5 py-2.5 bg-bgcard border border-bdr rounded-lg font-mono text-sm text-txt placeholder:text-txttri focus:outline-none focus:ring-2 focus:ring-acc/20 focus:border-acc disabled:opacity-50" />
            <button onClick={handleAuth} disabled={!tokenInput.trim() || authLoading}
              className="px-5 py-2.5 bg-acc text-white rounded-lg font-semibold text-sm disabled:opacity-50 hover:bg-acchov transition-all inline-flex items-center gap-2">
              {authLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Verifying...</> : 'Continue'}
            </button>
          </div>
          {authError && (
            <div className="mt-4 p-3 bg-redsoft border border-red/20 rounded-lg text-sm text-red text-left">
              {authError}
            </div>
          )}
        </div>
      </>
    );
  }

  // ========== CONFIGURE KEYS ==========
  return (
    <><Header />
      <main className="max-w-2xl mx-auto px-6 py-8">
        <div className="mb-8">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-accsoft text-acc mb-3 uppercase tracking-widest">Setup Guide</div>
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-txt mb-2">Configure your API keys</h1>
          <p className="text-sm text-txtsec leading-relaxed">Paste your API keys below and click "Save & Test" to verify. At least one LLM provider is needed for AI analysis.</p>
        </div>

        {/* LLM Providers */}
        <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 mb-4">
          <h3 className="text-sm font-semibold text-txt flex items-center gap-2 mb-1"><Key className="w-4 h-4 text-acc" /> LLM Providers</h3>
          <p className="text-xs text-txttri mb-5">At least one required for AI-powered analysis.</p>
          <div className="space-y-5">
            <KeyInput label="Anthropic API Key" value={keys.ANTHROPIC_API_KEY} onChange={v=>setKey('ANTHROPIC_API_KEY',v)} placeholder="sk-ant-api03-..." hint="Get from console.anthropic.com → API Keys" status={statuses.ANTHROPIC_API_KEY} statusDetail={statuses.ANTHROPIC_API_KEY_detail} />
            <KeyInput label="OpenAI API Key" value={keys.OPENAI_API_KEY} onChange={v=>setKey('OPENAI_API_KEY',v)} placeholder="sk-proj-..." hint="Get from platform.openai.com → API keys" status={statuses.OPENAI_API_KEY} statusDetail={statuses.OPENAI_API_KEY_detail} />
          </div>
        </div>

        {/* Model Selection */}
        <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 mb-4">
          <h3 className="text-sm font-semibold text-txt flex items-center gap-2 mb-1"><Cpu className="w-4 h-4 text-amb" /> Model Selection</h3>
          <p className="text-xs text-txttri mb-5">Choose which AI provider and model to use. Only one provider is called per analysis — the other serves as a fallback if the primary fails.</p>
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-semibold text-txt mb-1.5">Preferred Provider</label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { k: 'anthropic', label: 'Anthropic (Claude)', desc: 'Best quality' },
                  { k: 'openai', label: 'OpenAI (GPT)', desc: 'Cost-effective' },
                  { k: 'ollama', label: 'Ollama (Local)', desc: 'Air-gapped' },
                ].map(({ k, label, desc }) => (
                  <button key={k} onClick={() => setKey('LLM_PREFERRED_PROVIDER', k)}
                    className={`p-3 rounded-lg border text-left transition-all ${
                      keys.LLM_PREFERRED_PROVIDER === k
                        ? 'border-acc bg-accsoft ring-2 ring-acc/20'
                        : 'border-bdr hover:border-txttri hover:bg-bghover'
                    }`}>
                    <p className={`text-sm font-semibold ${keys.LLM_PREFERRED_PROVIDER === k ? 'text-acc' : 'text-txt'}`}>{label}</p>
                    <p className="text-xs text-txttri mt-0.5">{desc}</p>
                  </button>
                ))}
              </div>
              <p className="text-xs text-txttri mt-2">Current: <span className="font-mono text-txtsec">{keys.LLM_PREFERRED_PROVIDER || 'anthropic (default)'}</span>. Each analysis uses only the selected provider. The other is a fallback if the primary fails.</p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-txt mb-1.5">Anthropic Model</label>
              <select value={keys.LLM_PRIMARY_MODEL} onChange={e => setKey('LLM_PRIMARY_MODEL', e.target.value)}
                className="w-full px-3.5 py-2.5 bg-bgcard border border-bdr rounded-lg text-sm text-txt focus:outline-none focus:ring-2 focus:ring-acc/20 focus:border-acc transition-all appearance-none cursor-pointer">
                <option value="">Keep current setting</option>
                <option value="claude-sonnet-4-6">Claude Sonnet 4.6 — Best balance of quality and speed ($3/$15 per MTok)</option>
                <option value="claude-opus-4-6">Claude Opus 4.6 — Most intelligent, best for complex analysis ($5/$25 per MTok)</option>
                <option value="claude-haiku-4-5-20251001">Claude Haiku 4.5 — Fastest, cost-effective ($1/$5 per MTok)</option>
                <option value="claude-sonnet-4-20250514">Claude Sonnet 4 (legacy)</option>
              </select>
              <p className="text-xs text-txttri mt-1">Used when Anthropic API key is configured. Current: <span className="font-mono text-txtsec">{keys.LLM_PRIMARY_MODEL || 'default'}</span></p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-txt mb-1.5">OpenAI Model (Budget)</label>
              <select value={keys.LLM_BUDGET_MODEL} onChange={e => setKey('LLM_BUDGET_MODEL', e.target.value)}
                className="w-full px-3.5 py-2.5 bg-bgcard border border-bdr rounded-lg text-sm text-txt focus:outline-none focus:ring-2 focus:ring-acc/20 focus:border-acc transition-all appearance-none cursor-pointer">
                <option value="">Keep current setting</option>
                <option value="gpt-4o">GPT-4o — Best quality, higher cost (~$5/1M tokens)</option>
                <option value="gpt-4o-mini">GPT-4o Mini — Good balance (~$0.30/1M tokens)</option>
                <option value="gpt-4.1-mini">GPT-4.1 Mini — Latest mini model</option>
                <option value="gpt-4.1">GPT-4.1 — Latest full model</option>
                <option value="o4-mini">o4-mini — Reasoning model (best for complex analysis)</option>
              </select>
              <p className="text-xs text-txttri mt-1">Used when OpenAI API key is configured. Current: <span className="font-mono text-txtsec">{keys.LLM_BUDGET_MODEL || 'default'}</span></p>
            </div>
          </div>
          <div className="mt-4 p-3 rounded-lg bg-ambsoft border border-amb/10">
            <p className="text-xs text-amb font-medium mb-1">Recommendation for long transcripts</p>
            <p className="text-xs text-txtsec leading-relaxed">For meetings over 30 minutes, use <strong>GPT-4o</strong> or <strong>Claude Sonnet 4.6</strong> for the most thorough extraction of action items and topics. <strong>Claude Opus 4.6</strong> gives the best results for complex multi-topic meetings. <strong>GPT-4o Mini</strong> and <strong>Claude Haiku 4.5</strong> work well for shorter meetings but may miss nuance in longer ones.</p>
          </div>
        </div>

        {/* Google OAuth */}
        <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 mb-4">
          <h3 className="text-sm font-semibold text-txt flex items-center gap-2 mb-1"><Calendar className="w-4 h-4 text-blu" /> Google Calendar & Drive</h3>
          <p className="text-xs text-txttri mb-5">Optional — enables calendar integration and document gathering.</p>
          <div className="space-y-5">
            <KeyInput label="Google Client ID" value={keys.GOOGLE_CLIENT_ID} onChange={v=>setKey('GOOGLE_CLIENT_ID',v)} placeholder="123456789-abc.apps.googleusercontent.com" type="text" />
            <KeyInput label="Google Client Secret" value={keys.GOOGLE_CLIENT_SECRET} onChange={v=>setKey('GOOGLE_CLIENT_SECRET',v)} placeholder="GOCSPX-..." hint="Get from console.cloud.google.com → Credentials" />
          </div>
        </div>

        {/* Ollama */}
        <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 mb-6">
          <h3 className="text-sm font-semibold text-txt flex items-center gap-2 mb-1"><Server className="w-4 h-4 text-txtsec" /> Self-Hosted LLM (Ollama)</h3>
          <p className="text-xs text-txttri mb-5">Optional — for air-gapped Tier 3 processing.</p>
          <KeyInput label="Ollama Base URL" value={keys.OLLAMA_BASE_URL} onChange={v=>setKey('OLLAMA_BASE_URL',v)} placeholder="http://localhost:11434" type="text" status={statuses.OLLAMA_BASE_URL} statusDetail={statuses.OLLAMA_BASE_URL_detail} />
        </div>

        {/* Message */}
        {message && (
          <div className={`p-3.5 rounded-lg mb-4 text-sm font-medium border ${message.type==='success'?'bg-grnsoft text-grn border-grn/20':'bg-redsoft text-red border-red/20'}`}>{message.text}</div>
        )}

        {/* Action buttons */}
        <div className="flex gap-3">
          <button onClick={handleSaveAndTest} disabled={saving||testing}
            className="flex-1 justify-center py-3 bg-acc text-white rounded-xl font-semibold text-sm hover:bg-acchov transition-all inline-flex items-center gap-2 disabled:opacity-50">
            {saving?<><Loader2 className="w-4 h-4 animate-spin" /> Saving...</>:testing?<><Loader2 className="w-4 h-4 animate-spin" /> Testing...</>:<><Check className="w-4 h-4" /> Save & Test Connections</>}
          </button>
          <button onClick={handleTest} disabled={testing}
            className="py-3 px-5 bg-bgcard text-txt rounded-xl border border-bdr font-semibold text-sm hover:bg-bghover transition-all">
            Test Only
          </button>
        </div>

        {/* Help */}
        <div className="mt-8 p-5 rounded-xl bg-bgelev border border-bdr/50">
          <h4 className="text-sm font-semibold text-txt mb-2">Need help?</h4>
          <div className="text-sm text-txtsec leading-relaxed space-y-1.5">
            <p><strong>No keys?</strong> The toolkit works without them using built-in heuristic analysis.</p>
            <p><strong>Which provider?</strong> OpenAI is cost-effective. Anthropic produces higher quality.</p>
            <p><strong>Privacy?</strong> Use Ollama for fully self-hosted, air-gapped processing.</p>
            <p><strong>Google Calendar</strong> is optional — only needed for meeting import.</p>
          </div>
        </div>
      </main>
    </>
  );
}
