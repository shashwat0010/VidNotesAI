import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "VidNotes AI - AI-Powered Video Lecture Notes, Flashcards & RAG Chat",
  description: "Transform video/audio and YouTube URLs into structured knowledge. Create detailed revision notes, summaries, interactive quizzes, mind maps, and chat with your transcripts using semantic search citations.",
  keywords: ["AI notes", "video transcription", "revision cards", "MCQ quizzes", "mermaid diagrams", "RAG chat", "SaaS database search"],
  authors: [{ name: "VidNotes AI Team" }],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased dark`}>
      <body className="min-h-full bg-slate-950 text-slate-100 font-sans antialiased overflow-x-hidden selection:bg-indigo-500/30 selection:text-indigo-200">
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
