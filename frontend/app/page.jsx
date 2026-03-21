'use client';

import Link from 'next/link';
import { FileText, Zap, CheckSquare, ArrowRight, BarChart3 } from 'lucide-react';

export default function Home() {
  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-ink-200/60 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-ocean-600 rounded-lg flex items-center justify-center">
              <FileText className="w-4 h-4 text-white" />
            </div>
            <span className="font-display text-xl text-ink-900">Meeting Toolkit</span>
          </div>
          <nav className="flex items-center gap-6 text-sm">
            <Link href="/analyze" className="text-ink-600 hover:text-ink-900 transition-colors">
              Analyze
            </Link>
            <Link href="/quick" className="text-ink-600 hover:text-ink-900 transition-colors">
              Quick Analyze
            </Link>
            <a href="http://localhost:8000/docs" target="_blank" rel="noopener"
               className="text-ink-600 hover:text-ink-900 transition-colors">
              API Docs
            </a>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <main className="max-w-6xl mx-auto px-6">
        <section className="pt-20 pb-16">
          <div className="max-w-2xl">
            <h1 className="font-display text-5xl leading-tight text-ink-950 mb-6">
              Turn transcripts into<br />
              <span className="text-ocean-600 italic">actionable insights</span>
            </h1>
            <p className="text-lg text-ink-500 leading-relaxed mb-8">
              Upload a meeting transcript from any tool — Otter, Fireflies, Zoom, Teams —
              and get an AI-powered summary, action items, and key decisions in seconds.
            </p>
            <div className="flex items-center gap-4">
              <Link href="/analyze" className="btn-primary inline-flex items-center gap-2">
                Analyze a transcript <ArrowRight className="w-4 h-4" />
              </Link>
              <Link href="/quick" className="btn-secondary">
                Quick Analyze
              </Link>
            </div>
          </div>
        </section>

        {/* Feature cards */}
        <section className="pb-20 grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="card p-6">
            <div className="w-10 h-10 bg-ocean-50 rounded-lg flex items-center justify-center mb-4">
              <FileText className="w-5 h-5 text-ocean-600" />
            </div>
            <h3 className="font-semibold text-ink-900 mb-1.5">Multi-format ingestion</h3>
            <p className="text-sm text-ink-500 leading-relaxed">
              Upload SRT, VTT, CSV, JSON, or plain text. Format is auto-detected.
              Paste directly or drag and drop files.
            </p>
          </div>
          <div className="card p-6">
            <div className="w-10 h-10 bg-sage-50 rounded-lg flex items-center justify-center mb-4">
              <Zap className="w-5 h-5 text-sage-600" />
            </div>
            <h3 className="font-semibold text-ink-900 mb-1.5">AI-powered analysis</h3>
            <p className="text-sm text-ink-500 leading-relaxed">
              Generates executive summaries, key decisions, discussion topics,
              and speaker contribution analysis.
            </p>
          </div>
          <div className="card p-6">
            <div className="w-10 h-10 bg-ember-50 rounded-lg flex items-center justify-center mb-4">
              <CheckSquare className="w-5 h-5 text-ember-600" />
            </div>
            <h3 className="font-semibold text-ink-900 mb-1.5">Action item extraction</h3>
            <p className="text-sm text-ink-500 leading-relaxed">
              Extracts tasks with owners, deadlines, and priorities.
              Review, confirm, or reject with batch operations.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
