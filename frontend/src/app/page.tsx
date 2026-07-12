"use client";

import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { 
  Tv, 
  Cpu, 
  FileText, 
  Zap, 
  BrainCircuit, 
  ArrowRight, 
  Sparkles, 
  Clock, 
  Code2, 
  Bookmark, 
  CheckCircle2 
} from "lucide-react";

export default function Home() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-slate-950 bg-gradient-radial overflow-x-hidden flex flex-col">
      {/* Navigation */}
      <header className="glass-panel fixed top-0 w-full z-50 border-b border-slate-900 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Zap className="h-6 w-6 text-white" />
          </div>
          <span className="text-xl font-bold tracking-tight text-white">
            VidNotes <span className="text-gradient">AI</span>
          </span>
        </div>
        
        <nav className="flex items-center space-x-4">
          {user ? (
            <Link 
              href="/dashboard" 
              className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition duration-200 text-sm shadow-md shadow-indigo-600/10 flex items-center gap-2"
            >
              Go to Dashboard <ArrowRight className="h-4 w-4" />
            </Link>
          ) : (
            <>
              <Link href="/login" className="text-sm font-medium text-slate-300 hover:text-white transition duration-150">
                Sign In
              </Link>
              <Link 
                href="/signup" 
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition duration-200 text-sm shadow-md shadow-indigo-600/10"
              >
                Get Started
              </Link>
            </>
          )}
        </nav>
      </header>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6 flex flex-col items-center justify-center text-center relative z-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-indigo-500/30 bg-indigo-950/20 text-indigo-300 text-xs font-semibold mb-6 animate-pulse">
          <Sparkles className="h-3 w-3" /> Production-Ready AI Processing Engine
        </div>
        
        <h1 className="text-4xl md:text-6xl lg:text-7xl font-extrabold tracking-tight text-white max-w-4xl leading-tight">
          Turn Video Lectures Into <br className="hidden md:inline" />
          <span className="text-gradient">Structured Knowledge</span>
        </h1>
        
        <p className="mt-6 text-lg text-slate-400 max-w-2xl leading-relaxed">
          Paste a YouTube URL or upload files. Our advanced multi-modal pipeline runs Whisper transcription, extracts slide frames, executes OCR & vision models, and builds a searchable semantic database.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center gap-4">
          <Link 
            href={user ? "/dashboard" : "/signup"} 
            className="w-full sm:w-auto px-8 py-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shadow-lg shadow-indigo-600/25 transition duration-200 flex items-center justify-center gap-3 group"
          >
            Start Analyzing Free 
            <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
          </Link>
          <a 
            href="#pipeline" 
            className="w-full sm:w-auto px-8 py-4 rounded-xl border border-slate-800 bg-slate-900/40 hover:bg-slate-900 text-slate-300 hover:text-white font-semibold transition duration-200 flex items-center justify-center gap-2"
          >
            See Pipeline
          </a>
        </div>
      </section>

      {/* Pipeline Grid */}
      <section id="pipeline" className="py-20 px-6 max-w-7xl mx-auto w-full relative">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-white">How VidNotes AI Works</h2>
          <p className="text-slate-400 mt-3 max-w-xl mx-auto">Five automated steps convert video into accessible markdown notes, interactive quizzes, and visual charts.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-6 relative">
          <div className="glass-card p-6 rounded-2xl flex flex-col items-start">
            <div className="h-12 w-12 rounded-xl bg-indigo-950/40 border border-indigo-500/25 flex items-center justify-center text-indigo-400 mb-4 font-bold text-lg">01</div>
            <h3 className="font-semibold text-white mb-2 text-base">Media Upload</h3>
            <p className="text-sm text-slate-400">Pasted YouTube links or uploaded audio/video MP4 formats up to 500MB.</p>
          </div>
          <div className="glass-card p-6 rounded-2xl flex flex-col items-start">
            <div className="h-12 w-12 rounded-xl bg-indigo-950/40 border border-indigo-500/25 flex items-center justify-center text-indigo-400 mb-4 font-bold text-lg">02</div>
            <h3 className="font-semibold text-white mb-2 text-base">Whisper Parsing</h3>
            <p className="text-sm text-slate-400">Pulls captions if available, otherwise transcribes using local Faster-Whisper models.</p>
          </div>
          <div className="glass-card p-6 rounded-2xl flex flex-col items-start">
            <div className="h-12 w-12 rounded-xl bg-indigo-950/40 border border-indigo-500/25 flex items-center justify-center text-indigo-400 mb-4 font-bold text-lg">03</div>
            <h3 className="font-semibold text-white mb-2 text-base">OCR & Vision</h3>
            <p className="text-sm text-slate-400">Extracts frames every 10s. Runs OCR on slide text + Vision analysis on diagrams.</p>
          </div>
          <div className="glass-card p-6 rounded-2xl flex flex-col items-start">
            <div className="h-12 w-12 rounded-xl bg-indigo-950/40 border border-indigo-500/25 flex items-center justify-center text-indigo-400 mb-4 font-bold text-lg">04</div>
            <h3 className="font-semibold text-white mb-2 text-base">Vector RAG</h3>
            <p className="text-sm text-slate-400">Chunks content and computes OpenAI embeddings, indexing them into pgvector storage.</p>
          </div>
          <div className="glass-card p-6 rounded-2xl flex flex-col items-start">
            <div className="h-12 w-12 rounded-xl bg-indigo-950/40 border border-indigo-500/25 flex items-center justify-center text-indigo-400 mb-4 font-bold text-lg">05</div>
            <h3 className="font-semibold text-white mb-2 text-base">AI Generation</h3>
            <p className="text-sm text-slate-400">Compiles summaries, glossaries, MCQs, mind maps, and interactive QA chats.</p>
          </div>
        </div>
      </section>

      {/* Feature Section */}
      <section className="py-20 bg-slate-950/40 border-y border-slate-900 px-6">
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="text-3xl md:text-5xl font-bold text-white leading-tight">
              An Academic Workstation <br />
              Powered by <span className="text-gradient">Multi-Modal AI</span>
            </h2>
            <p className="text-slate-400 mt-6 leading-relaxed">
              VidNotes AI goes beyond simple transcript summarizing. We analyze diagrams, whiteboards, code setups, and slide presentations. You receive an integrated cockpit to learn, quiz, check structure, and export study assets.
            </p>
            
            <div className="mt-8 space-y-4">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-indigo-400 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-white text-base">Interactive Player-Transcript Sync</h4>
                  <p className="text-sm text-slate-400">Clicking any sentence in the transcript jumps the video directly to that time.</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-indigo-400 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-white text-base">3D Study Flashcards & MCQ Quizzes</h4>
                  <p className="text-sm text-slate-400">Flip cards interactively, track score performance, and review answers with explanations.</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-indigo-400 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-white text-base">Semantic Citation Chat</h4>
                  <p className="text-sm text-slate-400">Ask the chatbot questions. Get answers cited with video timestamps you can click to play.</p>
                </div>
              </div>
            </div>
          </div>
          
          <div className="glass-card p-4 rounded-3xl border border-slate-800 shadow-2xl relative overflow-hidden bg-slate-950/80">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"></div>
            <div className="flex items-center justify-between border-b border-slate-900 pb-3 mb-4">
              <div className="flex gap-1.5">
                <span className="w-3 h-3 rounded-full bg-red-500/80"></span>
                <span className="w-3 h-3 rounded-full bg-yellow-500/80"></span>
                <span className="w-3 h-3 rounded-full bg-green-500/80"></span>
              </div>
              <span className="text-xs font-semibold text-slate-500">Workspace Panel Preview</span>
            </div>
            
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2 rounded-xl aspect-video bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500 text-xs">
                Video Screen Sync
              </div>
              <div className="rounded-xl bg-slate-900 border border-slate-800 p-2 flex flex-col justify-between">
                <span className="text-[10px] text-indigo-400 font-bold uppercase">Chat AI</span>
                <span className="text-[10px] text-slate-400 leading-tight">Q: Explain RAG? <br />A: Retrieving relevant... [00:45]</span>
                <div className="h-5 rounded bg-indigo-600 flex items-center justify-center text-[9px] text-white">Ask</div>
              </div>
              <div className="col-span-3 rounded-xl bg-slate-900 border border-slate-800 p-3">
                <div className="flex gap-2 mb-2">
                  <span className="px-2 py-0.5 text-[9px] font-bold bg-indigo-500/10 text-indigo-400 rounded">Summary</span>
                  <span className="px-2 py-0.5 text-[9px] font-bold text-slate-400">Mermaid Graph</span>
                  <span className="px-2 py-0.5 text-[9px] font-bold text-slate-400">Flashcards</span>
                </div>
                <div className="h-16 w-full rounded bg-slate-950 border border-slate-900/60 p-2 text-[10px] text-slate-400 overflow-hidden leading-relaxed">
                  <b>Executive Summary:</b> This lecture outlines modern distributed system design patterns. Key focus areas include eventual consistency, vector databases, and state synchronization.
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-900 bg-slate-950 py-10 text-center text-slate-500 text-sm">
        <p>&copy; {new Date().getFullYear()} VidNotes AI. Build production systems correctly.</p>
      </footer>
    </div>
  );
}
