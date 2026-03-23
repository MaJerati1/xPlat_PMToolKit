import './globals.css';
import ThemeProvider from '../components/ThemeProvider';

export const metadata = {
  title: 'Meeting Toolkit',
  description: 'AI-powered meeting management',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen font-sans">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
