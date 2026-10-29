import type { Metadata } from "next";
import { Bricolage_Grotesque, JetBrains_Mono, Literata } from "next/font/google";
import { Providers } from "@/components/Providers";
import "./globals.css";

const ui = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-ui" });
const read = Literata({ subsets: ["latin"], variable: "--font-read" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: { default: "selfmemory", template: "%s · selfmemory" },
  description: "Your organization's wiki, written and kept up to date by an agent.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${ui.variable} ${read.variable} ${mono.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
