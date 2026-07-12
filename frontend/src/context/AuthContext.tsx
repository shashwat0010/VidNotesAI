"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { api } from "@/lib/api";

interface User {
  id: number;
  email: string;
  oauth_provider: string;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    async function loadUser() {
      const token = localStorage.getItem("vidnotes_token");
      if (token) {
        try {
          const userData = await api.get<User>("/auth/me");
          setUser(userData);
        } catch (err) {
          console.error("Token verification failed:", err);
          localStorage.removeItem("vidnotes_token");
          setUser(null);
        }
      }
      setLoading(false);
    }
    loadUser();
  }, []);

  useEffect(() => {
    // Basic route protection
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
      const formData = new FormData();
      formData.append("username", email);
      formData.append("password", password);
      
      const response = await api.postForm<{ access_token: string; user: User }>("/auth/login", formData);
      localStorage.setItem("vidnotes_token", response.access_token);
      setUser(response.user);
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
      await api.post("/auth/register", { email, password });
      // Log in immediately on success
      await login(email, password);
    } catch (err) {
      setLoading(false);
      throw err;
    }
  };

  const logout = () => {
    localStorage.removeItem("vidnotes_token");
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
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
