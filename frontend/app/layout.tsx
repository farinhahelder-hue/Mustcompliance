import "./globals.css";

export const metadata = {
  title: "MustCompliance - CGP Dashboard",
  description: "CGP Cabinet Compliance Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}