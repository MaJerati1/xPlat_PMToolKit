import './globals.css';

export const metadata = {
  title: 'Meeting Toolkit',
  description: 'AI-powered meeting management — transcript analysis, action items, and meeting minutes',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
