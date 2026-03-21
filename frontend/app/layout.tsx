export const metadata = {
  title: "Meeting Toolkit",
  description: "All-in-One Meeting Management Solution",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}