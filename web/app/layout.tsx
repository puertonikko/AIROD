import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIROD — AI R&D Group",
  description:
    "An R&D group made of collaborating AI agents. Assign a mission; watch them propose, ground, attack, score, and resolve.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
