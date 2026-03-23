/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
        serif: ['Source Serif 4', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      colors: {
        bg:       'var(--bg)',
        bgcard:   'var(--bg-card)',
        bgelev:   'var(--bg-elev)',
        bghover:  'var(--bg-hover)',
        txt:      'var(--txt)',
        txtsec:   'var(--txt-sec)',
        txttri:   'var(--txt-tri)',
        txtinv:   'var(--txt-inv)',
        bdr:      'var(--bdr)',
        acc:      'var(--acc)',
        acchov:   'var(--acc-hov)',
        accsoft:  'var(--acc-soft)',
        grn:      'var(--grn)',
        grnsoft:  'var(--grn-soft)',
        blu:      'var(--blu)',
        blusoft:  'var(--blu-soft)',
        amb:      'var(--amb)',
        ambsoft:  'var(--amb-soft)',
        red:      'var(--red)',
        redsoft:  'var(--red-soft)',
      },
      borderRadius: {
        xl: '12px',
        lg: '10px',
        md: '8px',
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
