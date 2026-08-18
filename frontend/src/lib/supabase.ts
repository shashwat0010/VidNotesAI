import { createClient, SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
// Support both Publishable Key (newer Supabase naming) and Anon Key (standard public client key)
const supabasePublishableKey = 
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  process.env.NEXT_PUBLIC_SUPABASE_PUBLIC_KEY ||
  process.env.NEXT_PUBLIC_SUPABASE_KEY ||
  "";

export const isSupabaseConfigured = (): boolean => {
  return Boolean(
    supabaseUrl &&
    supabasePublishableKey &&
    supabaseUrl.startsWith("https://") &&
    !supabaseUrl.includes("your-project-id") &&
    !supabasePublishableKey.includes("your-anon-key") &&
    !supabasePublishableKey.includes("your-publishable-key")
  );
};

export const supabase: SupabaseClient | null = isSupabaseConfigured()
  ? createClient(supabaseUrl, supabasePublishableKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null;
