'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTheme } from './ThemeProvider';
import { Sparkles, Sun, Moon, ExternalLink } from 'lucide-react';

export default function Header() {
  const pathname = usePathname();
  const { dark, toggle } = useTheme();

  const navLink = (href, label, active) => (
    <Link key={href} href={href}
      className={`px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
        active ? 'bg-bgelev text-txt border border-bdr' : 'text-txtsec hover:text-txt'
      }`}>
      {label}
    </Link>
  );

  return (
    <header className="sticky top-0 z-50 border-b border-bdr" style={{ backdropFilter: 'blur(12px)', background: 'var(--bg)' + 'DD' }}>
      <div className="max-w-4xl mx-auto px-6 py-3.5 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-acc flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="font-serif text-xl font-semibold tracking-tight text-txt">Meeting Toolkit</span>
        </Link>
        <div className="flex items-center gap-1.5">
          <Link href="/setup"
            className={`px-3.5 py-2 rounded-lg text-sm font-semibold transition-all ${
              pathname === '/setup' ? 'bg-acc text-white' : 'text-acc hover:bg-accsoft'
            }`}>
            Getting Started
          </Link>
          {navLink('/analyze', 'Analyze', pathname === '/analyze')}
          {navLink('/quick', 'Quick', pathname === '/quick')}
          <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer"
            className="px-3.5 py-2 rounded-lg text-sm font-medium text-txtsec hover:text-txt transition-colors flex items-center gap-1.5">
            API Docs <ExternalLink className="w-3 h-3" />
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
