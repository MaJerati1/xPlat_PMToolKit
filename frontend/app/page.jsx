'use client';
import Link from 'next/link';
import Header from '../components/Header';
import { ArrowRight, FileText, Sparkles, CheckSquare } from 'lucide-react';

export default function Home() {
  return (
    <>
      <Header />
      <main className="max-w-4xl mx-auto px-6">
        <section className="pt-20 pb-16">
          <div className="max-w-xl">
            <div className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-accsoft text-acc mb-5 tracking-wide">
              <Sparkles className="w-3.5 h-3.5" /> AI-Powered Analysis
            </div>
            <h1 className="font-serif text-5xl leading-tight font-semibold tracking-tight text-txt mb-5">
              Your meetings,<br />
              <span className="text-acc italic">finally useful</span>
            </h1>
            <p className="text-lg leading-relaxed text-txtsec mb-8 max-w-md">
              Paste any transcript — Otter, Fireflies, Zoom, Teams — and get a structured
              summary, action items, and key decisions in seconds.
            </p>
            <div className="flex items-center gap-3">
              <Link href="/analyze"
                className="px-6 py-3 bg-acc text-white rounded-xl font-semibold text-sm hover:bg-acchov transition-all inline-flex items-center gap-2 shadow-lg shadow-acc/20">
                Analyze a transcript <ArrowRight className="w-4 h-4" />
              </Link>
              <Link href="/quick"
                className="px-6 py-3 bg-bgcard text-txt rounded-xl font-semibold text-sm border border-bdr hover:bg-bghover transition-all shadow-sm">
                Quick Analyze
              </Link>
            </div>
          </div>
        </section>

        <section className="pb-20 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 hover:shadow-md transition-shadow">
            <div className="w-10 h-10 rounded-lg mb-4 flex items-center justify-center bg-blusoft text-blu">
              <FileText className="w-5 h-5" />
            </div>
            <h3 className="font-sans text-[15px] font-semibold text-txt mb-1.5">Multi-format ingestion</h3>
            <p className="font-sans text-sm leading-relaxed text-txtsec">SRT, VTT, CSV, JSON, or plain text. Auto-detected. Paste directly or drag-and-drop files.</p>
          </div>
          <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 hover:shadow-md transition-shadow">
            <div className="w-10 h-10 rounded-lg mb-4 flex items-center justify-center bg-accsoft text-acc">
              <Sparkles className="w-5 h-5" />
            </div>
            <h3 className="font-sans text-[15px] font-semibold text-txt mb-1.5">AI-powered analysis</h3>
            <p className="font-sans text-sm leading-relaxed text-txtsec">Executive summaries, key decisions, discussion topics, and speaker contribution analysis.</p>
          </div>
          <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-6 hover:shadow-md transition-shadow">
            <div className="w-10 h-10 rounded-lg mb-4 flex items-center justify-center bg-grnsoft text-grn">
              <CheckSquare className="w-5 h-5" />
            </div>
            <h3 className="font-sans text-[15px] font-semibold text-txt mb-1.5">Action item extraction</h3>
            <p className="font-sans text-sm leading-relaxed text-txtsec">Tasks with owners, deadlines, and priorities. Review, confirm, or decline with batch operations.</p>
          </div>
        </section>
      </main>
    </>
  );
}
