"use client";

import React, { useState, useEffect, useRef, use, useMemo } from "react";
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
  ListRestart,
  RefreshCw,
  Sun,
  Moon,
  Sparkles,
  Copy,
  Check,
  Search,
  CheckCircle2,
  XCircle,
  Lightbulb,
  Code2,
  X,
  ZoomIn
} from "lucide-react";

// Initialize mermaid
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
  const mediaBase = BASE_URL.replace(/\/api\/v1$/, "");

  if (url.includes("X-Amz-Signature") || url.includes("X-Amz-Credential")) {
    return url;
  }

  if (url.includes(".amazonaws.com/")) {
    const key = url.split(".amazonaws.com/")[1];
    return `${BASE_URL}/videos/media/${key}`;
  }

  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  
  if (url.startsWith("/")) {
    if (url.startsWith("/uploads/")) {
      const key = url.replace(/^\/uploads\//, "");
      return `${BASE_URL}/videos/media/${key}`;
    }
    if (mediaBase.startsWith("http")) {
      return `${mediaBase}${url}`;
    }
    return url;
  }
  return `${BASE_URL}/videos/media/${url}`;
};

function parseInlineStyles(text: string, isLight: boolean = false) {
  // Replace inline bold, code, and links
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={idx} className={`font-bold ${isLight ? "text-indigo-950" : "text-white"}`}>
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={idx} className={`px-1.5 py-0.5 rounded text-xs font-mono font-semibold ${isLight ? "bg-indigo-50 text-indigo-700 border border-indigo-200" : "bg-indigo-950/60 text-indigo-300 border border-indigo-800/60"}`}>
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

function CodeSnippet({ code, lang, isLight }: { code: string; lang?: string; isLight: boolean }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`my-4 rounded-xl border overflow-hidden font-mono text-xs ${isLight ? "bg-slate-900 border-slate-700 text-slate-100 shadow-md" : "bg-slate-950 border-slate-800 text-slate-200 shadow-xl"}`}>
      <div className="flex items-center justify-between px-4 py-2 bg-slate-900/90 border-b border-slate-800 text-[11px] text-slate-400">
        <span className="flex items-center gap-1.5 text-indigo-400 font-semibold uppercase tracking-wider">
          <Code2 className="h-3.5 w-3.5" /> {lang || "Code"}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-white transition px-2 py-0.5 rounded hover:bg-slate-800 cursor-pointer"
        >
          {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto text-xs leading-relaxed text-indigo-200/90 whitespace-pre">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function RichMarkdownViewer({ text, isLight }: { text: string; isLight: boolean }) {
  if (!text) return null;

  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // Code block ``` ... ```
    if (trimmed.startsWith("```")) {
      const lang = trimmed.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      elements.push(
        <CodeSnippet key={`code-${i}`} code={codeLines.join("\n")} lang={lang} isLight={isLight} />
      );
      continue;
    }

    // Headings
    if (trimmed.startsWith("#### ")) {
      elements.push(
        <h4 key={i} className={`text-sm font-bold mt-5 mb-2 flex items-center gap-2 ${isLight ? "text-indigo-700" : "text-indigo-300"}`}>
          {parseInlineStyles(trimmed.substring(5), isLight)}
        </h4>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith("### ")) {
      elements.push(
        <h3 key={i} className={`text-base font-bold mt-6 mb-2.5 flex items-center gap-2 pb-1 border-b ${isLight ? "text-slate-900 border-slate-200" : "text-white border-slate-800"}`}>
          {parseInlineStyles(trimmed.substring(4), isLight)}
        </h3>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith("## ")) {
      elements.push(
        <h2 key={i} className={`text-lg font-bold mt-7 mb-3 ${isLight ? "text-slate-900" : "text-white"}`}>
          {parseInlineStyles(trimmed.substring(3), isLight)}
        </h2>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith("# ")) {
      elements.push(
        <h1 key={i} className={`text-xl font-extrabold mt-8 mb-4 text-gradient`}>
          {parseInlineStyles(trimmed.substring(2), isLight)}
        </h1>
      );
      i++;
      continue;
    }

    // Blockquote
    if (trimmed.startsWith("> ")) {
      elements.push(
        <div key={i} className={`my-3 pl-4 py-2 border-l-2 text-xs leading-relaxed italic ${isLight ? "border-indigo-500 bg-indigo-50/50 text-slate-700" : "border-indigo-400 bg-indigo-950/20 text-slate-300"}`}>
          {parseInlineStyles(trimmed.substring(2), isLight)}
        </div>
      );
      i++;
      continue;
    }

    // Images: ![alt](url)
    const imgRegex = /!\[([^\]]*)\]\(([^)]*)\)/;
    const imgMatch = imgRegex.exec(trimmed);
    if (imgMatch) {
      const alt = imgMatch[1] || "Extracted Slide";
      const src = imgMatch[2];
      const resolvedSrc = getImageUrl(src);
      elements.push(
        <div key={i} className={`my-5 rounded-2xl border overflow-hidden shadow-xl max-w-xl group ${isLight ? "border-slate-200 bg-white" : "border-slate-800 bg-slate-950/90"}`}>
          <div className="relative aspect-video bg-black/40 flex items-center justify-center">
            <img 
              src={resolvedSrc} 
              alt={alt} 
              className="w-full h-full object-contain group-hover:scale-[1.01] transition duration-300"
              loading="lazy"
              onError={(e) => {
                const target = e.currentTarget;
                if (!target.src.includes("/uploads/")) {
                  target.src = getImageUrl(src);
                }
              }}
            />
          </div>
          <div className={`px-4 py-2.5 border-t flex items-center justify-between ${isLight ? "bg-slate-50 border-slate-200" : "bg-slate-900/70 border-slate-800"}`}>
            <span className={`text-xs font-semibold ${isLight ? "text-slate-700" : "text-slate-300"}`}>{alt}</span>
            <span className="text-[10px] text-indigo-500 font-mono bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">Slide Visual</span>
          </div>
        </div>
      );
      i++;
      continue;
    }

    // List items
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      elements.push(
        <li key={i} className={`ml-5 list-disc mb-1.5 leading-relaxed text-sm ${isLight ? "text-slate-700" : "text-slate-300"}`}>
          {parseInlineStyles(trimmed.substring(2), isLight)}
        </li>
      );
      i++;
      continue;
    }
    if (/^\d+\.\s+/.test(trimmed)) {
      elements.push(
        <li key={i} className={`ml-5 list-decimal mb-1.5 leading-relaxed text-sm ${isLight ? "text-slate-700" : "text-slate-300"}`}>
          {parseInlineStyles(trimmed.replace(/^\d+\.\s+/, ''), isLight)}
        </li>
      );
      i++;
      continue;
    }

    // Paragraph
    if (trimmed === "") {
      elements.push(<div key={i} className="h-2"></div>);
    } else {
      elements.push(
        <p key={i} className={`mb-2.5 leading-relaxed text-sm ${isLight ? "text-slate-700" : "text-slate-300"}`}>
          {parseInlineStyles(line, isLight)}
        </p>
      );
    }
    i++;
  }

  return <div className="space-y-1">{elements}</div>;
}

const getYoutubeEmbedId = (vidId: string, vidUrl: string | null) => {
  if (vidUrl) {
    const match = vidUrl.match(/(?:v=|\/embed\/|\/watch\?v=|\/v\/|https:\/\/youtu\.be\/|\/shorts\/)([a-zA-Z0-9_-]{11})/);
    if (match && match[1]) return match[1];
  }
  if (vidId && vidId.includes("_")) {
    return vidId.split("_")[0];
  }
  return vidId;
};

export default function Workspace({ params }: PageProps) {
  const router = useRouter();
  const resolvedParams = use(params);
  const videoId = resolvedParams.id;
  const { user, loading: authLoading } = useAuth();

  // Theme state
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved = localStorage.getItem("vidnotes_theme") as "dark" | "light" | null;
    if (saved) {
      setTheme(saved);
    }
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("vidnotes_theme", next);
  };

  const isLight = theme === "light";

  // Core Data
  const [video, setVideo] = useState<VideoDetails | null>(null);
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([]);
  const [keyframes, setKeyframes] = useState<Keyframe[]>([]);
  const [notes, setNotes] = useState<NoteOutput | null>(null);
  
  // Loading states
  const [dataLoading, setDataLoading] = useState(true);
  const [exportLoading, setExportLoading] = useState<string | null>(null);
  const [notesRegenLoading, setNotesRegenLoading] = useState(false);
  const [flashcardsLoading, setFlashcardsLoading] = useState(false);
  const [quizLoading, setQuizLoading] = useState(false);
  const [mindmapLoading, setMindmapLoading] = useState(false);
  
  // Workspace UI Tabs
  const [activeTab, setActiveTab] = useState<"summary" | "notes" | "flashcards" | "quiz" | "mindmap" | "slides">("summary");
  const [selectedSlideZoom, setSelectedSlideZoom] = useState<Keyframe | null>(null);
  
  // Video playback timing
  const [currentTime, setCurrentTime] = useState(0);
  const videoPlayerRef = useRef<HTMLVideoElement | null>(null);
  const ytPlayerRef = useRef<HTMLIFrameElement | null>(null);

  // Transcript Search Filter
  const [transcriptSearch, setTranscriptSearch] = useState("");

  // Chat Panel State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [userQuery, setUserQuery] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);

  // Flashcards Study deck
  const [activeCardIndex, setActiveCardIndex] = useState(0);
  const [isCardFlipped, setIsCardFlipped] = useState(false);

  // MCQ Selection State
  const [mcqAnswers, setMcqAnswers] = useState<Record<number, string>>({});
  const [submittedMcqs, setSubmittedMcqs] = useState<Record<number, boolean>>({});

  // Mermaid SVG render state
  const [mindmapSvg, setMindmapSvg] = useState<string>("");

  // Dynamic Contextual Prompt Suggestions (Derived from video & notes content)
  const promptSuggestions = useMemo(() => {
    const list: { label: string; query: string }[] = [];

    list.push({
      label: "💡 What are the key concepts & main ideas?",
      query: "What are the key concepts and main ideas discussed in this video?"
    });

    if (video?.title && video.title.length > 3 && !video.title.toLowerCase().startsWith("video workspace")) {
      const cleanTitle = video.title.replace(/[^\w\s-]/g, "").trim();
      const shortTitle = cleanTitle.length > 38 ? cleanTitle.slice(0, 38) + "..." : cleanTitle;
      list.push({
        label: `⚡ Explain the core principles of ${shortTitle}`,
        query: `Explain the core principles and details of ${cleanTitle} covered in this lecture.`
      });
    } else {
      list.push({
        label: "⚡ Deep dive into the central topic",
        query: "Provide a detailed deep dive into the primary topic taught in this video."
      });
    }

    if (keyframes && keyframes.length > 0) {
      list.push({
        label: "📊 Explain the visual slides & key diagrams",
        query: "What are the most important slides or visual demonstrations shown in this video?"
      });
    } else {
      list.push({
        label: "💻 Walk me through the practical examples",
        query: "Walk me through the practical examples and applications demonstrated in this video."
      });
    }

    list.push({
      label: "📝 Summarize actionable takeaways with timestamps",
      query: "Summarize the most important actionable takeaways with relevant timestamps from this lecture."
    });

    return list;
  }, [video, keyframes]);

  useEffect(() => {
    if (user && videoId) {
      loadWorkspaceData();
    }
  }, [user, videoId]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, chatLoading]);

  const loadWorkspaceData = async () => {
    setDataLoading(true);
    try {
      const [vData, tData, kData, nData] = await Promise.all([
        api.get<VideoDetails>(`/videos/${videoId}`),
        api.get<TranscriptSegment[]>(`/videos/${videoId}/transcript`).catch(() => []),
        api.get<Keyframe[]>(`/videos/${videoId}/keyframes`).catch(() => []),
        api.get<NoteOutput>(`/videos/${videoId}/notes`).catch(() => null),
      ]);

      setVideo(vData);
      setTranscript(tData);
      setKeyframes(kData);
      if (nData) {
        setNotes(nData);
        if (nData.mindmap) {
          renderMermaid(nData.mindmap);
        }
      }
    } catch (err) {
      console.error("Error loading workspace data:", err);
    } finally {
      setDataLoading(false);
    }
  };

  const fetchFlashcards = async (regenerate: boolean = false) => {
    setFlashcardsLoading(true);
    try {
      const data = await api.get<{ question: string; answer: string }[]>(`/videos/${videoId}/flashcards${regenerate ? "?regenerate=true" : ""}`);
      if (Array.isArray(data) && data.length > 0) {
        setNotes((prev) => (prev ? { ...prev, flashcards: data } : prev));
        setActiveCardIndex(0);
        setIsCardFlipped(false);
      }
    } catch (e) {
      console.error("Failed to load flashcards:", e);
    } finally {
      setFlashcardsLoading(false);
    }
  };

  const fetchQuiz = async (regenerate: boolean = false) => {
    setQuizLoading(true);
    try {
      const data = await api.get<MCQ[]>(`/videos/${videoId}/quiz${regenerate ? "?regenerate=true" : ""}`);
      if (Array.isArray(data) && data.length > 0) {
        setNotes((prev) => (prev ? { ...prev, mcqs: data } : prev));
        setMcqAnswers({});
        setSubmittedMcqs({});
      }
    } catch (e) {
      console.error("Failed to load quiz:", e);
    } finally {
      setQuizLoading(false);
    }
  };

  const fetchMindmap = async (regenerate: boolean = false) => {
    setMindmapLoading(true);
    try {
      const res = await api.get<{ mindmap: string }>(`/videos/${videoId}/mindmap${regenerate ? "?regenerate=true" : ""}`);
      if (res && res.mindmap) {
        setNotes((prev) => (prev ? { ...prev, mindmap: res.mindmap } : prev));
        await renderMermaid(res.mindmap);
      }
    } catch (e) {
      console.error("Failed to load mindmap:", e);
    } finally {
      setMindmapLoading(false);
    }
  };

  const handleTabChange = (tab: "summary" | "notes" | "flashcards" | "quiz" | "mindmap" | "slides") => {
    setActiveTab(tab);
    if (tab === "flashcards" && (!notes?.flashcards || notes.flashcards.length === 0)) {
      fetchFlashcards();
    } else if (tab === "quiz" && (!notes?.mcqs || notes.mcqs.length === 0)) {
      fetchQuiz();
    } else if (tab === "mindmap" && (!notes?.mindmap || !mindmapSvg)) {
      fetchMindmap();
    }
  };

  const renderMermaid = async (chartCode: string) => {
    try {
      const cleanCode = chartCode.replace(/```mermaid/g, "").replace(/```/g, "").trim();
      const uniqueId = `mermaid-${Date.now()}`;
      const { svg } = await mermaid.render(uniqueId, cleanCode);
      setMindmapSvg(svg);
    } catch (err) {
      console.error("Mermaid parsing exception:", err);
    }
  };

  const handleTimeJump = (timestamp: number) => {
    setCurrentTime(timestamp);
    if (videoPlayerRef.current) {
      videoPlayerRef.current.currentTime = timestamp;
      videoPlayerRef.current.play().catch(() => {});
    } else if (ytPlayerRef.current && ytPlayerRef.current.contentWindow) {
      ytPlayerRef.current.contentWindow.postMessage(
        JSON.stringify({ event: "command", func: "seekTo", args: [timestamp, true] }),
        "*"
      );
    }
  };

  const handleExport = async (format: "markdown" | "pdf" | "docx") => {
    setExportLoading(format);
    try {
      const blob = await api.downloadBlob(`/videos/${videoId}/export/${format}`);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${video?.title || "VidNotes"}_export.${format === "markdown" ? "md" : format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (err) {
      console.error(`Export ${format} error:`, err);
    } finally {
      setExportLoading(null);
    }
  };

  const handleSendMessage = async (e?: React.FormEvent, customQuery?: string) => {
    if (e) e.preventDefault();
    const query = (customQuery || userQuery).trim();
    if (!query || chatLoading) return;
    
    setUserQuery("");
    setChatLoading(true);

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
        content: "I encountered an error querying the video transcript. Please try again.",
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

  const filteredTranscript = transcript.filter((seg) =>
    seg.text.toLowerCase().includes(transcriptSearch.toLowerCase())
  );

  if (authLoading || dataLoading) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${isLight ? "bg-slate-50 text-slate-900" : "bg-slate-950 text-white"}`}>
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="animate-spin h-10 w-10 text-indigo-500" />
          <span className="text-xs font-semibold text-indigo-400 tracking-wider uppercase">Loading Workspace...</span>
        </div>
      </div>
    );
  }

  const fileSourceUrl = video?.file_path 
    ? `${BASE_URL.replace("/api/v1", "")}/vidnotes-storage/${video.file_path}` 
    : "";

  return (
    <div className={`h-screen max-h-screen flex flex-col font-sans overflow-hidden ${theme}`}>
      
      {/* 1. Global Glossy Workspace Header */}
      <header className={`h-14 px-5 flex items-center justify-between border-b shrink-0 z-30 ${isLight ? "bg-white/90 border-slate-200 backdrop-blur-xl" : "glossy-panel border-b border-white/10"}`}>
        <div className="flex items-center space-x-3 min-w-0">
          <Link href="/dashboard" className={`p-2 rounded-xl border transition ${isLight ? "bg-slate-100 hover:bg-slate-200 border-slate-200 text-slate-700" : "bg-slate-900/80 hover:bg-slate-800 border-white/10 text-slate-400 hover:text-white shadow-sm"}`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="min-w-0">
            <h1 className={`text-xs sm:text-sm font-bold truncate max-w-sm sm:max-w-lg ${isLight ? "text-slate-900" : "text-gradient"}`}>
              {video?.title || "Video Workspace"}
            </h1>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 font-semibold">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span> Ready
              </span>
              <span className={`text-[10px] ${isLight ? "text-slate-400" : "text-slate-500"}`}>• ID: {videoId}</span>
            </div>
          </div>
        </div>

        {/* Right Action Bar: Theme Toggle & Exports */}
        <div className="flex items-center space-x-2">
          <button
            onClick={toggleTheme}
            className={`p-2 rounded-xl border transition cursor-pointer ${isLight ? "bg-slate-100 hover:bg-slate-200 border-slate-300 text-slate-800" : "bg-slate-900/80 hover:bg-slate-800 border-white/10 text-amber-400 shadow-sm"}`}
            title={`Switch to ${isLight ? "Dark" : "Light"} mode`}
          >
            {isLight ? <Moon className="h-4 w-4 text-indigo-600" /> : <Sun className="h-4 w-4" />}
          </button>

          <div className={`flex items-center rounded-xl border p-0.5 ${isLight ? "bg-slate-100 border-slate-200" : "bg-slate-900/80 border-white/10 shadow-sm"}`}>
            <button
              onClick={() => handleExport("markdown")}
              disabled={!!exportLoading}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer disabled:opacity-50 ${isLight ? "hover:bg-slate-200 text-slate-700" : "hover:bg-slate-800 text-slate-300 hover:text-white"}`}
            >
              {exportLoading === "markdown" ? <Loader2 className="animate-spin h-3.5 w-3.5" /> : <Download className="h-3.5 w-3.5" />} MD
            </button>
            <button
              onClick={() => handleExport("pdf")}
              disabled={!!exportLoading}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer disabled:opacity-50 ${isLight ? "hover:bg-slate-200 text-slate-700" : "hover:bg-slate-800 text-slate-300 hover:text-white"}`}
            >
              {exportLoading === "pdf" ? <Loader2 className="animate-spin h-3.5 w-3.5" /> : <Download className="h-3.5 w-3.5" />} PDF
            </button>
            <button
              onClick={() => handleExport("docx")}
              disabled={!!exportLoading}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer disabled:opacity-50 ${isLight ? "hover:bg-slate-200 text-slate-700" : "hover:bg-slate-800 text-slate-300 hover:text-white"}`}
            >
              {exportLoading === "docx" ? <Loader2 className="animate-spin h-3.5 w-3.5" /> : <Download className="h-3.5 w-3.5" />} DOCX
            </button>
          </div>
        </div>
      </header>

      {/* 2. Main 3-Column Viewport Split with Independent Scrollbars */}
      <div className="flex-1 flex flex-col lg:flex-row h-[calc(100vh-56px)] overflow-hidden">
        
        {/* ========================================================================= */}
        {/* LEFT COLUMN: Pinned Media Player & Interactive Transcript (380px)        */}
        {/* ========================================================================= */}
        <div className={`w-full lg:w-[380px] xl:w-[410px] border-r flex flex-col h-full overflow-hidden shrink-0 ${isLight ? "bg-slate-50 border-slate-200" : "bg-slate-950/40 border-white/10 backdrop-blur-xl"}`}>
          
          {/* Pinned Aspect Video Box */}
          <div className="aspect-video w-full border-b border-white/10 bg-black relative shrink-0 shadow-lg">
            {video?.url ? (
              <iframe
                ref={ytPlayerRef}
                src={`https://www.youtube.com/embed/${getYoutubeEmbedId(video.id, video.url)}?enablejsapi=1&origin=${typeof window !== "undefined" ? window.location.origin : ""}`}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                className="w-full h-full border-0"
              ></iframe>
            ) : video?.file_path ? (
              <video
                ref={videoPlayerRef}
                src={fileSourceUrl}
                controls
                className="w-full h-full object-contain"
                onTimeUpdate={(e) => setCurrentTime((e.target as HTMLVideoElement).currentTime)}
              ></video>
            ) : (
              <div className="h-full w-full flex items-center justify-center text-slate-500 text-xs">No media source available</div>
            )}
          </div>

          {/* Independent Scrollable Interactive Transcript */}
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <div className={`p-3 border-b flex items-center justify-between shrink-0 ${isLight ? "bg-white border-slate-200" : "bg-slate-950/70 border-white/10"}`}>
              <h3 className={`text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 ${isLight ? "text-indigo-900" : "text-indigo-400"}`}>
                <Volume2 className="h-4 w-4 text-indigo-400" /> Interactive Transcript
              </h3>
              <span className="text-[10px] text-slate-400 font-mono bg-white/5 px-2 py-0.5 rounded-full border border-white/10">{transcript.length} segs</span>
            </div>

            {/* Transcript Search Filter */}
            <div className={`px-3 py-2 border-b shrink-0 ${isLight ? "bg-slate-50 border-slate-200" : "bg-slate-950/50 border-white/10"}`}>
              <div className="relative">
                <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter transcript..."
                  value={transcriptSearch}
                  onChange={(e) => setTranscriptSearch(e.target.value)}
                  className={`w-full pl-8 pr-3 py-1.5 rounded-xl text-xs border focus:outline-none focus:ring-1 focus:ring-indigo-500 ${isLight ? "bg-white border-slate-300 text-slate-800 placeholder-slate-400" : "bg-slate-900/80 border-white/10 text-slate-200 placeholder-slate-500 shadow-inner"}`}
                />
              </div>
            </div>

            {/* Transcript Scroll Area */}
            <div className="flex-1 p-3 overflow-y-auto flex flex-col gap-1.5">
              {filteredTranscript.length === 0 ? (
                <div className="text-slate-500 text-xs py-8 text-center">No matching transcript segments found.</div>
              ) : (
                filteredTranscript.map((seg) => (
                  <button
                    key={seg.id}
                    onClick={() => handleTimeJump(seg.start_time)}
                    className={`w-full p-2.5 rounded-xl text-left text-xs leading-relaxed transition flex items-start gap-2.5 group cursor-pointer border ${
                      currentTime >= seg.start_time && currentTime <= seg.end_time
                        ? "bg-indigo-600/25 border-indigo-400/50 shadow-md shadow-indigo-500/10 text-white"
                        : isLight
                        ? "hover:bg-white border-transparent hover:border-slate-200 text-slate-700"
                        : "hover:bg-slate-900/60 border-transparent hover:border-white/10 text-slate-300"
                    }`}
                  >
                    <span className="font-mono text-indigo-400 text-[10px] font-bold mt-0.5 bg-indigo-500/15 px-2 py-0.5 rounded-lg shrink-0 border border-indigo-500/20">
                      {formatTimestamp(seg.start_time)}
                    </span>
                    <span className="flex-1">{seg.text}</span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* CENTER COLUMN: Notes & Study Material Tab Hub (Scrolls independently)     */}
        {/* ========================================================================= */}
        <div className={`flex-1 border-r flex flex-col h-full overflow-hidden min-w-0 ${isLight ? "bg-slate-100/40 border-slate-200" : "bg-slate-950/20 border-white/10"}`}>
          
          {/* Notes Menu Tabs Navigation (Glossy Floating Pills) */}
          <div className={`flex border-b px-4 shrink-0 overflow-x-auto whitespace-nowrap scrollbar-none gap-2 py-2.5 ${isLight ? "bg-white border-slate-200" : "bg-slate-950/80 border-white/10 backdrop-blur-xl"}`}>
            {(["summary", "notes", "flashcards", "quiz", "mindmap", "slides"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => handleTabChange(tab)}
                className={`px-4 py-2 rounded-xl font-bold text-xs transition cursor-pointer capitalize flex items-center gap-1.5 ${
                  activeTab === tab
                    ? "glossy-tab-active"
                    : isLight
                    ? "text-slate-600 hover:bg-slate-100"
                    : "glossy-tab-inactive"
                }`}
              >
                {tab === "summary" && <FileText className="h-3.5 w-3.5" />}
                {tab === "notes" && <Bookmark className="h-3.5 w-3.5" />}
                {tab === "flashcards" && <Brain className="h-3.5 w-3.5" />}
                {tab === "quiz" && <HelpCircle className="h-3.5 w-3.5" />}
                {tab === "mindmap" && <Layers className="h-3.5 w-3.5" />}
                {tab === "slides" && <Video className="h-3.5 w-3.5" />}
                {tab === "mindmap" ? "Concept Map" : tab === "slides" ? "Key Slides" : tab}
              </button>
            ))}
          </div>

          {/* Notes Independent Content Area */}
          <div className="flex-1 p-6 overflow-y-auto min-h-0">
            {notes ? (
              <div className="max-w-3xl mx-auto space-y-6 pb-12">
                
                {/* TAB 1: Summary */}
                {activeTab === "summary" && (
                  <div className="space-y-6">
                    <div>
                      <h2 className={`text-base font-bold mb-3 flex items-center gap-2 ${isLight ? "text-slate-900" : "text-white"}`}>
                        <Lightbulb className="h-4 w-4 text-indigo-400" /> Executive Overview
                      </h2>
                      <div className={`p-5 rounded-2xl border text-sm leading-relaxed whitespace-pre-line shadow-sm ${isLight ? "bg-white border-slate-200 text-slate-800" : "glossy-card text-slate-200"}`}>
                        {notes.summary_exec}
                      </div>
                    </div>

                    <div>
                      <h2 className={`text-base font-bold mb-3 flex items-center gap-2 ${isLight ? "text-slate-900" : "text-white"}`}>
                        <FileText className="h-4 w-4 text-indigo-400" /> Comprehensive Lecture Notes & Visual Breakdown
                      </h2>
                      <div className={`p-6 rounded-2xl border text-sm leading-relaxed shadow-sm ${isLight ? "bg-white border-slate-200 text-slate-800" : "glossy-card text-slate-200"}`}>
                        <RichMarkdownViewer text={notes.summary_detailed} isLight={isLight} />
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 2: Study Notes */}
                {activeTab === "notes" && (
                  <div className="space-y-6">
                    <div>
                      <h2 className={`text-base font-bold mb-3 ${isLight ? "text-slate-900" : "text-white"}`}>Key Learnings & Takeaways</h2>
                      <div className={`p-5 rounded-2xl border text-sm leading-relaxed shadow-sm ${isLight ? "bg-white border-slate-200" : "glossy-card text-slate-200"}`}>
                        <RichMarkdownViewer text={notes.takeaways} isLight={isLight} />
                      </div>
                    </div>

                    <div>
                      <h2 className={`text-base font-bold mb-3 ${isLight ? "text-slate-900" : "text-white"}`}>Revision Checklist</h2>
                      <div className={`p-5 rounded-2xl border text-sm leading-relaxed shadow-sm ${isLight ? "bg-white border-slate-200" : "glossy-card text-slate-200"}`}>
                        <RichMarkdownViewer text={notes.revision_notes} isLight={isLight} />
                      </div>
                    </div>

                    <div>
                      <h2 className={`text-base font-bold mb-3 ${isLight ? "text-slate-900" : "text-white"}`}>Glossary of Terms</h2>
                      <div className={`p-5 rounded-2xl border text-sm leading-relaxed shadow-sm ${isLight ? "bg-white border-slate-200" : "glossy-card text-slate-200"}`}>
                        <RichMarkdownViewer text={notes.glossary} isLight={isLight} />
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 3: Flashcards */}
                {activeTab === "flashcards" && (
                  <div className="flex flex-col items-center justify-center min-h-[380px] max-w-md mx-auto">
                    <div className="w-full flex items-center justify-between mb-4">
                      <h2 className={`text-base font-bold flex items-center gap-2 ${isLight ? "text-slate-900" : "text-white"}`}>
                        <Brain className="h-4 w-4 text-indigo-400" /> Active Recall Flashcards
                      </h2>
                      <button
                        onClick={() => fetchFlashcards(true)}
                        disabled={flashcardsLoading}
                        className="flex items-center gap-1 px-3 py-1 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 text-xs font-bold transition cursor-pointer disabled:opacity-50"
                      >
                        <RefreshCw className={`h-3 w-3 ${flashcardsLoading ? "animate-spin" : ""}`} /> Regenerate
                      </button>
                    </div>

                    {flashcardsLoading ? (
                      <div className="flex flex-col items-center justify-center py-16 gap-3">
                        <Loader2 className="animate-spin h-8 w-8 text-indigo-500" />
                        <span className="text-xs text-slate-400 font-medium">Generating active recall flashcards...</span>
                      </div>
                    ) : notes.flashcards && notes.flashcards.length > 0 ? (
                      <div className="w-full space-y-4">
                        <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
                          <span>Card {activeCardIndex + 1} of {notes.flashcards.length}</span>
                          <span className="text-indigo-400">Click card to flip</span>
                        </div>

                        <div 
                          onClick={() => setIsCardFlipped(!isCardFlipped)}
                          className="w-full aspect-[4/3] flip-card cursor-pointer"
                        >
                          <div className={`flip-card-inner ${isCardFlipped ? "flipped" : ""}`}>
                            {/* Front */}
                            <div className={`flip-card-front border p-8 flex flex-col items-center justify-center text-center shadow-xl ${isLight ? "bg-white border-slate-200 text-slate-900" : "glossy-card border-white/10 text-white"}`}>
                              <Brain className="h-8 w-8 text-indigo-400 mb-4" />
                              <p className="text-base font-bold">{notes.flashcards[activeCardIndex].question}</p>
                              <span className="text-[11px] text-slate-400 mt-6 font-medium">Click to reveal answer ↺</span>
                            </div>

                            {/* Back */}
                            <div className="flip-card-back border border-indigo-400/40 p-8 bg-gradient-to-br from-indigo-600 to-purple-600 text-white flex flex-col items-center justify-center text-center shadow-2xl">
                              <Sparkles className="h-8 w-8 text-amber-300 mb-4" />
                              <p className="text-sm font-semibold leading-relaxed">{notes.flashcards[activeCardIndex].answer}</p>
                            </div>
                          </div>
                        </div>

                        {/* Controls */}
                        <div className="flex items-center justify-between pt-2">
                          <button
                            onClick={() => {
                              setIsCardFlipped(false);
                              setActiveCardIndex((prev) => (prev > 0 ? prev - 1 : notes.flashcards.length - 1));
                            }}
                            className={`px-4 py-2 rounded-xl text-xs font-bold border transition ${isLight ? "bg-white hover:bg-slate-100 border-slate-300" : "glossy-tab-inactive"}`}
                          >
                            Previous
                          </button>
                          <button
                            onClick={() => {
                              setIsCardFlipped(false);
                              setActiveCardIndex((prev) => (prev < notes.flashcards.length - 1 ? prev + 1 : 0));
                            }}
                            className="px-5 py-2 rounded-xl text-xs font-bold glossy-tab-active shadow-md transition"
                          >
                            Next Card
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-12 space-y-3">
                        <p className="text-slate-400 text-xs">No flashcards found for this lecture.</p>
                        <button
                          onClick={() => fetchFlashcards(true)}
                          className="px-4 py-2 rounded-xl glossy-tab-active text-xs font-bold transition shadow"
                        >
                          Generate Flashcard Deck
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* TAB 4: Quiz */}
                {activeTab === "quiz" && (
                  <div className="space-y-6">
                    <div className="flex items-center justify-between">
                      <h2 className={`text-base font-bold flex items-center gap-2 ${isLight ? "text-slate-900" : "text-white"}`}>
                        <HelpCircle className="h-4 w-4 text-indigo-400" /> Interactive Assessment Quiz
                      </h2>
                      <button
                        onClick={() => fetchQuiz(true)}
                        disabled={quizLoading}
                        className="flex items-center gap-1 px-3 py-1 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 text-xs font-bold transition cursor-pointer disabled:opacity-50"
                      >
                        <RefreshCw className={`h-3 w-3 ${quizLoading ? "animate-spin" : ""}`} /> Regenerate
                      </button>
                    </div>

                    {quizLoading ? (
                      <div className="flex flex-col items-center justify-center py-16 gap-3">
                        <Loader2 className="animate-spin h-8 w-8 text-indigo-500" />
                        <span className="text-xs text-slate-400 font-medium">Generating interactive quiz questions...</span>
                      </div>
                    ) : notes.mcqs && notes.mcqs.length > 0 ? (
                      notes.mcqs.map((mcq, mIdx) => {
                        const selected = mcqAnswers[mIdx];
                        const isSubmitted = submittedMcqs[mIdx];
                        return (
                          <div key={mIdx} className={`p-5 rounded-2xl border shadow-sm space-y-4 ${isLight ? "bg-white border-slate-200" : "glossy-card"}`}>
                            <p className="text-sm font-bold">{mIdx + 1}. {mcq.question}</p>
                            <div className="space-y-2">
                              {mcq.options.map((opt, oIdx) => {
                                const isCorrect = opt === mcq.answer;
                                const isChosen = selected === opt;
                                let btnStyle = isLight 
                                  ? "bg-slate-50 border-slate-200 hover:bg-slate-100 text-slate-800" 
                                  : "bg-slate-900/60 border-white/10 hover:bg-slate-800 text-slate-200";

                                if (isSubmitted) {
                                  if (isCorrect) btnStyle = "bg-emerald-500/20 border-emerald-500/50 text-emerald-300";
                                  else if (isChosen) btnStyle = "bg-rose-500/20 border-rose-500/50 text-rose-300";
                                } else if (isChosen) {
                                  btnStyle = "bg-indigo-600/30 border-indigo-500 text-indigo-300";
                                }

                                return (
                                  <button
                                    key={oIdx}
                                    disabled={isSubmitted}
                                    onClick={() => setMcqAnswers(prev => ({ ...prev, [mIdx]: opt }))}
                                    className={`w-full p-3 rounded-xl border text-xs text-left transition flex items-center justify-between cursor-pointer ${btnStyle}`}
                                  >
                                    <span>{opt}</span>
                                    {isSubmitted && isCorrect && <Check className="h-4 w-4 text-emerald-400" />}
                                    {isSubmitted && isChosen && !isCorrect && <X className="h-4 w-4 text-rose-400" />}
                                  </button>
                                );
                              })}
                            </div>

                            {!isSubmitted ? (
                              <button
                                disabled={!selected}
                                onClick={() => setSubmittedMcqs(prev => ({ ...prev, [mIdx]: true }))}
                                className="px-4 py-2 rounded-xl glossy-tab-active text-xs font-bold transition disabled:opacity-40 cursor-pointer shadow-md"
                              >
                                Check Answer
                              </button>
                            ) : (
                              <div className={`p-3 rounded-xl text-xs leading-relaxed border ${isLight ? "bg-indigo-50 border-indigo-200 text-slate-800" : "bg-indigo-950/40 border-indigo-500/30 text-slate-200"}`}>
                                <span className="font-bold text-indigo-400 block mb-1">Explanation:</span>
                                {mcq.explanation}
                              </div>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      <div className="text-center py-12 space-y-3">
                        <p className="text-slate-400 text-xs">No quiz questions generated.</p>
                        <button
                          onClick={() => fetchQuiz(true)}
                          className="px-4 py-2 rounded-xl glossy-tab-active text-xs font-bold transition shadow"
                        >
                          Generate Quiz
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* TAB 5: Mind Map */}
                {activeTab === "mindmap" && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h2 className={`text-base font-bold ${isLight ? "text-slate-900" : "text-white"}`}>Interactive Concept Map</h2>
                      <button
                        onClick={() => fetchMindmap(true)}
                        disabled={mindmapLoading}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 text-xs font-bold transition cursor-pointer disabled:opacity-50"
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${mindmapLoading ? "animate-spin" : ""}`} /> Regenerate Map
                      </button>
                    </div>

                    <div className={`p-6 rounded-2xl border overflow-x-auto flex items-center justify-center min-h-[400px] shadow-sm ${isLight ? "bg-white border-slate-200" : "glossy-card border-white/10"}`}>
                      {mindmapLoading ? (
                        <div className="flex flex-col items-center justify-center gap-3">
                          <Loader2 className="animate-spin h-8 w-8 text-indigo-500" />
                          <span className="text-xs text-slate-400 font-medium">Synthesizing interactive concept map...</span>
                        </div>
                      ) : mindmapSvg ? (
                        <div dangerouslySetInnerHTML={{ __html: mindmapSvg }} className="w-full flex justify-center" />
                      ) : (
                        <div className="text-center py-12 space-y-3">
                          <p className="text-slate-400 text-xs">Concept map diagram not available.</p>
                          <button
                            onClick={() => fetchMindmap(true)}
                            className="px-4 py-2 rounded-xl glossy-tab-active text-xs font-bold transition shadow"
                          >
                            Generate Concept Map
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* TAB 6: Key Slides */}
                {activeTab === "slides" && (
                  <div className="space-y-4">
                    <h2 className={`text-base font-bold ${isLight ? "text-slate-900" : "text-white"}`}>Key Video Slides ({keyframes.length})</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {keyframes.map((kf) => (
                        <div key={kf.id} className={`rounded-2xl border overflow-hidden shadow-sm flex flex-col ${isLight ? "bg-white border-slate-200" : "glossy-card"}`}>
                          <div className="aspect-video relative bg-black/60 flex items-center justify-center">
                            <img
                              src={getImageUrl(kf.s3_url)}
                              alt={`Slide at ${formatTimestamp(kf.timestamp)}`}
                              className="w-full h-full object-contain"
                              loading="lazy"
                              onError={(e) => {
                                (e.target as HTMLImageElement).src = "/uploads/placeholder_slide.jpg";
                              }}
                            />
                            <div className="absolute top-2.5 left-2.5">
                              <span className="font-mono text-xs font-bold bg-black/70 text-indigo-400 px-2 py-0.5 rounded-md border border-white/10 backdrop-blur-md">
                                {formatTimestamp(kf.timestamp)}
                              </span>
                            </div>
                            <button
                              onClick={() => setSelectedSlideZoom(kf)}
                              className="absolute top-2.5 right-2.5 p-1.5 rounded-lg bg-black/60 hover:bg-black/80 text-white backdrop-blur-md border border-white/10 transition cursor-pointer"
                              title="Zoom Slide"
                            >
                              <ZoomIn className="h-3.5 w-3.5" />
                            </button>
                          </div>

                          <div className="p-3.5 flex-1 flex flex-col justify-between gap-2 border-t border-white/5">
                            <p className={`text-xs leading-relaxed line-clamp-2 ${isLight ? "text-slate-700" : "text-slate-300"}`}>
                              {kf.vision_description || "Visual keyframe extracted from video lecture."}
                            </p>
                            <button
                              onClick={() => handleTimeJump(kf.timestamp)}
                              className="self-start flex items-center gap-1 text-[11px] font-bold text-indigo-400 hover:text-indigo-300 transition cursor-pointer"
                            >
                              <Play className="h-3 w-3 fill-current" /> Jump to {formatTimestamp(kf.timestamp)}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              </div>
            ) : (
              <div className="text-center py-20 text-slate-500 text-xs">No notes generated for this video.</div>
            )}
          </div>
        </div>

        {/* ========================================================================= */}
        {/* RIGHT COLUMN: Interactive AI Study Copilot (Chatbot RAG) (340px)          */}
        {/* ========================================================================= */}
        <aside className={`w-full lg:w-[340px] xl:w-[360px] flex flex-col h-full overflow-hidden shrink-0 ${isLight ? "bg-white border-slate-200" : "bg-slate-950/40 border-white/10 backdrop-blur-xl"}`}>
          
          {/* Glossy Header with AI Avatar Pulse */}
          <div className={`p-3.5 border-b flex items-center justify-between shrink-0 ${isLight ? "bg-slate-50/80 border-slate-200" : "bg-slate-950/80 border-white/10"}`}>
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-500 flex items-center justify-center shadow-lg shadow-indigo-500/20 ai-avatar-pulse border border-white/20">
                <Sparkles className="h-4 w-4 text-white" />
              </div>
              <div>
                <h3 className={`text-xs font-bold flex items-center gap-1.5 ${isLight ? "text-slate-900" : "text-white"}`}>
                  AI Study Copilot
                </h3>
                <span className="text-[10px] text-emerald-400 font-semibold flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping"></span> Live RAG Citations
                </span>
              </div>
            </div>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-md border ${isLight ? "bg-slate-100 text-slate-600 border-slate-300" : "bg-slate-900 text-slate-400 border-white/10"}`}>
              v2.5 Synced
            </span>
          </div>

          {/* Chat Messages Feed (Independent Scroll Container) */}
          <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-4 min-h-0">
            {chatMessages.length === 0 ? (
              <div className="my-auto text-center space-y-4 py-8">
                <div className="h-12 w-12 rounded-2xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center mx-auto text-indigo-400 shadow-inner">
                  <MessageSquare className="h-6 w-6" />
                </div>
                <div className="space-y-1">
                  <h4 className={`text-xs font-bold ${isLight ? "text-slate-800" : "text-slate-200"}`}>Ask anything about this video</h4>
                  <p className="text-[11px] text-slate-400 max-w-[220px] mx-auto leading-relaxed">
                    AI will instantly search transcript moments and explain with video timestamps.
                  </p>
                </div>

                {/* Dynamic Quick Prompt Suggestion Pills */}
                <div className="flex flex-col gap-1.5 pt-2">
                  {promptSuggestions.map((prompt, pIdx) => (
                    <button
                      key={pIdx}
                      onClick={() => handleSendMessage(undefined, prompt.query)}
                      className={`text-xs text-left px-3 py-2 rounded-xl border transition cursor-pointer font-medium ${
                        isLight
                          ? "bg-slate-50 hover:bg-indigo-50 hover:border-indigo-300 text-slate-700"
                          : "glossy-tab-inactive hover:border-indigo-500/40 text-slate-300"
                      }`}
                    >
                      {prompt.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              chatMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col max-w-[90%] rounded-2xl p-3.5 text-xs leading-relaxed shadow-sm ${
                    msg.role === "user"
                      ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white self-end rounded-br-none font-medium shadow-md shadow-indigo-600/20 border border-white/20"
                      : isLight
                      ? "bg-white border border-slate-200 text-slate-800 self-start rounded-bl-none shadow"
                      : "glossy-card border-indigo-500/20 text-slate-200 self-start rounded-bl-none shadow-lg"
                  }`}
                >
                  <RichMarkdownViewer text={msg.content} isLight={isLight && msg.role !== "user"} />
                  
                  {/* Clickable Citations Badge Block */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-indigo-500/20 flex flex-wrap gap-1.5">
                      {msg.citations.map((cit, cIdx) => (
                        <button
                          key={cIdx}
                          onClick={() => handleTimeJump(cit.start_time)}
                          className="px-2.5 py-1 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-[10px] text-indigo-400 font-bold hover:bg-indigo-600 hover:text-white transition flex items-center gap-1 cursor-pointer"
                        >
                          <Play className="h-2.5 w-2.5 fill-current" /> {formatTimestamp(cit.start_time)}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}

            {chatLoading && (
              <div className={`flex items-center gap-2 p-3 rounded-2xl text-xs border self-start ${isLight ? "bg-slate-100 border-slate-200 text-slate-600" : "glossy-card border-indigo-500/30 text-indigo-300"}`}>
                <Loader2 className="animate-spin h-3.5 w-3.5 text-indigo-400" /> AI Synthesizing answer...
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Glowing Glossy Chat Input Bar */}
          <form onSubmit={(e) => handleSendMessage(e)} className={`p-3 border-t shrink-0 ${isLight ? "bg-slate-50 border-slate-200" : "bg-slate-950/80 border-white/10"}`}>
            <div className={`flex items-center rounded-xl border p-1.5 transition ai-glow-border ${isLight ? "bg-white border-slate-300" : "bg-slate-900/90 border-white/10"}`}>
              <input
                type="text"
                value={userQuery}
                onChange={(e) => setUserQuery(e.target.value)}
                placeholder="Ask about this video..."
                required
                className={`flex-1 px-3 py-1.5 bg-transparent text-xs focus:outline-none ${isLight ? "text-slate-900 placeholder-slate-400" : "text-slate-100 placeholder-slate-500"}`}
              />
              <button
                type="submit"
                disabled={chatLoading}
                className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition shrink-0 cursor-pointer disabled:opacity-40 shadow-sm"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </div>
            <span className="text-[9px] text-slate-500 block text-center mt-1.5">Press ↵ to send • Click timestamps to jump playback</span>
          </form>
        </aside>
      </div>

      {/* Glossy Slide Zoom Modal */}
      {selectedSlideZoom && (
        <div 
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xl flex items-center justify-center p-4 sm:p-6 transition-all animate-in fade-in duration-200"
          onClick={() => setSelectedSlideZoom(null)}
        >
          <div 
            className={`relative max-w-4xl w-full max-h-[90vh] rounded-3xl overflow-hidden flex flex-col border shadow-2xl ${isLight ? "bg-white border-slate-200" : "glossy-panel border-white/20"}`}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className={`p-4 border-b flex items-center justify-between shrink-0 ${isLight ? "bg-slate-50 border-slate-200" : "bg-slate-950/80 border-white/10"}`}>
              <div className="flex items-center gap-2.5">
                <span className="font-mono text-xs font-bold bg-indigo-500/20 text-indigo-400 px-2.5 py-1 rounded-lg border border-indigo-500/30">
                  {formatTimestamp(selectedSlideZoom.timestamp)}
                </span>
                <span className={`text-xs font-semibold truncate ${isLight ? "text-slate-800" : "text-slate-200"}`}>
                  Slide Preview & Vision Breakdown
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    handleTimeJump(selectedSlideZoom.timestamp);
                    setSelectedSlideZoom(null);
                  }}
                  className="px-3 py-1.5 rounded-xl glossy-tab-active text-xs font-bold transition flex items-center gap-1.5 shadow-md cursor-pointer"
                >
                  <Play className="h-3 w-3 fill-current" /> Jump in Video
                </button>
                <button
                  onClick={() => setSelectedSlideZoom(null)}
                  className={`p-1.5 rounded-xl border transition cursor-pointer ${isLight ? "bg-slate-100 hover:bg-slate-200 border-slate-200 text-slate-700" : "bg-slate-900 hover:bg-slate-800 border-white/10 text-slate-400 hover:text-white"}`}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Modal Image Display */}
            <div className="flex-1 bg-black/90 relative flex items-center justify-center p-2 min-h-[350px] overflow-hidden">
              <img
                src={getImageUrl(selectedSlideZoom.s3_url)}
                alt={`Slide at ${formatTimestamp(selectedSlideZoom.timestamp)}`}
                className="max-h-[65vh] w-auto object-contain rounded-lg shadow-2xl"
              />
            </div>

            {/* Modal Footer Description */}
            {selectedSlideZoom.vision_description && (
              <div className={`p-4 border-t text-xs leading-relaxed ${isLight ? "bg-slate-50 text-slate-700 border-slate-200" : "bg-slate-950/90 text-slate-300 border-white/10"}`}>
                <span className="font-bold text-indigo-400 block mb-1">Visual Context:</span>
                {selectedSlideZoom.vision_description}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
