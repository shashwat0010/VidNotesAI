"use client";

import React, { useState, useEffect, useRef, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, BASE_URL } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import mermaid from "mermaid";
import {
  ArrowLeft,
  Play,
  MessageSquare,
  FileText,
  HelpCircle,
  Layers,
  ChevronRight,
  Brain,
  Download,
  Bookmark,
  Share2,
  Send,
  Loader2,
  Volume2,
  Video,
  ListRestart
} from "lucide-react";

// Initialize mermaid outside component
if (typeof window !== "undefined") {
  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    securityLevel: "loose",
  });
}

interface PageProps {
  params: Promise<{ id: string }>;
}

interface VideoDetails {
  id: string;
  title: string;
  url: string | null;
  file_path: string | null;
  status: string;
  duration: number | null;
}

interface TranscriptSegment {
  id: number;
  text: string;
  start_time: number;
  end_time: number;
}

interface Keyframe {
  id: number;
  timestamp: number;
  s3_url: string;
  ocr_text: string | null;
  vision_description: string | null;
}

interface Flashcard {
  question: string;
  answer: string;
}

interface MCQ {
  question: string;
  options: string[];
  answer: string;
  explanation: string;
}

interface NoteOutput {
  summary_exec: string;
  summary_detailed: string;
  revision_notes: string;
  takeaways: string;
  glossary: string;
  flashcards: Flashcard[];
  mcqs: MCQ[];
  mindmap: string;
}

interface ChatCitation {
  text: string;
  start_time: number;
  end_time: number;
}

interface ChatMessage {
  id: number;
  role: string;
  content: string;
  citations: ChatCitation[] | null;
}

const getImageUrl = (url: string) => {
  if (!url) return "";
  if (url.startsWith("/")) {
    if (typeof window !== "undefined") {
      // If we are running frontend on a dev server (like port 3000), route images to Nginx proxy port (80)
      if (window.location.port === "3000") {
        return `${window.location.protocol}//${window.location.hostname}${url}`;
      }
    }
    return url;
  }
  return url;
};

function parseMarkdown(text: string) {
  if (!text) return null;
  const lines = text.split("\n");
  return lines.map((line, idx) => {
    // Check headings
    if (line.startsWith("### ")) {
      return <h3 key={idx} className="text-base font-bold text-white mt-4 mb-2">{parseInlineStyles(line.substring(4))}</h3>;
    }
    if (line.startsWith("## ")) {
      return <h2 key={idx} className="text-lg font-bold text-white mt-5 mb-2">{parseInlineStyles(line.substring(3))}</h2>;
    }
    if (line.startsWith("# ")) {
      return <h1 key={idx} className="text-xl font-bold text-white mt-6 mb-3">{parseInlineStyles(line.substring(2))}</h1>;
    }
    // Check list item
    if (line.startsWith("- ")) {
      return <li key={idx} className="ml-4 list-disc text-slate-300 mb-1">{parseInlineStyles(line.substring(2))}</li>;
    }
    // Check images
    const imgRegex = /!\[([^\]]*)\]\(([^)]*)\)/g;
    const imgMatch = imgRegex.exec(line);
    if (imgMatch) {
      const alt = imgMatch[1];
      const src = imgMatch[2];
      return (
        <div key={idx} className="my-4 rounded-xl border border-slate-900 overflow-hidden bg-slate-950 max-w-lg">
          <img src={getImageUrl(src)} alt={alt} className="w-full h-auto object-contain" />
          <span className="text-[10px] text-slate-500 p-2 block border-t border-slate-900 bg-slate-900/20">{alt}</span>
        </div>
      );
    }
    // Paragraph
    if (line.trim() === "") return <div key={idx} className="h-2"></div>;
    return <p key={idx} className="mb-2 leading-relaxed text-slate-300 text-sm">{parseInlineStyles(line)}</p>;
  });
}

function parseInlineStyles(text: string) {
  const parts = text.split(/\*\*([^*]+)\*\*/g);
  return parts.map((part, idx) => {
    if (idx % 2 === 1) {
      return <strong key={idx} className="font-bold text-white">{part}</strong>;
    }
    return part;
  });
}

export default function Workspace({ params }: PageProps) {
  const router = useRouter();
  const resolvedParams = use(params);
  const videoId = resolvedParams.id;
  const { user, loading: authLoading } = useAuth();

  // Core Data
  const [video, setVideo] = useState<VideoDetails | null>(null);
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([]);
  const [keyframes, setKeyframes] = useState<Keyframe[]>([]);
  const [notes, setNotes] = useState<NoteOutput | null>(null);
  
  // Loading states
  const [dataLoading, setDataLoading] = useState(true);
  const [exportLoading, setExportLoading] = useState<string | null>(null);
  const [flashcardsLoading, setFlashcardsLoading] = useState(false);
  const [quizLoading, setQuizLoading] = useState(false);
  const [mindmapLoading, setMindmapLoading] = useState(false);
  
  // Workspace UI Tabs
  const [activeTab, setActiveTab] = useState<"summary" | "notes" | "flashcards" | "quiz" | "mindmap" | "slides">("summary");
  
  // Video playback timing
  const [currentTime, setCurrentTime] = useState(0);
  const videoPlayerRef = useRef<HTMLVideoElement | null>(null);
  const ytPlayerRef = useRef<HTMLIFrameElement | null>(null);

  // Chat Panel State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [userQuery, setUserQuery] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  // Flashcards Study deck active card
  const [activeCardIndex, setActiveCardIndex] = useState(0);
  const [isCardFlipped, setIsCardFlipped] = useState(false);

  // MCQ Selection State
  const [mcqAnswers, setMcqAnswers] = useState<Record<number, string>>({});
  const [submittedMcqs, setSubmittedMcqs] = useState<Record<number, boolean>>({});

  // Mermaid SVG render state
  const [mindmapSvg, setMindmapSvg] = useState<string>("");

  useEffect(() => {
    if (user && videoId) {
      loadWorkspaceData();
    }
  }, [user, videoId]);

  // Load Dynamic Tab Content on Demand
  useEffect(() => {
    if (!notes) return;

    if (activeTab === "flashcards" && notes.flashcards.length === 0 && !flashcardsLoading) {
      fetchFlashcards();
    } else if (activeTab === "quiz" && notes.mcqs.length === 0 && !quizLoading) {
      fetchQuiz();
    } else if (activeTab === "mindmap" && !notes.mindmap && !mindmapLoading) {
      fetchMindmap();
    }
  }, [activeTab, notes]);

  const fetchFlashcards = async () => {
    setFlashcardsLoading(true);
    try {
      const data = await api.get<Flashcard[]>(`/videos/${videoId}/notes/flashcards`);
      setNotes(prev => prev ? { ...prev, flashcards: data } : null);
    } catch (err) {
      console.error("Error loading flashcards:", err);
    } finally {
      setFlashcardsLoading(false);
    }
  };

  const fetchQuiz = async () => {
    setQuizLoading(true);
    try {
      const data = await api.get<MCQ[]>(`/videos/${videoId}/notes/quiz`);
      setNotes(prev => prev ? { ...prev, mcqs: data } : null);
    } catch (err) {
      console.error("Error loading quiz:", err);
    } finally {
      setQuizLoading(false);
    }
  };

  const fetchMindmap = async () => {
    setMindmapLoading(true);
    try {
      const data = await api.get<{ mindmap: string }>(`/videos/${videoId}/notes/mindmap`);
      setNotes(prev => prev ? { ...prev, mindmap: data.mindmap } : null);
    } catch (err) {
      console.error("Error loading mindmap:", err);
    } finally {
      setMindmapLoading(false);
    }
  };

  // Handle rendering of Mermaid mind map
  useEffect(() => {
    if (notes?.mindmap && activeTab === "mindmap") {
      renderMindmap();
    }
  }, [notes, activeTab]);

  const loadWorkspaceData = async () => {
    setDataLoading(true);
    try {
      // 1. Fetch Video Metadata
      const videoData = await api.get<VideoDetails>(`/videos/${videoId}`);
      setVideo(videoData);

      // 2. Fetch Transcript
      const transData = await api.get<TranscriptSegment[]>(`/videos/${videoId}/transcript`);
      setTranscript(transData);

      // 3. Fetch Keyframes
      const kfData = await api.get<Keyframe[]>(`/videos/${videoId}/keyframes`);
      setKeyframes(kfData);

      // 4. Fetch Notes
      const notesData = await api.get<NoteOutput>(`/videos/${videoId}/notes`);
      setNotes(notesData);

      // 5. Fetch Chat History
      const chatData = await api.get<ChatMessage[]>(`/chat/${videoId}/messages`);
      setChatMessages(chatData);

    } catch (err) {
      console.error("Error loading workspace resources:", err);
    } finally {
      setDataLoading(false);
    }
  };

  const renderMindmap = async () => {
    if (!notes?.mindmap) return;
    try {
      // Create clean canvas container or remove old container
      const uniqueId = `mermaid-${Date.now()}`;
      // Clean up Mermaid input syntax (ensure no tags or markdown backticks)
      let cleanedSyntax = notes.mindmap.trim();
      if (cleanedSyntax.startsWith("```mermaid")) cleanedSyntax = cleanedSyntax.slice(10);
      if (cleanedSyntax.endsWith("```")) cleanedSyntax = cleanedSyntax.slice(0, -3);
      cleanedSyntax = cleanedSyntax.trim();

      const { svg } = await mermaid.render(uniqueId, cleanedSyntax);
      setMindmapSvg(svg);
    } catch (err) {
      console.error("Mermaid parsing exception:", err);
      setMindmapSvg(`<div class="p-4 rounded-xl border border-red-500/20 bg-red-950/20 text-red-400 text-xs font-semibold">
        Failed to render Mermaid chart syntax. Raw mindmap output:<br/><pre class="mt-2 text-[10px] text-slate-400 select-all">${notes.mindmap}</pre>
      </div>`);
    }
  };

  const handleTimeJump = (seconds: number) => {
    setCurrentTime(seconds);
    
    // Jump HTML5 Video Player
    if (videoPlayerRef.current) {
      videoPlayerRef.current.currentTime = seconds;
      videoPlayerRef.current.play();
    }
    
    // Jump YouTube IFrame player using query postmessage
    if (ytPlayerRef.current && video?.url) {
      const message = JSON.stringify({
        event: "command",
        func: "seekTo",
        args: [seconds, true]
      });
      ytPlayerRef.current.contentWindow?.postMessage(message, "*");
      
      const playMsg = JSON.stringify({
        event: "command",
        func: "playVideo",
        args: []
      });
      ytPlayerRef.current.contentWindow?.postMessage(playMsg, "*");
    }
  };

  const handleExport = async (format: string) => {
    setExportLoading(format);
    try {
      const token = localStorage.getItem("vidnotes_token");
      const res = await fetch(`${BASE_URL}/videos/${videoId}/export/${format}`, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      if (!res.ok) throw new Error("Export failed");
      
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${video?.title.replace(/\s+/g, "_")}_notes.${format === "markdown" ? "md" : format === "docx" ? "docx" : "pdf"}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export error:", err);
      alert("Failed to export notes.");
    } finally {
      setExportLoading(null);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userQuery.trim() || chatLoading) return;
    
    const query = userQuery;
    setUserQuery("");
    setChatLoading(true);

    // Optimistically update list with User query
    const userMsg: ChatMessage = {
      id: Date.now(),
      role: "user",
      content: query,
      citations: null
    };
    setChatMessages(prev => [...prev, userMsg]);

    try {
      const response = await api.post<ChatMessage>(`/chat/${videoId}`, { content: query });
      setChatMessages(prev => [...prev, response]);
    } catch (err) {
      console.error("RAG chatbot error:", err);
      const errorMsg: ChatMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: "I encountered an error querying the RAG transcript chunks. Make sure OpenAI / Gemini keys are valid.",
        citations: null
      };
      setChatMessages(prev => [...prev, errorMsg]);
    } finally {
      setChatLoading(false);
    }
  };

  const formatTimestamp = (sec: number): string => {
    const mins = Math.floor(sec / 60);
    const secs = Math.floor(sec % 60);
    const pad = (num: number) => String(num).padStart(2, '0');
    return `${pad(mins)}:${pad(secs)}`;
  };


  if (authLoading || dataLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 className="animate-spin h-10 w-10 text-indigo-500" />
      </div>
    );
  }

  // Find addressable URL for files (presigned proxy or absolute direct link)
  const fileSourceUrl = video?.file_path 
    ? `${BASE_URL.replace("/api/v1", "")}/vidnotes-storage/${video.file_path}` 
    : "";

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100 font-sans">
      
      {/* Workspace Header */}
      <header className="glass-panel border-b border-slate-900 px-6 py-4 flex items-center justify-between z-20">
        <div className="flex items-center space-x-4 min-w-0">
          <Link href="/dashboard" className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="min-w-0">
            <h1 className="text-sm font-bold text-white truncate max-w-lg">{video?.title}</h1>
            <span className="text-[10px] text-slate-500 block mt-0.5">VidNotes Workspace Workspace ID: {videoId}</span>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => handleExport("markdown")}
            disabled={!!exportLoading}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/40 hover:bg-slate-900 text-slate-400 hover:text-white transition text-xs font-semibold cursor-pointer disabled:opacity-50"
          >
            {exportLoading === "markdown" ? <Loader2 className="animate-spin h-3.5 w-3.5" /> : <Download className="h-3.5 w-3.5" />} MD
          </button>
          <button
            onClick={() => handleExport("pdf")}
            disabled={!!exportLoading}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/40 hover:bg-slate-900 text-slate-400 hover:text-white transition text-xs font-semibold cursor-pointer disabled:opacity-50"
          >
            {exportLoading === "pdf" ? <Loader2 className="animate-spin h-3.5 w-3.5" /> : <Download className="h-3.5 w-3.5" />} PDF
          </button>
          <button
            onClick={() => handleExport("docx")}
            disabled={!!exportLoading}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/40 hover:bg-slate-900 text-slate-400 hover:text-white transition text-xs font-semibold cursor-pointer disabled:opacity-50"
          >
            {exportLoading === "docx" ? <Loader2 className="animate-spin h-3.5 w-3.5" /> : <Download className="h-3.5 w-3.5" />} Word
          </button>
        </div>
      </header>

      {/* Main Workspace Split Grid */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        
        {/* Left Hand Panel (Media Player & Interactive Transcript) */}
        <div className="w-full lg:w-2/5 border-r border-slate-900 flex flex-col overflow-y-auto">
          
          {/* Player Box */}
          <div className="bg-slate-950 aspect-video w-full border-b border-slate-900 relative">
            {video?.url ? (
              // YouTube Embed
              <iframe
                ref={ytPlayerRef}
                src={`https://www.youtube.com/embed/${video.id}?enablejsapi=1&origin=${typeof window !== "undefined" ? window.location.origin : ""}`}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                className="w-full h-full border-0"
              ></iframe>
            ) : video?.file_path ? (
              // HTML5 Native Video Player
              <video
                ref={videoPlayerRef}
                src={fileSourceUrl}
                controls
                className="w-full h-full object-contain"
                onTimeUpdate={(e) => setCurrentTime((e.target as HTMLVideoElement).currentTime)}
              ></video>
            ) : (
              <div className="h-full w-full flex items-center justify-center text-slate-600 text-xs">No media source available</div>
            )}
          </div>

          {/* Synced Timeline Transcript */}
          <div className="flex-1 flex flex-col min-h-0 bg-slate-950/20">
            <div className="p-4 border-b border-slate-900 flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Volume2 className="h-4 w-4 text-indigo-400" /> Interactive Transcript
              </h3>
              <span className="text-[10px] text-slate-500 font-mono">Click sentence to jump time</span>
            </div>

            <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-2">
              {transcript.length === 0 ? (
                <div className="text-slate-600 text-xs py-8 text-center">Transcript data not available for this session.</div>
              ) : (
                transcript.map((seg) => (
                  <button
                    key={seg.id}
                    onClick={() => handleTimeJump(seg.start_time)}
                    className="w-full p-2.5 rounded-lg hover:bg-slate-900/60 transition text-left text-xs leading-relaxed text-slate-300 hover:text-white flex items-start gap-3 group border border-transparent hover:border-slate-800 cursor-pointer"
                  >
                    <span className="font-mono text-indigo-500 text-[10px] font-bold mt-0.5 bg-indigo-500/5 px-2 py-0.5 rounded select-none group-hover:bg-indigo-500/15">
                      {formatTimestamp(seg.start_time)}
                    </span>
                    <span className="flex-1">{seg.text}</span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Middle Panel (Generated Notes & Interactive Study Materials) */}
        <div className="flex-1 border-r border-slate-900 flex flex-col overflow-hidden bg-slate-950/30">
          
          {/* Notes Menu Tabs */}
          <div className="flex border-b border-slate-900 bg-slate-950 overflow-x-auto whitespace-nowrap scrollbar-none">
            {(["summary", "notes", "flashcards", "quiz", "mindmap", "slides"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-5 py-4 border-b-2 font-semibold text-xs transition cursor-pointer capitalize ${
                  activeTab === tab
                    ? "border-indigo-500 text-indigo-400 bg-indigo-500/5"
                    : "border-transparent text-slate-400 hover:text-slate-200"
                }`}
              >
                {tab === "mindmap" ? "Concept Map" : tab === "slides" ? "Key Slides" : tab}
              </button>
            ))}
          </div>

          {/* Notes Content Grid */}
          <div className="flex-1 p-6 overflow-y-auto min-h-0">
            {notes ? (
              <>
                {/* Tab: Summary */}
                {activeTab === "summary" && (
                  <div className="flex flex-col gap-6 max-w-3xl">
                    <div>
                      <h2 className="text-lg font-bold text-white mb-3">Executive Summary</h2>
                      <div className="glass-card p-5 rounded-2xl border border-slate-900 text-slate-300 text-sm leading-relaxed whitespace-pre-line">
                        {notes.summary_exec}
                      </div>
                    </div>

                    <div>
                      <h2 className="text-lg font-bold text-white mb-3">Detailed Lecture Notes</h2>
                      <div className="glass-card p-5 rounded-2xl border border-slate-900 text-slate-300 text-sm leading-relaxed prose prose-invert max-w-none">
                        {parseMarkdown(notes.summary_detailed)}
                      </div>
                    </div>
                  </div>
                )}

                {/* Tab: Study Notes & Checklists */}
                {activeTab === "notes" && (
                  <div className="flex flex-col gap-6 max-w-3xl">
                    <div>
                      <h2 className="text-lg font-bold text-white mb-3">Key Learnings & Takeaways</h2>
                      <div className="glass-card p-5 rounded-2xl border border-slate-900 text-slate-300 text-sm leading-relaxed">
                        {parseMarkdown(notes.takeaways)}
                      </div>
                    </div>

                    <div>
                      <h2 className="text-lg font-bold text-white mb-3">Revision Checklists & Study Tips</h2>
                      <div className="glass-card p-5 rounded-2xl border border-slate-900 text-slate-300 text-sm leading-relaxed">
                        {parseMarkdown(notes.revision_notes)}
                      </div>
                    </div>

                    <div>
                      <h2 className="text-lg font-bold text-white mb-3">Glossary of Key Terms</h2>
                      <div className="glass-card p-5 rounded-2xl border border-slate-900 text-slate-300 text-sm leading-relaxed">
                        {parseMarkdown(notes.glossary)}
                      </div>
                    </div>
                  </div>
                )}

                {/* Tab: Flashcards study area */}
                {activeTab === "flashcards" && (
                  <div className="flex flex-col items-center justify-center h-full max-w-md mx-auto min-h-[300px]">
                    {flashcardsLoading ? (
                      <div className="flex flex-col items-center justify-center gap-3">
                        <Loader2 className="animate-spin h-8 w-8 text-indigo-500" />
                        <span className="text-xs text-slate-500 font-medium">Generating flashcards...</span>
                      </div>
                    ) : notes.flashcards.length === 0 ? (
                      <div className="text-slate-600 text-xs">No Flashcards generated.</div>
                    ) : (
                      <>
                        <div className="text-slate-400 text-xs font-semibold mb-3">
                          Flashcard {activeCardIndex + 1} of {notes.flashcards.length}
                        </div>

                        {/* Interactive Flip Card Card container */}
                        <div 
                          onClick={() => setIsCardFlipped(!isCardFlipped)}
                          className="w-full aspect-[4/3] min-h-[260px] flip-card cursor-pointer"
                        >
                          <div className={`flip-card-inner ${isCardFlipped ? "flipped" : ""}`}>
                            
                            {/* Front Side */}
                            <div className="flip-card-front bg-slate-900 border border-slate-800 shadow-xl flex flex-col items-center justify-center p-6 text-center select-none">
                              <div className="flex flex-col items-center gap-4">
                                <Brain className="h-8 w-8 text-indigo-400" />
                                <p className="text-base font-semibold text-slate-100">{notes.flashcards[activeCardIndex].question}</p>
                                <span className="text-[10px] text-slate-500 uppercase tracking-wider mt-4">Click to reveal answer</span>
                              </div>
                            </div>
                            
                            {/* Back Side */}
                            <div className="flip-card-back bg-slate-950 border border-indigo-500/20 shadow-xl flex items-center justify-center p-6 text-center select-none">
                              <div>
                                <p className="text-sm text-slate-300 leading-relaxed">{notes.flashcards[activeCardIndex].answer}</p>
                                <span className="text-[10px] text-indigo-500 uppercase tracking-wider block mt-6">Click to flip back</span>
                              </div>
                            </div>

                          </div>
                        </div>

                        {/* Pagination Controllers */}
                        <div className="flex gap-4 mt-6 w-full">
                          <button
                            disabled={activeCardIndex === 0}
                            onClick={() => {
                              setIsCardFlipped(false);
                              setTimeout(() => setActiveCardIndex(activeCardIndex - 1), 150);
                            }}
                            className="flex-1 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:bg-slate-900 cursor-pointer disabled:opacity-50 text-xs font-semibold transition"
                          >
                            Previous Card
                          </button>
                          <button
                            disabled={activeCardIndex === notes.flashcards.length - 1}
                            onClick={() => {
                              setIsCardFlipped(false);
                              setTimeout(() => setActiveCardIndex(activeCardIndex + 1), 150);
                            }}
                            className="flex-1 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold cursor-pointer disabled:opacity-50 text-xs transition"
                          >
                            Next Card
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {/* Tab: MCQ Quiz */}
                {activeTab === "quiz" && (
                  <div className="max-w-2xl mx-auto flex flex-col gap-6 min-h-[300px]">
                    {quizLoading ? (
                      <div className="flex flex-col items-center justify-center gap-3 py-12">
                        <Loader2 className="animate-spin h-8 w-8 text-indigo-500" />
                        <span className="text-xs text-slate-500 font-medium">Generating quiz questions...</span>
                      </div>
                    ) : notes.mcqs.length === 0 ? (
                      <div className="text-slate-600 text-xs py-12 text-center">No MCQ Quiz generated for this video.</div>
                    ) : (
                      notes.mcqs.map((mcq, idx) => (
                        <div key={idx} className="glass-card p-5 rounded-2xl border border-slate-900">
                          <h4 className="font-semibold text-sm text-white mb-4">
                            Question {idx + 1}: {mcq.question}
                          </h4>
                          
                          <div className="flex flex-col gap-2.5">
                            {mcq.options.map((opt) => {
                              const isSelected = mcqAnswers[idx] === opt;
                              const isSubmitted = submittedMcqs[idx];
                              const isCorrect = opt === mcq.answer;
                              
                              let buttonStyles = "border border-slate-800 bg-slate-900/30 hover:bg-slate-900/60 text-slate-300";
                              if (isSelected && !isSubmitted) {
                                buttonStyles = "border border-indigo-500 bg-indigo-500/10 text-indigo-400";
                              } else if (isSubmitted) {
                                if (isCorrect) {
                                  buttonStyles = "border border-emerald-500 bg-emerald-500/10 text-emerald-400 cursor-default";
                                } else if (isSelected) {
                                  buttonStyles = "border border-red-500 bg-red-500/10 text-red-400 cursor-default";
                                } else {
                                  buttonStyles = "border border-slate-900 bg-slate-950/40 text-slate-500 cursor-default";
                                }
                              }

                              return (
                                <button
                                  key={opt}
                                  disabled={isSubmitted}
                                  onClick={() => setMcqAnswers({ ...mcqAnswers, [idx]: opt })}
                                  className={`w-full px-4 py-2.5 rounded-lg text-xs font-medium text-left transition ${buttonStyles}`}
                                >
                                  {opt}
                                </button>
                              );
                            })}
                          </div>

                          {!submittedMcqs[idx] && (
                            <button
                              disabled={!mcqAnswers[idx]}
                              onClick={() => setSubmittedMcqs({ ...submittedMcqs, [idx]: true })}
                              className="mt-4 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold text-[10px] rounded-lg cursor-pointer transition"
                            >
                              Check Answer
                            </button>
                          )}

                          {submittedMcqs[idx] && (
                            <div className="mt-4 pt-3 border-t border-slate-900/80">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 block mb-1">Answer explanation</span>
                              <p className="text-xs text-slate-400 leading-relaxed">{mcq.explanation}</p>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* Tab: Concept Map (Mermaid chart canvas) */}
                {activeTab === "mindmap" && (
                  <div className="flex flex-col items-center justify-center min-h-[400px] w-full glass-card p-6 rounded-3xl border border-slate-900 overflow-x-auto">
                    {mindmapLoading ? (
                      <div className="flex flex-col items-center justify-center gap-3">
                        <Loader2 className="animate-spin h-8 w-8 text-indigo-500" />
                        <span className="text-xs text-slate-500 font-medium">Generating concept map...</span>
                      </div>
                    ) : mindmapSvg ? (
                      <div 
                        dangerouslySetInnerHTML={{ __html: mindmapSvg }}
                        className="w-full flex justify-center text-slate-100 svg-container"
                      ></div>
                    ) : (
                      <div className="text-slate-600 text-xs">No mind map generated.</div>
                    )}
                  </div>
                )}

                {/* Tab: Key Slides & Keyframe OCR Log */}
                {activeTab === "slides" && (
                  <div className="flex flex-col gap-8 max-w-3xl">
                    <h2 className="text-lg font-bold text-white">Visual keyframe analysis</h2>
                    {keyframes.length === 0 ? (
                      <div className="text-slate-600 text-xs py-8 text-center">No visuals extracted from this source.</div>
                    ) : (
                      <div className="flex flex-col gap-6">
                        {keyframes.map((kf) => (
                          <div key={kf.id} className="glass-card rounded-2xl border border-slate-900 overflow-hidden flex flex-col md:flex-row">
                            <div className="w-full md:w-2/5 bg-slate-950 aspect-video md:aspect-auto flex items-center justify-center border-b md:border-b-0 md:border-r border-slate-900 relative shrink-0">
                              <img
                                src={getImageUrl(kf.s3_url)}
                                alt={`Frame at ${kf.timestamp}`}
                                className="w-full h-full object-contain"
                              />
                              <button
                                onClick={() => handleTimeJump(kf.timestamp)}
                                className="absolute bottom-2 left-2 flex items-center gap-1.5 px-2 py-1 rounded bg-indigo-600/90 text-white text-[10px] font-bold"
                              >
                                <Play className="h-3 w-3 fill-current" /> {formatTimestamp(kf.timestamp)}
                              </button>
                            </div>
                            
                            <div className="p-4 flex-1 flex flex-col gap-3 min-w-0">
                              <div>
                                <span className="text-[9px] font-bold text-indigo-400 uppercase tracking-wider block mb-1">Slide Visual Description</span>
                                <p className="text-xs text-slate-300 leading-relaxed line-clamp-4">{kf.vision_description}</p>
                              </div>
                              
                              {kf.ocr_text && (
                                <div>
                                  <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block mb-1">OCR Text Found</span>
                                  <div className="bg-slate-950 border border-slate-900 rounded p-2 max-h-16 overflow-y-auto text-[10px] text-slate-400 font-mono leading-tight whitespace-pre-wrap select-all">
                                    {kf.ocr_text}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <div className="h-full w-full flex items-center justify-center text-slate-500 text-sm">Notes payload could not be decoded.</div>
            )}
          </div>
        </div>

        {/* Right Hand Sidebar Panel (Interactive Citation RAG Chat) */}
        <aside className="w-full lg:w-[360px] border-t lg:border-t-0 lg:border-l border-slate-900 bg-slate-950/45 flex flex-col h-[400px] lg:h-auto overflow-hidden">
          
          <div className="p-4 border-b border-slate-900 flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <MessageSquare className="h-4 w-4 text-indigo-400" /> AI Study Chat
            </h3>
            <span className="text-[10px] text-slate-500">RAG Synced Citations</span>
          </div>

          {/* Dialogue list */}
          <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-4 min-h-0 bg-slate-950/20">
            {chatMessages.length === 0 ? (
              <div className="text-slate-600 text-xs py-12 text-center max-w-[240px] mx-auto leading-relaxed">
                Ask a question about this lecture! Our RAG system will locate the exact video timestamps and explain.
              </div>
            ) : (
              chatMessages.map((msg) => (
                <div 
                  key={msg.id}
                  className={`flex flex-col max-w-[85%] rounded-2xl p-3 text-xs leading-relaxed ${
                    msg.role === "user"
                      ? "bg-indigo-600 text-white self-end rounded-br-none"
                      : "bg-slate-900 border border-slate-800 text-slate-200 self-start rounded-bl-none"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  
                  {/* Citations block */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-2.5 pt-2 border-t border-slate-800 flex flex-wrap gap-1.5">
                      {msg.citations.map((cit, cIdx) => (
                        <button
                          key={cIdx}
                          onClick={() => handleTimeJump(cit.start_time)}
                          className="px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-[9px] text-indigo-400 font-bold hover:bg-indigo-500 hover:text-white transition duration-150 flex items-center gap-0.5 cursor-pointer"
                          title={`Cite: "${cit.text.substring(0, 40)}..."`}
                        >
                          <Play className="h-2 w-2 fill-current" /> {formatTimestamp(cit.start_time)}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
            
            {chatLoading && (
              <div className="flex items-center gap-2 p-3 text-xs text-slate-500 bg-slate-900/30 border border-slate-800/40 rounded-2xl self-start">
                <Loader2 className="animate-spin h-3.5 w-3.5" /> AI Search indexing...
              </div>
            )}
          </div>

          {/* Form input */}
          <form onSubmit={handleSendMessage} className="p-4 border-t border-slate-900 bg-slate-950 flex gap-2">
            <input
              type="text"
              value={userQuery}
              onChange={(e) => setUserQuery(e.target.value)}
              placeholder="Ask about this video..."
              required
              className="flex-1 px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 text-slate-200 placeholder-slate-500"
            />
            <button
              type="submit"
              disabled={chatLoading}
              className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition shrink-0 cursor-pointer disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </aside>

      </div>
    </div>
  );
}
