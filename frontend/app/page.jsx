'use client';
import Link from 'next/link';
import Header from '../components/Header';
import {
  ArrowRight, Calendar, FileText, Sparkles, CheckSquare, Shield,
  BarChart3, FolderOpen, ListChecks, Server, Lock, FileSearch,
  Users, ClipboardList, Zap,
} from 'lucide-react';

export default function Home() {
  return (
    <>
      <Header />
      <main className="max-w-5xl mx-auto px-6">
        {/* ===== HERO ===== */}
        <section className="pt-20 pb-20">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-accsoft text-acc mb-5 tracking-wide">
              <Sparkles className="w-3.5 h-3.5" /> AI-Powered Meeting Management
            </div>
            <h1 className="font-serif text-5xl leading-[1.1] font-semibold tracking-tight text-txt mb-6">
              Less admin.<br />
              <span className="text-acc">More <span className="italic">impact</span>.</span>
            </h1>
            <p className="text-lg leading-relaxed text-txtsec mb-8 max-w-lg">
              The all-in-one platform that prepares you before the meeting, captures
              everything during, and drives accountability after. So you can focus on
              the work that actually moves the needle.
            </p>
            <div className="flex items-center gap-3 flex-wrap">
              <Link href="/setup"
                className="px-6 py-3 bg-acc text-white rounded-xl font-semibold text-sm hover:bg-acchov transition-all inline-flex items-center gap-2 shadow-lg shadow-acc/20">
                Get Started <ArrowRight className="w-4 h-4" />
              </Link>
              <Link href="/analyze"
                className="px-6 py-3 bg-bgcard text-txt rounded-xl font-semibold text-sm border border-bdr hover:bg-bghover transition-all shadow-sm">
                Analyze a Transcript
              </Link>
            </div>
          </div>
        </section>

        {/* ===== THREE MODULES ===== */}
        <section className="pb-16">
          <div className="text-center mb-10">
            <h2 className="font-serif text-3xl font-semibold tracking-tight text-txt mb-3">
              Your complete meeting lifecycle
            </h2>
            <p className="text-sm text-txtsec max-w-md mx-auto">
              From preparation to follow-through — every stage of every meeting, handled.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Before Meeting */}
            <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 hover:shadow-md transition-shadow">
              <div className="w-10 h-10 rounded-lg mb-4 flex items-center justify-center bg-blusoft text-blu">
                <Calendar className="w-5 h-5" />
              </div>
              <h3 className="font-sans text-base font-semibold text-txt mb-2">Before Meeting</h3>
              <p className="text-sm leading-relaxed text-txtsec mb-4">
                Import calendar events, gather relevant documents from Google Drive, and generate
                briefing packages — so everyone walks in prepared.
              </p>
              <div className="space-y-2">
                {[
                  { icon: Calendar, text: 'Google Calendar import' },
                  { icon: FileSearch, text: 'Smart document gathering' },
                  { icon: FolderOpen, text: 'Briefing package generation' },
                  { icon: Users, text: 'Attendee & role management' },
                ].map(({ icon: I, text }) => (
                  <div key={text} className="flex items-center gap-2 text-xs text-txtsec">
                    <I className="w-3.5 h-3.5 text-blu" /> {text}
                  </div>
                ))}
              </div>
            </div>

            {/* Transcript Tools */}
            <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 hover:shadow-md transition-shadow">
              <div className="w-10 h-10 rounded-lg mb-4 flex items-center justify-center bg-accsoft text-acc">
                <FileText className="w-5 h-5" />
              </div>
              <h3 className="font-sans text-base font-semibold text-txt mb-2">Transcript Tools</h3>
              <p className="text-sm leading-relaxed text-txtsec mb-4">
                Upload transcripts from any tool — Otter, Fireflies, Zoom, Teams — and
                get AI-powered summaries, key decisions, and action items in seconds.
              </p>
              <div className="space-y-2">
                {[
                  { icon: FileText, text: 'SRT, VTT, CSV, JSON, TXT support' },
                  { icon: Sparkles, text: 'AI summary & decision extraction' },
                  { icon: BarChart3, text: 'Speaker & topic analysis' },
                  { icon: Zap, text: 'Quick Analyze — paste and go' },
                ].map(({ icon: I, text }) => (
                  <div key={text} className="flex items-center gap-2 text-xs text-txtsec">
                    <I className="w-3.5 h-3.5 text-acc" /> {text}
                  </div>
                ))}
              </div>
            </div>

            {/* After Meeting */}
            <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 hover:shadow-md transition-shadow">
              <div className="w-10 h-10 rounded-lg mb-4 flex items-center justify-center bg-grnsoft text-grn">
                <CheckSquare className="w-5 h-5" />
              </div>
              <h3 className="font-sans text-base font-semibold text-txt mb-2">After Meeting</h3>
              <p className="text-sm leading-relaxed text-txtsec mb-4">
                Extract action items with owners and deadlines. Track follow-ups, generate
                meeting minutes, and prepare draft agendas for the next meeting.
              </p>
              <div className="space-y-2">
                {[
                  { icon: ListChecks, text: 'Action item tracking & confirm/decline' },
                  { icon: ClipboardList, text: 'Meeting minutes generation' },
                  { icon: Calendar, text: 'Future meeting prep from open items' },
                  { icon: BarChart3, text: 'Coverage & completion dashboards' },
                ].map(({ icon: I, text }) => (
                  <div key={text} className="flex items-center gap-2 text-xs text-txtsec">
                    <I className="w-3.5 h-3.5 text-grn" /> {text}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ===== HOW IT WORKS ===== */}
        <section className="pb-16">
          <div className="text-center mb-10">
            <h2 className="font-serif text-3xl font-semibold tracking-tight text-txt mb-3">
              How it works
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { num: '1', title: 'Import', desc: 'Pull meetings from Google Calendar or create them manually', icon: Calendar },
              { num: '2', title: 'Prepare', desc: 'Gather documents, generate briefings, share with attendees', icon: FolderOpen },
              { num: '3', title: 'Analyze', desc: 'Upload the transcript — AI extracts summaries, decisions, and actions', icon: Sparkles },
              { num: '4', title: 'Follow up', desc: 'Track action items, generate minutes, prep the next meeting', icon: ListChecks },
            ].map(({ num, title, desc, icon: I }) => (
              <div key={num} className="text-center px-3">
                <div className="w-10 h-10 rounded-full bg-acc text-white flex items-center justify-center text-sm font-bold mx-auto mb-3">
                  {num}
                </div>
                <h4 className="text-sm font-semibold text-txt mb-1">{title}</h4>
                <p className="text-xs text-txtsec leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ===== PRIVACY & SECURITY ===== */}
        <section className="pb-20">
          <div className="bg-bgcard rounded-2xl border border-bdr shadow-sm overflow-hidden">
            <div className="p-8 md:flex items-start gap-8">
              <div className="flex-shrink-0 mb-6 md:mb-0">
                <div className="w-14 h-14 rounded-2xl bg-blusoft flex items-center justify-center">
                  <Shield className="w-7 h-7 text-blu" />
                </div>
              </div>
              <div className="flex-1">
                <h3 className="font-serif text-2xl font-semibold text-txt mb-3">
                  Your data stays yours
                </h3>
                <p className="text-sm text-txtsec leading-relaxed mb-5 max-w-xl">
                  Meeting transcripts contain some of the most sensitive information in your
                  organization — strategy, personnel decisions, financial data, IP discussions.
                  We built the Meeting Toolkit with a three-tier data isolation architecture
                  so you control exactly where your data goes.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 rounded-xl bg-bgelev">
                    <div className="flex items-center gap-2 mb-2">
                      <Lock className="w-4 h-4 text-blu" />
                      <span className="text-sm font-semibold text-txt">Tier 1: Cloud ZDR</span>
                    </div>
                    <p className="text-xs text-txtsec leading-relaxed">
                      Zero data retention with Anthropic and OpenAI. Your transcripts are never stored
                      or used for model training.
                    </p>
                  </div>
                  <div className="p-4 rounded-xl bg-bgelev">
                    <div className="flex items-center gap-2 mb-2">
                      <Shield className="w-4 h-4 text-amb" />
                      <span className="text-sm font-semibold text-txt">Tier 2: Redaction</span>
                    </div>
                    <p className="text-xs text-txtsec leading-relaxed">
                      Sensitive identifiers are automatically masked before reaching any AI provider.
                      Names, numbers, and project codes are replaced with placeholders.
                    </p>
                  </div>
                  <div className="p-4 rounded-xl bg-bgelev">
                    <div className="flex items-center gap-2 mb-2">
                      <Server className="w-4 h-4 text-grn" />
                      <span className="text-sm font-semibold text-txt">Tier 3: Self-Hosted</span>
                    </div>
                    <p className="text-xs text-txtsec leading-relaxed">
                      Run AI analysis on your own hardware with Ollama. No data ever leaves your
                      network — ideal for classified, NPI, or regulated environments.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
