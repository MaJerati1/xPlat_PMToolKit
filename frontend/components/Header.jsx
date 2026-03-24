'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTheme } from './ThemeProvider';
import { useState, useRef, useEffect } from 'react';
import {
  Sparkles, Sun, Moon, ExternalLink, ChevronDown,
  Calendar, FileSearch, FileText as FileTextIcon, ClipboardList,
  BarChart3, ListChecks, FolderOpen, Shield,
} from 'lucide-react';

function Dropdown({ label, icon: Icon, items, pathname }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const isActive = items.some(i => i.href === pathname);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen(!open)}
        className={`px-3.5 py-2 rounded-lg text-sm font-medium flex items-center gap-1.5 transition-all ${
          isActive ? 'bg-bgelev text-txt border border-bdr' : 'text-txtsec hover:text-txt'
        }`}>
        {Icon && <Icon className="w-3.5 h-3.5" />}
        {label}
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute top-full mt-1.5 left-0 min-w-[220px] bg-bgcard border border-bdr rounded-xl shadow-lg overflow-hidden z-50"
          style={{ backdropFilter: 'blur(12px)' }}>
          {items.map(({ href, label: itemLabel, icon: ItemIcon, desc }) => (
            <Link key={href} href={href} onClick={() => setOpen(false)}
              className={`flex items-start gap-3 px-4 py-3 hover:bg-bghover transition-colors ${
                pathname === href ? 'bg-bgelev' : ''
              }`}>
              {ItemIcon && <ItemIcon className="w-4 h-4 text-txtsec mt-0.5 flex-shrink-0" />}
              <div>
                <span className={`text-sm font-medium block ${pathname === href ? 'text-acc' : 'text-txt'}`}>{itemLabel}</span>
                {desc && <span className="text-xs text-txttri leading-snug block mt-0.5">{desc}</span>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Header() {
  const pathname = usePathname();
  const { dark, toggle } = useTheme();

  const beforeItems = [
    { href: '/calendar', label: 'Calendar Import', icon: Calendar, desc: 'Import events from Google Calendar' },
    { href: '/documents', label: 'Document Gathering', icon: FileSearch, desc: 'Find relevant docs from Drive' },
    { href: '/briefing', label: 'Briefing Package', icon: FolderOpen, desc: 'Generate pre-meeting briefings' },
  ];

  const transcriptItems = [
    { href: '/analyze', label: 'Analyze Transcript', icon: BarChart3, desc: 'Upload and analyze with AI' },
    { href: '/quick', label: 'Quick Analyze', icon: Sparkles, desc: 'Paste and go — no setup needed' },
  ];

  const afterItems = [
    { href: '/actions', label: 'Action Items', icon: ListChecks, desc: 'Track and manage action items' },
    { href: '/minutes', label: 'Meeting Minutes', icon: ClipboardList, desc: 'Generate formal minutes' },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-bdr" style={{ backdropFilter: 'blur(12px)', background: 'var(--bg)' + 'DD' }}>
      <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-acc flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="font-serif text-lg font-semibold tracking-tight text-txt">Meeting Toolkit</span>
        </Link>

        {/* Navigation */}
        <div className="flex items-center gap-1">
          <Link href="/setup"
            className={`px-3.5 py-2 rounded-lg text-sm font-semibold transition-all ${
              pathname === '/setup' ? 'bg-acc text-white' : 'text-acc hover:bg-accsoft'
            }`}>
            Getting Started
          </Link>

          <Dropdown label="Before Meeting" icon={Calendar} items={beforeItems} pathname={pathname} />
          <Dropdown label="Transcript Tools" icon={FileTextIcon} items={transcriptItems} pathname={pathname} />
          <Dropdown label="After Meeting" icon={ListChecks} items={afterItems} pathname={pathname} />

          <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer"
            className="px-3 py-2 rounded-lg text-sm font-medium text-txtsec hover:text-txt transition-colors flex items-center gap-1.5">
            API <ExternalLink className="w-3 h-3" />
          </a>

          <button onClick={toggle} title={dark ? 'Light mode' : 'Dark mode'}
            className="ml-1 p-2 rounded-lg bg-bgelev border border-bdr text-txtsec hover:text-txt transition-all">
            {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </header>
  );
}
