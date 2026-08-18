"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { supabase, isSupabaseConfigured } from "@/lib/supabase";

export interface User {
  id: number;
  email: string;
  oauth_provider: string;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isSupabase: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  loginWithOAuth: (provider: "google" | "github") => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();
  const isSupabase = isSupabaseConfigured();

  // Helper to sync Supabase session with backend PostgreSQL DB
  const syncSupabaseSession = async (accessToken: string, email: string, uid?: string) => {
    localStorage.setItem("vidnotes_token", accessToken);
    try {
      const response = await api.post<{ access_token: string; user: User }>("/auth/supabase-sync", {
        access_token: accessToken,
        email: email,
        id: uid || ""
      });
      setUser(response.user);
      return response.user;
    } catch (err) {
      console.warn("Backend sync notice:", err);
      // Fallback: try fetching /auth/me with Bearer token
      try {
        const userData = await api.get<User>("/auth/me");
        setUser(userData);
        return userData;
      } catch (meErr) {
        console.error("Auth me fallback failed:", meErr);
        // Minimal local user object if backend is waking up
        const fallbackUser: User = {
          id: 1,
          email: email,
          oauth_provider: "supabase",
          created_at: new Date().toISOString()
        };
        setUser(fallbackUser);
        return fallbackUser;
      }
    }
  };

  useEffect(() => {
    let mounted = true;

    async function initAuth() {
      // 1. If Supabase is configured, check active Supabase session
      if (isSupabase && supabase) {
        try {
          const { data: { session }, error } = await supabase.auth.getSession();
          if (session && session.user?.email && mounted) {
            await syncSupabaseSession(session.access_token, session.user.email, session.user.id);
          }
        } catch (supaErr) {
          console.error("Error reading Supabase session:", supaErr);
        }

        // Listen for Supabase auth state changes (OAuth redirects, token refreshes, logouts)
        const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
          if (!mounted) return;
          if (session && session.user?.email) {
            await syncSupabaseSession(session.access_token, session.user.email, session.user.id);
          } else if (event === "SIGNED_OUT") {
            localStorage.removeItem("vidnotes_token");
            setUser(null);
          }
        });

        if (mounted) setLoading(false);
        return () => {
          mounted = false;
          subscription.unsubscribe();
        };
      }

      // 2. Direct FastAPI Auth Fallback (if Supabase not yet configured)
      const token = localStorage.getItem("vidnotes_token");
      if (token && mounted) {
        try {
          const userData = await api.get<User>("/auth/me");
          if (mounted) setUser(userData);
        } catch (err) {
          console.error("Token verification failed:", err);
          localStorage.removeItem("vidnotes_token");
          if (mounted) setUser(null);
        }
      }
      if (mounted) setLoading(false);
    }

    initAuth();

    return () => {
      mounted = false;
    };
  }, [isSupabase]);

  useEffect(() => {
    // Route protection
    if (!loading) {
      const token = localStorage.getItem("vidnotes_token");
      const isAuthPage = pathname === "/login" || pathname === "/signup" || pathname === "/";
      if (!token && !isAuthPage) {
        router.push("/login");
      } else if (token && (pathname === "/login" || pathname === "/signup")) {
        router.push("/dashboard");
      }
    }
  }, [user, loading, pathname, router]);

  const login = async (email: string, password: string) => {
    setLoading(true);
    try {
      if (isSupabase && supabase) {
        // Sign in with Supabase Auth
        const { data, error } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password: password.trim(),
        });
        if (error) throw error;
        if (data.session && data.user?.email) {
          await syncSupabaseSession(data.session.access_token, data.user.email, data.user.id);
        }
      } else {
        // Direct FastAPI Backend Login
        const formData = new FormData();
        formData.append("username", email.trim());
        formData.append("password", password.trim());
        
        const response = await api.postForm<{ access_token: string; user: User }>("/auth/login", formData);
        localStorage.setItem("vidnotes_token", response.access_token);
        setUser(response.user);
      }
      router.push("/dashboard");
    } catch (err) {
      setLoading(false);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const register = async (email: string, password: string) => {
    setLoading(true);
    try {
      if (isSupabase && supabase) {
        // Register with Supabase Auth
        const { data, error } = await supabase.auth.signUp({
          email: email.trim(),
          password: password.trim(),
        });
        if (error) throw error;
        
        // If session created immediately (auto-confirm enabled)
        if (data.session && data.user?.email) {
          await syncSupabaseSession(data.session.access_token, data.user.email, data.user.id);
          router.push("/dashboard");
        } else {
          // If Supabase requires email confirmation, try signing in or prompt
          await login(email, password);
        }
      } else {
        // Direct FastAPI Backend Registration
        await api.post("/auth/register", { email: email.trim(), password: password.trim() });
        await login(email, password);
      }
    } catch (err) {
      setLoading(false);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const loginWithOAuth = async (provider: "google" | "github") => {
    if (!isSupabase || !supabase) {
      throw new Error("Supabase is not configured. Please add your NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY to .env.local.");
    }
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const { error } = await supabase.auth.signInWithOAuth({
      provider: provider,
      options: {
        redirectTo: `${origin}/dashboard`,
      },
    });
    if (error) throw error;
  };

  const logout = async () => {
    try {
      if (isSupabase && supabase) {
        await supabase.auth.signOut();
      }
    } catch (e) {
      console.warn("Supabase signout warning:", e);
    } finally {
      localStorage.removeItem("vidnotes_token");
      setUser(null);
      router.push("/login");
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, isSupabase, login, register, loginWithOAuth, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
