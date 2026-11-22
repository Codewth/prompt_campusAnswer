import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { GoogleAuthProvider, onAuthStateChanged, signInWithPopup, signOut } from "firebase/auth";
import { firebaseAuth, firebaseConfigured } from "./firebase.js";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const RETURN_TO_KEY = "campusanswer:auth-return-to";
const LOGOUT_WARNING_KEY = "campusanswer:logout-warning";
const AuthContext = createContext(null);

function safeReturnPath(value) {
  const allowedPaths = new Set(["/dashboard", "/chat", "/documents", "/evaluation", "/profile"]);
  return allowedPaths.has(value) ? value : "/dashboard";
}

async function fetchProfile(user) {
  const token = await user.getIdToken();
  const response = await fetch(`${API}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("The authentication API returned an unreadable response.");
  }
  if (!response.ok) {
    const error = new Error(data.detail || "The API could not verify your Google sign-in.");
    error.status = response.status;
    throw error;
  }
  return data;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const generation = useRef(0);

  useEffect(() => {
    document.documentElement.dataset.theme = profile?.theme === "dark" ? "dark" : "light";
  }, [profile?.theme]);

  useEffect(() => {
    if (!firebaseAuth) {
      setLoading(false);
      return undefined;
    }

    let active = true;
    const unsubscribe = onAuthStateChanged(firebaseAuth, async (nextUser) => {
      const currentGeneration = ++generation.current;
      setUser(nextUser);
      setProfile(null);
      setAuthError("");
      setLoading(Boolean(nextUser));

      if (!nextUser) {
        setLoading(false);
        return;
      }

      try {
        const nextProfile = await fetchProfile(nextUser);
        if (active && generation.current === currentGeneration) setProfile(nextProfile);
      } catch (error) {
        if (active && generation.current === currentGeneration) setAuthError(error.message);
      } finally {
        if (active && generation.current === currentGeneration) setLoading(false);
      }
    }, (error) => {
      if (!active) return;
      setUser(null);
      setProfile(null);
      setAuthError(error.message || "Firebase could not restore the sign-in session.");
      setLoading(false);
    });

    return () => {
      active = false;
      generation.current += 1;
      unsubscribe();
    };
  }, []);

  const signIn = useCallback(async (returnTo = "/dashboard") => {
    if (!firebaseAuth) throw new Error("Firebase is not configured for this application.");
    const destination = safeReturnPath(returnTo);
    sessionStorage.setItem(RETURN_TO_KEY, destination);
    setAuthError("");
    await signInWithPopup(firebaseAuth, new GoogleAuthProvider());
  }, []);

  const signOutUser = useCallback(async () => {
    let logoutWarning = "";
    const currentUser = firebaseAuth?.currentUser;
    if (currentUser) {
      try {
        const token = await currentUser.getIdToken();
        const response = await fetch(`${API}/api/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          let detail = "The API could not revoke this sign-in session.";
          try {
            const data = await response.json();
            detail = data.detail || detail;
          } catch {
            // Keep the explicit fallback message for unreadable error responses.
          }
          throw new Error(detail);
        }
      } catch (error) {
        logoutWarning = `You were signed out on this device, but server session revocation failed: ${error.message}`;
      }
    }

    try {
      if (firebaseAuth) await signOut(firebaseAuth);
    } finally {
      sessionStorage.removeItem(RETURN_TO_KEY);
      if (logoutWarning) sessionStorage.setItem(LOGOUT_WARNING_KEY, logoutWarning);
      else sessionStorage.removeItem(LOGOUT_WARNING_KEY);
      setProfile(null);
      setAuthError("");
    }
  }, []);

  const refreshProfile = useCallback(async ({ silent = false } = {}) => {
    const currentUser = firebaseAuth?.currentUser;
    if (!currentUser) return null;
    const currentGeneration = ++generation.current;
    if (!silent) setLoading(true);
    setAuthError("");
    try {
      const nextProfile = await fetchProfile(currentUser);
      if (generation.current === currentGeneration) setProfile(nextProfile);
      return nextProfile;
    } catch (error) {
      if (generation.current === currentGeneration) setAuthError(error.message);
      return null;
    } finally {
      if (!silent && generation.current === currentGeneration) setLoading(false);
    }
  }, []);

  const authorizedFetch = useCallback(async (input, options = {}) => {
    const currentUser = firebaseAuth?.currentUser;
    if (!currentUser) throw new Error("Sign in with Google to continue.");
    const token = await currentUser.getIdToken();
    const headers = new Headers(options.headers);
    headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(input, { ...options, headers });
    if (response.status === 401) {
      await signOutUser();
      throw new Error("Your sign-in expired or was revoked. Please sign in again.");
    }
    return response;
  }, [signOutUser]);

  const value = useMemo(() => ({
    user,
    profile,
    loading,
    authError,
    configured: firebaseConfigured,
    signIn,
    signOut: signOutUser,
    refreshProfile,
    authorizedFetch,
  }), [user, profile, loading, authError, signIn, signOutUser, refreshProfile, authorizedFetch]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}

export { LOGOUT_WARNING_KEY, RETURN_TO_KEY, safeReturnPath };
