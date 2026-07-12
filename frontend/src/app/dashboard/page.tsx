"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { 
  Folder as FolderIcon, 
  Video as VideoIcon, 
  Plus, 
  Trash2, 
  Link as LinkIcon, 
  Upload, 
  Search, 
  FolderPlus, 
  Zap, 
  LogOut, 
  Clock, 
  Play, 
  Loader2, 
  CheckCircle2, 
  XCircle,
  FileAudio
} from "lucide-react";

interface Folder {
  id: number;
  name: string;
  parent_id: number | null;
}

interface Video {
  id: string;
  title: string;
  url: string | null;
  status: string;
  error_message: string | null;
  duration: number | null;
  size: number | null;
  folder_id: number | null;
  created_at: string;
}

export default function Dashboard() {
  const { user, logout, loading: authLoading } = useAuth();
  const router = useRouter();

  const [folders, setFolders] = useState<Folder[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(null);
  
  // Create state
  const [newFolderName, setNewFolderName] = useState("");
  const [showFolderInput, setShowFolderInput] = useState(false);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [ytLoading, setYtLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  
  // Active Tab for Ingestion
  const [activeIngestTab, setActiveIngestTab] = useState<"youtube" | "file">("youtube");

  // Load Folders & Videos
  useEffect(() => {
    if (user) {
      fetchFolders();
      fetchVideos();
    }
  }, [user]);

  // Polling for processing videos
  useEffect(() => {
    const hasProcessing = videos.some(v => v.status === "processing" || v.status === "pending");
    if (hasProcessing) {
      const interval = setInterval(() => {
        fetchVideos();
      }, 5000); // Poll every 5s
      return () => clearInterval(interval);
    }
  }, [videos]);

  const fetchFolders = async () => {
    try {
      const data = await api.get<Folder[]>("/folders/");
      setFolders(data);
    } catch (err) {
      console.error("Error loading folders:", err);
    }
  };

  const fetchVideos = async () => {
    try {
      const data = await api.get<Video[]>("/videos/");
      setVideos(data);
    } catch (err) {
      console.error("Error loading videos:", err);
    }
  };

  const handleCreateFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;
    try {
      const newFolder = await api.post<Folder>("/folders/", { name: newFolderName });
      setFolders([newFolder, ...folders]);
      setNewFolderName("");
      setShowFolderInput(false);
    } catch (err) {
      console.error("Error creating folder:", err);
    }
  };

  const handleDeleteFolder = async (folderId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this folder? All child files will be un-categorized.")) return;
    try {
      await api.delete(`/folders/${folderId}`);
      setFolders(folders.filter(f => f.id !== folderId));
      if (selectedFolderId === folderId) {
        setSelectedFolderId(null);
      }
    } catch (err) {
      console.error("Error deleting folder:", err);
    }
  };

  const handleDeleteVideo = async (videoId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this video analysis?")) return;
    try {
      await api.delete(`/videos/${videoId}`);
      setVideos(videos.filter(v => v.id !== videoId));
    } catch (err) {
      console.error("Error deleting video:", err);
    }
  };

  const handleYoutubeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!youtubeUrl.trim()) return;
    setYtLoading(true);
    try {
      const formData = new FormData();
      formData.append("url", youtubeUrl);
      if (selectedFolderId) {
        formData.append("folder_id", String(selectedFolderId));
      }
      
      const newVideo = await api.postForm<Video>("/videos/youtube", formData);
      setVideos([newVideo, ...videos]);
      setYoutubeUrl("");
    } catch (err: any) {
      alert(err.message || "Failed to process YouTube URL");
    } finally {
      setYtLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];
    
    setUploadLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (selectedFolderId) {
        formData.append("folder_id", String(selectedFolderId));
      }
      
      const newVideo = await api.postForm<Video>("/videos/upload", formData);
      setVideos([newVideo, ...videos]);
    } catch (err: any) {
      alert(err.message || "Failed to upload video file");
    } finally {
      setUploadLoading(false);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 className="animate-spin h-10 w-10 text-indigo-500" />
      </div>
    );
  }

  // Filtering videos by selected folder and search query
  const filteredVideos = videos.filter(video => {
    const matchesFolder = selectedFolderId === null || video.folder_id === selectedFolderId;
    const matchesSearch = searchQuery.trim() === "" || 
      video.title.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFolder && matchesSearch;
  });

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100 font-sans">
      {/* Header */}
      <header className="glass-panel border-b border-slate-900 px-6 py-4 flex items-center justify-between z-20">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center">
            <Zap className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-bold tracking-tight text-white">VidNotes AI</span>
        </div>
        
        <div className="flex items-center space-x-4">
          <span className="text-sm text-slate-400 font-medium hidden sm:inline">{user?.email}</span>
          <button 
            onClick={logout} 
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/40 hover:bg-slate-900 text-slate-400 hover:text-white transition duration-150 text-xs font-semibold cursor-pointer"
          >
            <LogOut className="h-3.5 w-3.5" /> Sign Out
          </button>
        </div>
      </header>

      {/* Workspace Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar (Folders) */}
        <aside className="w-64 border-r border-slate-900 bg-slate-950/40 p-6 hidden md:flex flex-col gap-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Library Folders</h3>
            <button 
              onClick={() => setShowFolderInput(!showFolderInput)} 
              className="text-slate-400 hover:text-white transition"
              title="New Folder"
            >
              <FolderPlus className="h-4 w-4" />
            </button>
          </div>

          {showFolderInput && (
            <form onSubmit={handleCreateFolder} className="flex gap-2">
              <input
                type="text"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                placeholder="Folder name..."
                className="flex-1 px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 text-slate-200"
                autoFocus
              />
              <button 
                type="submit" 
                className="px-2.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold cursor-pointer"
              >
                Create
              </button>
            </form>
          )}

          <nav className="flex flex-col gap-1.5">
            <button
              onClick={() => setSelectedFolderId(null)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition text-left cursor-pointer ${
                selectedFolderId === null 
                  ? "bg-indigo-600/10 text-indigo-400 border border-indigo-500/10" 
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/40"
              }`}
            >
              <span className="flex items-center gap-2"><FolderIcon className="h-4 w-4" /> All Notes</span>
              <span className="text-[10px] bg-slate-900/60 px-1.5 py-0.5 rounded text-slate-400">{videos.length}</span>
            </button>

            {folders.map(folder => {
              const count = videos.filter(v => v.folder_id === folder.id).length;
              return (
                <button
                  key={folder.id}
                  onClick={() => setSelectedFolderId(folder.id)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition text-left group cursor-pointer ${
                    selectedFolderId === folder.id 
                      ? "bg-indigo-600/10 text-indigo-400 border border-indigo-500/10" 
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/40"
                  }`}
                >
                  <span className="flex items-center gap-2 truncate">
                    <FolderIcon className="h-4 w-4 shrink-0" /> {folder.name}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] bg-slate-900/60 px-1.5 py-0.5 rounded text-slate-400">{count}</span>
                    <button 
                      onClick={(e) => handleDeleteFolder(folder.id, e)} 
                      className="text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition duration-150 cursor-pointer"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </button>
              );
            })}
          </nav>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-5xl mx-auto flex flex-col gap-8">
            
            {/* Ingestion Panel */}
            <div className="glass-panel p-6 rounded-2xl border border-slate-900 flex flex-col gap-5">
              <div className="flex items-center justify-between border-b border-slate-900 pb-3">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Plus className="h-5 w-5 text-indigo-400" /> Convert New Media
                </h2>
                
                <div className="flex bg-slate-900 p-0.5 rounded-lg border border-slate-800">
                  <button
                    onClick={() => setActiveIngestTab("youtube")}
                    className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer ${
                      activeIngestTab === "youtube" 
                        ? "bg-indigo-600 text-white shadow-sm" 
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    <LinkIcon className="h-3 w-3" /> YouTube URL
                  </button>
                  <button
                    onClick={() => setActiveIngestTab("file")}
                    className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer ${
                      activeIngestTab === "file" 
                        ? "bg-indigo-600 text-white shadow-sm" 
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    <Upload className="h-3 w-3" /> Audio/Video File
                  </button>
                </div>
              </div>

              {activeIngestTab === "youtube" ? (
                <form onSubmit={handleYoutubeSubmit} className="flex flex-col sm:flex-row gap-3">
                  <div className="flex-1 relative">
                    <LinkIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                    <input
                      type="url"
                      value={youtubeUrl}
                      onChange={(e) => setYoutubeUrl(e.target.value)}
                      placeholder="https://www.youtube.com/watch?v=..."
                      required
                      className="w-full pl-10 pr-4 py-2.5 bg-slate-950/60 border border-slate-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-slate-200"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={ytLoading}
                    className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                  >
                    {ytLoading ? <Loader2 className="animate-spin h-4 w-4" /> : "Process Link"}
                  </button>
                </form>
              ) : (
                <div className="border-2 border-dashed border-slate-800 rounded-xl p-8 flex flex-col items-center justify-center text-center hover:border-indigo-500/50 transition relative">
                  <input
                    type="file"
                    accept="video/*,audio/*"
                    onChange={handleFileUpload}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    disabled={uploadLoading}
                  />
                  <div className="h-10 w-10 rounded-full bg-slate-900 flex items-center justify-center text-slate-400 mb-3 border border-slate-800">
                    {uploadLoading ? <Loader2 className="animate-spin h-5 w-5 text-indigo-500" /> : <Upload className="h-5 w-5" />}
                  </div>
                  <span className="text-sm font-semibold text-slate-200">
                    {uploadLoading ? "Uploading & Initializing..." : "Select audio or video file"}
                  </span>
                  <span className="text-xs text-slate-500 mt-1">MP4, MP3, WAV formats up to 500MB</span>
                </div>
              )}
            </div>

            {/* List Header & Search */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
              <div>
                <h1 className="text-xl font-bold text-white">Your Study Workspace</h1>
                <p className="text-xs text-slate-500 mt-0.5">
                  {selectedFolderId 
                    ? `Showing notes in ${folders.find(f => f.id === selectedFolderId)?.name}` 
                    : "Showing all processed lectures"}
                </p>
              </div>

              <div className="relative w-full sm:w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search notes title..."
                  className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 text-slate-200"
                />
              </div>
            </div>

            {/* Video Study Cards Grid */}
            {filteredVideos.length === 0 ? (
              <div className="glass-panel p-12 text-center rounded-2xl border border-slate-900">
                <VideoIcon className="h-12 w-12 text-slate-600 mx-auto mb-4" />
                <h3 className="text-sm font-semibold text-slate-300">No notes found</h3>
                <p className="text-xs text-slate-500 mt-1">Convert a new video file or YouTube URL above to begin.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredVideos.map(video => {
                  const isProcessing = video.status === "processing" || video.status === "pending";
                  const isFailed = video.status === "failed";
                  
                  return (
                    <div 
                      key={video.id}
                      onClick={() => {
                        if (!isProcessing && !isFailed) {
                          router.push(`/workspace/${video.id}`);
                        }
                      }}
                      className={`glass-card p-5 rounded-2xl border flex flex-col justify-between h-48 relative overflow-hidden ${
                        isProcessing 
                          ? "border-slate-900/60 opacity-80 cursor-default" 
                          : isFailed 
                          ? "border-red-950/40 opacity-90 cursor-default"
                          : "border-slate-900 cursor-pointer"
                      }`}
                    >
                      {/* Top Bar inside card */}
                      <div className="flex items-start justify-between gap-4">
                        <div className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-indigo-400 shrink-0">
                          {video.url ? <VideoIcon className="h-5 w-5" /> : <FileAudio className="h-5 w-5" />}
                        </div>
                        
                        {/* Status Icon */}
                        {isProcessing ? (
                          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-950/40 text-indigo-400 text-[10px] font-bold glow-loader">
                            <Loader2 className="animate-spin h-3 w-3" /> Processing
                          </div>
                        ) : isFailed ? (
                          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-950/40 text-red-400 text-[10px] font-bold border border-red-500/10">
                            <XCircle className="h-3 w-3" /> Failed
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/40 text-emerald-400 text-[10px] font-bold border border-emerald-500/10">
                            <CheckCircle2 className="h-3 w-3" /> Processed
                          </div>
                        )}
                      </div>

                      {/* Video Title */}
                      <div className="mt-4 flex-1">
                        <h3 className="font-semibold text-sm text-slate-100 line-clamp-2 leading-snug group-hover:text-indigo-400 transition">
                          {video.title}
                        </h3>
                        {isFailed && (
                          <p className="text-[10px] text-red-400 line-clamp-1 mt-1 font-mono">
                            {video.error_message || "Ingestion error"}
                          </p>
                        )}
                      </div>

                      {/* Card Footer Details */}
                      <div className="mt-4 pt-3 border-t border-slate-900/60 flex items-center justify-between text-[11px] text-slate-500">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" /> 
                          {video.duration ? `${Math.round(video.duration / 60)} min` : "unknown"}
                        </span>
                        
                        <button
                          onClick={(e) => handleDeleteVideo(video.id, e)}
                          className="p-1 rounded hover:bg-slate-900 hover:text-red-400 transition cursor-pointer"
                          title="Delete Workspace"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

          </div>
        </main>
      </div>
    </div>
  );
}
