import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowDown, ArrowRight, BookOpen, Check, ChevronDown, CircleHelp,
  Clock3, FileText, FlaskConical, GraduationCap, Home, Info, LibraryBig, LoaderCircle,
  LogOut, Menu, MessageCircle, Moon, Plus, Save, Search, Send, Settings2,
  ShieldCheck, Sparkles, Sun, Upload, UserRound, X,
} from "lucide-react";
import { LOGOUT_WARNING_KEY, RETURN_TO_KEY, safeReturnPath, useAuth } from "./AuthContext.jsx";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const CHAT_REQUEST_TIMEOUT_MS = 120_000;
const links = [
  { id: "dashboard", label: "Overview", icon: Home },
  { id: "chat", label: "Ask CampusAnswer", icon: MessageCircle },
  { id: "documents", label: "Policy library", icon: LibraryBig },
  { id: "evaluation", label: "Prompt evaluation", icon: FlaskConical },
];
const suggestions = [
  "What is the minimum attendance requirement?",
  "When are semester fees due?",
  "What time should hostel residents return?",
];

function Logo({ small = false }) {
  return <div className={`brand ${small ? "brand-small" : ""}`}><span className="brand-mark"><GraduationCap size={21} /></span><span>Campus<span className="brand-accent">Answer</span></span></div>;
}

function PublicShell({ children, isAuthenticated = false }) {
  const getStartedTo = isAuthenticated ? "/dashboard" : "/login";
  return <div className="public-site">
    <header className="public-nav">
      <Link to="/" className="public-brand"><Logo /></Link>
      <nav aria-label="Public navigation">
        <Link to="/">Home</Link>
        <a href="/#features">Features</a>
        <Link to="/about">About</Link>
      </nav>
      <div className="public-nav-actions">
        {isAuthenticated ? <Link className="public-signin" to="/dashboard">Dashboard</Link> : <Link className="public-signin" to="/login">Sign in</Link>}
        <Link className="button-primary public-get-started" to={getStartedTo}>Get started <ArrowRight size={15} /></Link>
      </div>
    </header>
    {children}
    <footer className="public-footer">
      <Link to="/" className="public-brand"><Logo small /></Link>
      <span>Document-grounded answers for campus questions.</span>
    </footer>
  </div>;
}

function AuthLoading() {
  return <main className="auth-screen"><div className="auth-loading"><LoaderCircle size={22} className="spin" /><span>Verifying your sign-in…</span></div></main>;
}

function App() {
  const { user, profile, loading, configured, authError } = useAuth();
  return <Routes>
    <Route path="/" element={<PublicHome isAuthenticated={Boolean(user && profile)} />} />
    <Route path="/about" element={<PublicAbout isAuthenticated={Boolean(user && profile)} />} />
    <Route path="/login" element={<AuthRoute mode="login" />} />
    <Route path="/register" element={<AuthRoute mode="register" />} />
    <Route element={<RequireAuthentication />}>
      <Route path="/dashboard" element={<Workspace page="dashboard" />} />
      <Route path="/chat" element={<Workspace page="chat" />} />
      <Route path="/documents" element={<Workspace page="documents" />} />
      <Route path="/evaluation" element={<Workspace page="evaluation" />} />
      <Route path="/profile" element={<Workspace page="profile" />} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>;
}

function PublicHome({ isAuthenticated }) {
  const navigate = useNavigate();
  const [logoutWarning, setLogoutWarning] = useState(() => sessionStorage.getItem(LOGOUT_WARNING_KEY) || "");
  useEffect(() => {
    const readLogoutWarning = () => {
      const warning = sessionStorage.getItem(LOGOUT_WARNING_KEY);
      if (!warning) return;
      setLogoutWarning(warning);
      sessionStorage.removeItem(LOGOUT_WARNING_KEY);
    };
    readLogoutWarning();
    window.addEventListener("campusanswer:logout-warning", readLogoutWarning);
    return () => window.removeEventListener("campusanswer:logout-warning", readLogoutWarning);
  }, [isAuthenticated]);
  const openProtectedPage = (page) => {
    if (page === "about") {
      navigate("/about");
      return;
    }
    const path = `/${page}`;
    navigate(isAuthenticated ? path : "/login", { state: { from: { pathname: path } } });
  };
  return <PublicShell isAuthenticated={isAuthenticated}>
    {logoutWarning && <div className="auth-error logout-warning" role="alert"><Info size={15} />{logoutWarning}</div>}
    <Landing navigate={openProtectedPage} />
  </PublicShell>;
}

function PublicAbout({ isAuthenticated }) {
  return <PublicShell isAuthenticated={isAuthenticated}><About /></PublicShell>;
}

function AuthRoute({ mode }) {
  const { user, profile, loading, authError, configured, signIn, signOut, refreshProfile } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [signInError, setSignInError] = useState("");
  const [signInPending, setSignInPending] = useState(false);
  const signInPendingRef = useRef(false);
  const destination = safeReturnPath(
    location.state?.from?.pathname || sessionStorage.getItem(RETURN_TO_KEY),
  );

  useEffect(() => {
    if (user && profile && !loading) {
      sessionStorage.removeItem(RETURN_TO_KEY);
      navigate(destination, { replace: true });
    }
  }, [user, profile, loading, destination, navigate]);

  const startGoogleFlow = async () => {
    if (signInPendingRef.current) return;
    signInPendingRef.current = true;
    setSignInPending(true);
    setSignInError("");
    try {
      await signIn(destination);
    } catch (error) {
      const messages = {
        "auth/cancelled-popup-request": "A previous Google sign-in attempt was cancelled. Close any open Google sign-in windows and try again.",
        "auth/popup-blocked": "Your browser blocked the Google sign-in window. Allow pop-ups for this site and try again.",
        "auth/unauthorized-domain": "This app’s domain is not authorized in Firebase Authentication settings.",
      };
      setSignInError(messages[error.code] || error.message || "Google sign-in failed.");
    } finally {
      signInPendingRef.current = false;
      setSignInPending(false);
    }
  };

  const leaveAuthPage = async () => {
    try {
      await signOut();
      sessionStorage.removeItem(RETURN_TO_KEY);
      navigate("/", { replace: true });
    } catch (error) {
      setSignInError(error.message || "Could not sign out.");
    }
  };

  if (loading) return <AuthLoading />;
  const error = signInError || authError;
  return <main className="auth-screen"><section className="auth-card">
    <Link to="/" className="public-brand"><Logo /></Link>
    <span className="auth-eyebrow">SECURE CAMPUS ACCESS</span>
    <h1>{mode === "register" ? "Create your account" : "Sign in to CampusAnswer"}</h1>
    <p>{mode === "register"
      ? "Create your CampusAnswer account securely with your Google account."
      : "Use your Google account to ask policy questions and access your documents."}</p>
    {error && <div className="auth-error"><Info size={15} />{error}</div>}
    {configured && !user && <button className="button-primary google-signin" onClick={startGoogleFlow} disabled={signInPending}>
      <span className="google-mark">G</span>{signInPending ? "Opening Google…" : mode === "register" ? "Create account with Google" : "Continue with Google"}
    </button>}
    {!configured && <div className="firebase-setup-notice"><ShieldCheck size={17} /><span><b>Firebase setup is required</b><small>Add the Firebase web app settings to the project’s local <code>.env</code>, then restart the frontend.</small></span></div>}
    {user && authError && <>
      <button className="button-outline auth-signout" onClick={refreshProfile}><LoaderCircle size={15} />Retry account verification</button>
      <button className="button-outline auth-signout" onClick={leaveAuthPage}><LogOut size={15} />Sign out and return home</button>
    </>}
    <div className="auth-footnote"><ShieldCheck size={14} /> The API verifies your Google token before granting access.</div>
    <span className="auth-project-note">{mode === "register" ? "Already registered?" : "New to CampusAnswer?"}{" "}
      <Link to={mode === "register" ? "/login" : "/register"}>{mode === "register" ? "Sign in" : "Create an account"}</Link>
    </span>
    <span className="auth-project-note">SCSE4041 · GroundTruth · Fictional demo policies</span>
  </section></main>;
}

function RequireAuthentication() {
  const { user, profile, loading, configured, authError } = useAuth();
  const location = useLocation();
  if (loading) return <AuthLoading />;
  if (!configured) return <Navigate to="/login" replace state={{ from: location }} />;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (authError || !profile) {
    return <AuthRoute mode="login" />;
  }
  return <Outlet />;
}

function Workspace({ page }) {
  const { user, profile, signOut, authorizedFetch } = useAuth();
  const routerNavigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef(null);
  const [documents, setDocuments] = useState([]);
  const [docError, setDocError] = useState("");
  const chatStorageKey = `campusanswer-chat:${profile?.uid || user?.uid || "student"}`;
  const [history, setHistory] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(chatStorageKey) || "[]"); } catch { return []; }
  });
  const [evaluation, setEvaluation] = useState(null);
  const [evaluationError, setEvaluationError] = useState("");

  useEffect(() => {
    let active = true;
    authorizedFetch(`${API}/api/documents`).then(async (response) => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load policy documents.");
      if (active) setDocuments(data);
    }).catch((error) => { if (active) setDocError(error.message); });
    return () => { active = false; };
  }, [authorizedFetch]);

  useEffect(() => {
    fetch("/demo-evaluation-results.json").then((res) => {
      if (!res.ok) throw new Error("Evaluation results are not available yet.");
      return res.json();
    }).then(setEvaluation).catch((error) => setEvaluationError(error.message));
  }, []);

  useEffect(() => sessionStorage.setItem(chatStorageKey, JSON.stringify(history)), [chatStorageKey, history]);

  useEffect(() => {
    const closeOnOutsideClick = (event) => {
      if (!profileMenuRef.current?.contains(event.target)) setProfileMenuOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setProfileMenuOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  const navigate = (next) => {
    const routes = { home: "/dashboard", dashboard: "/dashboard", chat: "/chat", library: "/documents", documents: "/documents", evaluation: "/evaluation", profile: "/profile", about: "/about" };
    routerNavigate(routes[next] || "/dashboard");
    setMenuOpen(false);
    setProfileMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const handleSignOut = () => {
    routerNavigate("/", { replace: true });
    signOut().catch((error) => {
      sessionStorage.setItem(LOGOUT_WARNING_KEY, `Could not complete sign-out: ${error.message}`);
      window.dispatchEvent(new Event("campusanswer:logout-warning"));
    });
  };
  const refreshDocuments = async () => {
    const response = await authorizedFetch(`${API}/api/documents`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not refresh policy documents.");
    setDocuments(data);
  };
  const common = { navigate, documents, docError, history, setHistory, evaluation, evaluationError, authorizedFetch, isAdmin: profile?.is_admin };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}>
        <div className="sidebar-top"><Logo small /><button className="icon-btn mobile-close" onClick={() => setMenuOpen(false)} aria-label="Close menu"><X size={19} /></button></div>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav">{links.map(({ id, label, icon: Icon }) => (
          <button key={id} className={`nav-link ${page === id ? "active" : ""}`} onClick={() => navigate(id)}><Icon size={18} /><span>{label}</span>{id === "chat" && history.length > 0 && <span className="nav-count">{history.length}</span>}</button>
        ))}</nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note"><div className="note-icon"><ShieldCheck size={17} /></div><strong>Grounded by design</strong><p>Answers cite the supplied policy text. Missing evidence is never guessed.</p></div>
          <div className="sidebar-account" ref={profileMenuRef}>
            <button className="sidebar-user" type="button" aria-haspopup="menu" aria-expanded={profileMenuOpen} onClick={() => setProfileMenuOpen((open) => !open)}>
              <span className="sidebar-avatar"><span>{(profile?.name || user?.displayName || profile?.email || "CA").trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase()}</span>{(user?.photoURL || profile?.photo_url) && <img src={user?.photoURL || profile?.photo_url} alt="" onError={(event) => { event.currentTarget.hidden = true; }} />}</span>
              <span className="sidebar-user-copy"><strong>{profile?.name || user?.displayName || profile?.email || "Google account"}</strong><small>{profile?.email || "Signed in with Google"}</small></span>
              <ChevronDown size={16} className="muted-icon" />
            </button>
            {profileMenuOpen && <div className="account-menu" role="menu" aria-label="Account menu">
              <button type="button" role="menuitem" onClick={() => navigate("profile")}><UserRound size={16} />My Profile</button>
              <button type="button" role="menuitem" onClick={() => { setProfileMenuOpen(false); routerNavigate("/profile#settings"); }}><Settings2 size={16} />Account Settings</button>
              <div className="account-menu-divider" />
              <button type="button" role="menuitem" className="account-menu-signout" onClick={handleSignOut}><LogOut size={16} />Sign Out</button>
            </div>}
          </div>
        </div>
      </aside>
      {menuOpen && <button className="mobile-backdrop" onClick={() => setMenuOpen(false)} aria-label="Close navigation" />}
      <main className="main-area">
        <header className="topbar"><button className="icon-btn mobile-menu" onClick={() => setMenuOpen(true)} aria-label="Open menu"><Menu size={21} /></button><div className="breadcrumb"><span>CampusAnswer</span><ArrowRight size={14} /><strong>{links.find((item) => item.id === page)?.label || (page === "profile" ? "My Profile" : "")}</strong></div><div className="topbar-right"><button className="help-button" onClick={() => routerNavigate("/about")}><CircleHelp size={17} /><span>Help</span></button><button className="signout-button" onClick={handleSignOut} aria-label="Sign out of Google"><LogOut size={15} /><span>Sign out</span></button></div></header>
        {page === "dashboard" && <Landing {...common} />}
        {page === "chat" && <Chat {...common} />}
        {page === "documents" && <Library {...common} refreshDocuments={refreshDocuments} />}
        {page === "evaluation" && <Evaluation {...common} />}
        {page === "profile" && <StudentProfile user={user} authProfile={profile} authorizedFetch={authorizedFetch} onSignOut={handleSignOut} />}
        <footer className="page-footer"><span>CampusAnswer · Answers grounded in supplied sources.</span></footer>
      </main>
    </div>
  );
}

const studentProfileFields = [
  ["university", "University name", 180],
  ["enrollment_number", "Enrollment number", 80],
  ["course", "Course", 150],
  ["specialization", "Specialization", 180],
  ["academic_year", "Academic year", 40],
  ["semester", "Semester", 40],
  ["batch", "Batch", 40],
];

function StudentProfile({ user, authProfile, authorizedFetch, onSignOut }) {
  const { refreshProfile } = useAuth();
  const location = useLocation();
  const [details, setDetails] = useState(null);
  const [form, setForm] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingTheme, setSavingTheme] = useState(false);
  const [editing, setEditing] = useState(false);
  const [theme, setTheme] = useState(authProfile?.theme || "light");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadProfile = useCallback(async () => {
    setLoadingProfile(true);
    setError("");
    try {
      const response = await authorizedFetch(`${API}/api/profile`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load your profile.");
      const loaded = { ...data, name: data.name || user?.displayName || "" };
      setDetails(loaded);
      setForm(loaded);
      setTheme(loaded.theme || "light");
    } catch (requestError) {
      setError(requestError.message || "Could not load your profile.");
    } finally {
      setLoadingProfile(false);
    }
  }, [authorizedFetch, user?.displayName]);

  useEffect(() => { loadProfile(); }, [loadProfile]);

  useEffect(() => {
    if (location.hash === "#settings" && !loadingProfile) {
      document.getElementById("account-settings")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [location.hash, loadingProfile]);

  const beginEditing = () => {
    setForm({ ...details });
    setEditing(true);
    setMessage("");
    setError("");
  };

  const cancelEditing = () => {
    setForm({ ...details });
    setEditing(false);
    setMessage("");
    setError("");
  };

  const saveProfile = async (event) => {
    event.preventDefault();
    setSavingProfile(true);
    setMessage("");
    setError("");
    try {
      const payload = {
        name: form.name,
        ...Object.fromEntries(studentProfileFields.map(([key]) => [key, form[key] || ""])),
      };
      const response = await authorizedFetch(`${API}/api/profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save your profile.");
      setDetails(data);
      setForm(data);
      setEditing(false);
      setMessage("Your profile changes have been saved.");
      await refreshProfile({ silent: true });
    } catch (requestError) {
      setError(requestError.message || "Could not save your profile.");
    } finally {
      setSavingProfile(false);
    }
  };

  const saveTheme = async () => {
    setSavingTheme(true);
    setMessage("");
    setError("");
    try {
      const response = await authorizedFetch(`${API}/api/profile/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save your theme preference.");
      setDetails(data);
      setTheme(data.theme);
      await refreshProfile({ silent: true });
      setMessage("Your theme preference has been saved.");
    } catch (requestError) {
      setError(requestError.message || "Could not save your theme preference.");
    } finally {
      setSavingTheme(false);
    }
  };

  const displayName = details?.name || user?.displayName || "Not provided";
  const email = user?.email || authProfile?.email || "";
  const photoUrl = user?.photoURL || details?.photo_url || authProfile?.photo_url;
  const initials = (displayName !== "Not provided" ? displayName : email)
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  return <div className="page-content profile-page">
    <div className="page-title-row">
      <div><div className="eyebrow">YOUR ACCOUNT</div><h1>My Profile</h1><p>Manage your student details and account preferences.</p></div>
    </div>
    {(message || error) && <div className={`profile-feedback${error ? " is-error" : ""}`} role={error ? "alert" : "status"}>{error || message}</div>}
    {loadingProfile ? <div className="profile-loading"><LoaderCircle size={20} className="spin" />Loading your profile…</div>
      : error && !details ? <div className="profile-loading profile-load-error"><span>{error}</span><button className="button-outline" onClick={loadProfile}>Try again</button></div>
        : details && form && <>
          <section className="profile-hero-card">
            <div className="profile-avatar-large">
              <span>{initials || <UserRound size={32} />}</span>
              {photoUrl && <img src={photoUrl} alt={`${displayName}'s Google profile`} onError={(event) => { event.currentTarget.hidden = true; }} />}
            </div>
            <div className="profile-hero-copy">
              <span className="profile-account-label"><span /> GOOGLE ACCOUNT</span>
              <h2>{displayName}</h2>
              <p>{email || "Not provided"}</p>
            </div>
            {!editing
              ? <button className="button-primary profile-edit-button" type="button" onClick={beginEditing}><Settings2 size={16} />Edit Profile</button>
              : <span className="profile-editing-label">Editing profile</span>}
          </section>

          <form className={`profile-details-card${editing ? " is-editing" : ""}`} onSubmit={saveProfile}>
            <div className="profile-section-heading"><div><span className="profile-section-icon"><GraduationCap size={17} /></span><div><h2>Student information</h2><p>Details are saved securely to your CampusAnswer account.</p></div></div>{editing && <span className="profile-editing-label">Editing</span>}</div>
            <div className="profile-fields-grid">
              <label className="profile-field"><span>Full name</span>{editing ? <input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} maxLength={120} required autoComplete="name" /> : <strong>{details.name || "Not provided"}</strong>}</label>
              <label className="profile-field"><span>Email address <small>Google account · read only</small></span><input value={email} readOnly aria-readonly="true" placeholder="Not provided" /></label>
              {studentProfileFields.map(([key, label, maxLength]) => <label className="profile-field" key={key}><span>{label}</span>{editing ? <input value={form[key] || ""} onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))} maxLength={maxLength} /> : <strong>{details[key] || "Not provided"}</strong>}</label>)}
            </div>
            {editing && <div className="profile-form-actions"><button type="button" className="button-outline" onClick={cancelEditing} disabled={savingProfile}>Cancel</button><button type="submit" className="button-primary" disabled={savingProfile}>{savingProfile ? <LoaderCircle size={15} className="spin" /> : <Save size={15} />}{savingProfile ? "Saving…" : "Save Changes"}</button></div>}
          </form>

          <section className="profile-settings-card" id="account-settings">
            <div className="profile-section-heading"><div><span className="profile-section-icon"><Settings2 size={17} /></span><div><h2>Account settings</h2><p>Choose how CampusAnswer looks across your account.</p></div></div></div>
            <div className="theme-preference">
              <div><strong>Theme preference</strong><small>Saved to your account and applied across CampusAnswer.</small></div>
              <div className="theme-options" role="radiogroup" aria-label="Theme preference">
                <button type="button" role="radio" aria-checked={theme === "light"} className={theme === "light" ? "selected" : ""} onClick={() => setTheme("light")}><Sun size={17} />Light</button>
                <button type="button" role="radio" aria-checked={theme === "dark"} className={theme === "dark" ? "selected" : ""} onClick={() => setTheme("dark")}><Moon size={17} />Dark</button>
              </div>
              <button type="button" className="button-outline theme-save-button" onClick={saveTheme} disabled={savingTheme || theme === (details.theme || "light")}>{savingTheme ? <LoaderCircle size={15} className="spin" /> : <Save size={15} />}{savingTheme ? "Saving…" : "Save preference"}</button>
            </div>
            <div className="profile-signout-row"><div><strong>Sign out of CampusAnswer</strong><small>Your profile details will remain saved for your next sign-in.</small></div><button type="button" className="button-outline" onClick={onSignOut}><LogOut size={15} />Sign Out</button></div>
          </section>
        </>}
  </div>;
}

function Landing({ navigate, documents }) {
  return <div className="page-content landing-page">
    <section className="hero-panel">
      <div className="hero-copy"><div className="eyebrow"><span className="eyebrow-line" /> A CLEARER WAY TO FIND YOUR WAY</div><h1>Your campus policies,<br /><span>clearly answered.</span></h1><p>Ask a question. Get an answer grounded in the documents that matter—with the exact source to back it up.</p><div className="hero-actions"><button className="button-primary" onClick={() => navigate("chat")}>Ask a question <ArrowRight size={17} /></button><button className="button-quiet" onClick={() => navigate("library")}>Browse policies</button></div><div className="hero-proof"><span className="proof-check"><Check size={13} /></span> No source? No guess.</div></div>
      <div className="hero-art" aria-hidden="true"><div className="art-glow" /><div className="art-ring ring-one" /><div className="art-ring ring-two" /><div className="orbit-dot dot-a" /><div className="orbit-dot dot-b" /><div className="orbit-dot dot-c" /><div className="art-document"><div className="document-top"><span className="doc-stamp"><FileText size={17} /></span><span className="doc-dots">•••</span></div><div className="doc-heading">POLICY EXCERPT</div><div className="doc-title">Attendance & eligibility</div><div className="doc-line line-long" /><div className="doc-line line-short" /><div className="doc-quote"><span>“</span> Students must maintain a minimum of 75% attendance in each course.</div><div className="doc-citation"><span className="citation-check"><Check size={11} /></span><span><b>Source verified</b><small>Fictional sample · Section 4.2</small></span></div></div><div className="art-chip"><Sparkles size={14} /><span>Evidence-backed</span></div></div>
      <div className="hero-bottom"><span>BUILT FOR CAMPUS QUESTIONS</span><div><span>Attendance</span><i /> <span>Exams</span><i /> <span>Fees</span><i /> <span>Hostel</span></div></div>
    </section>
    <p className="policy-note" role="note"><Info size={14} />Sample policies — not official university guidance.</p>
    <section className="trust-strip"><div><span className="strip-icon"><ShieldCheck size={19} /></span><span><strong>Grounded answers</strong><small>Only from supplied documents</small></span></div><div><span className="strip-icon"><BookOpen size={19} /></span><span><strong>Traceable sources</strong><small>Quotes, sections, and documents</small></span></div><div><span className="strip-icon"><Sparkles size={19} /></span><span><strong>Honest uncertainty</strong><small>Clear when evidence is missing</small></span></div></section>
    <section className="section-block" id="features"><div className="section-heading"><div><div className="eyebrow">YOUR CAMPUS, LESS COMPLICATED</div><h2>One place for the answers you need.</h2></div><button className="text-link" onClick={() => navigate("chat")}>Explore the assistant <ArrowRight size={15} /></button></div><div className="feature-grid">{[
      { icon: MessageCircle, title: "Ask in plain language", body: "No digging through long PDFs. Just ask the question the way you'd ask a person.", tint: "teal" },
      { icon: FileText, title: "See where it came from", body: "Every supported answer includes its document, section, and exact supporting quote.", tint: "blue" },
      { icon: ShieldCheck, title: "No made-up policies", body: "If the supplied documents don't say, CampusAnswer says so—and points you to an office.", tint: "violet" },
    ].map(({ icon: Icon, title, body, tint }) => <article className="feature-card" key={title}><span className={`feature-icon ${tint}`}><Icon size={19} /></span><h3>{title}</h3><p>{body}</p><button className="card-link" onClick={() => navigate("chat")}>Learn more <ArrowRight size={14} /></button></article>)}</div></section>
    <section className="how-section" id="how-it-works"><div className="how-intro"><div className="eyebrow">SIMPLE BY DESIGN</div><h2>From question<br />to clarity.</h2><p>A careful workflow that puts the source before the answer.</p><button className="button-outline" onClick={() => navigate("about")}>How it works <ArrowRight size={15} /></button></div><div className="steps">{[
      ["01", "Ask", "Type your question in everyday language."],
      ["02", "Find evidence", "Relevant sections are retrieved from the supplied policy library."],
      ["03", "Verify", "The response is checked against its exact supporting quote."],
      ["04", "Understand", "Get a clear answer, confidence, and source—or an honest gap."],
    ].map(([num, title, text], index) => <div className="step" key={num}><span className={`step-num ${index === 0 ? "step-current" : ""}`}>{num}</span><div><strong>{title}</strong><p>{text}</p></div>{index < 3 && <ArrowDown className="step-down" size={14} />}</div>)}</div></section>
  </div>;
}

function Chat({ history, setHistory, navigate, authorizedFetch }) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [retryRequest, setRetryRequest] = useState(null);
  const [version, setVersion] = useState("v3");
  const [collection, setCollection] = useState("official");
  const scrollRef = useRef(null);
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [history, loading]);
  const submit = async (value = question, retryId = null) => {
    const text = value.trim();
    if (!text || loading) return;
    setQuestion(""); setError(""); setLoading(true);
    if (!retryId) setRetryRequest(null);
    const id = retryId || `${Date.now()}-${Math.random()}`;
    setHistory((items) => retryId
      ? items.map((item) => item.id === retryId ? { ...item, pending: true } : item)
      : [...items, { id, question: text, pending: true }]);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), CHAT_REQUEST_TIMEOUT_MS);
    try {
      const context = history.filter((item) => !item.pending && item.id !== retryId).slice(-6).flatMap((item) => {
        const messages = [{ role: "user", content: item.question }];
        if (item.answer) {
          const answerText = item.answer.segments?.length
            ? item.answer.segments.map((segment) => `${segment.response_label}: ${segment.answer}`).join("\n")
            : item.answer.answer;
          messages.push({
            role: "assistant",
            content: answerText,
            response_type: item.answer.response_type,
            category: item.answer.category,
          });
        }
        return messages;
      });
      const response = await authorizedFetch(`${API}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, prompt_version: version, collection, history: context }),
        signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = typeof data.detail === "string" ? data.detail : data.detail?.message;
        throw new Error(detail || "The assistant could not answer right now.");
      }
      setHistory((items) => items.map((item) => item.id === id ? { ...item, answer: data, pending: false } : item));
      setRetryRequest(null);
    } catch (requestError) {
      setHistory((items) => items.map((item) => item.id === id ? { ...item, pending: false } : item));
      setRetryRequest({ id, question: text });
      setError(requestError.name === "AbortError"
        ? "CampusAnswer did not respond within 120 seconds. The free service may be waking up; please retry."
        : requestError instanceof TypeError
          ? "Could not reach CampusAnswer. Check your connection and try again."
          : requestError.message || "The assistant could not answer right now.");
    } finally {
      clearTimeout(timeoutId);
      setLoading(false);
    }
  };
  return <div className="page-content chat-page">
    <div className="page-title-row"><div><div className="eyebrow">THE POLICY ASSISTANT</div><h1>Ask CampusAnswer</h1><p>Ask general questions or find policy answers grounded in supplied documents.</p></div><button className="button-outline clear-button" onClick={() => { setHistory([]); setError(""); setRetryRequest(null); }} disabled={!history.length}><Plus size={16} /> New conversation</button></div>
    <div className="chat-layout"><section className="chat-panel"><div className="chat-panel-head"><div className="assistant-identity"><span className="assistant-avatar"><Sparkles size={18} /></span><span><strong>CampusAnswer</strong><small><i className="online-dot" /> Ready to help</small></span></div><div className="chat-source-controls"><label className="version-select">Sources <select value={collection} onChange={(event) => setCollection(event.target.value)}><option value="official">Bennett official PDFs</option><option value="demo">Fictional samples &amp; uploads</option></select><ChevronDown size={13} /></label><label className="version-select">Prompt <select value={version} onChange={(event) => setVersion(event.target.value)}><option value="v1">Version 1 · Baseline</option><option value="v2">Version 2 · Improved</option><option value="v3">Version 3 · Final</option></select><ChevronDown size={13} /></label></div></div>
      <div className="chat-messages">{history.length === 0 ? <div className="chat-empty"><span className="empty-art"><MessageCircle size={25} /><Sparkles size={15} /></span><h2>What would you like to know?</h2><p>Ask general questions or look up attendance, exams, fees, and other policies.</p><div className="suggestion-list">{suggestions.map((item) => <button key={item} onClick={() => submit(item)}>{item}<ArrowRight size={14} /></button>)}</div><div className="chat-disclaimer"><ShieldCheck size={14} />{collection === "official" ? " Official Bennett PDFs only; policy answers include citations." : " Fictional samples and local uploads only."}</div></div> : <div className="message-list">{history.map((item) => <div className="conversation-turn" key={item.id}><div className="user-message"><span className="user-avatar">Y</span><span>{item.question}</span></div>{item.pending ? <div className="assistant-message"><span className="assistant-avatar"><Sparkles size={15} /></span><span className="typing-indicator"><i /><i /><i /> Preparing an answer…</span></div> : item.answer ? <AnswerCard answer={item.answer} /> : null}</div>)}
      {error && <div className="inline-error" role="alert"><Info size={16} /><span>{error}</span>{retryRequest && <button className="button-outline retry-button" onClick={() => submit(retryRequest.question, retryRequest.id)} disabled={loading}>Retry</button>}</div>}<div ref={scrollRef} /></div>}</div>
      <form className="composer" onSubmit={(event) => { event.preventDefault(); submit(); }}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } }} placeholder="Ask anything or ask about a university policy…" rows={1} maxLength={2000} /><div className="composer-bottom"><span><ShieldCheck size={13} /> Policy answers grounded in sources</span><button className="send-button" type="submit" disabled={!question.trim() || loading} aria-label="Send question">{loading ? <LoaderCircle size={17} className="spin" /> : <Send size={16} />}</button></div></form><div className="composer-footnote">General AI answers may need verification. Check cited documents and contact the relevant office for official policy guidance.</div>
    </section><aside className="chat-side"><div className="side-card"><div className="side-card-icon"><ShieldCheck size={18} /></div><h3>Trust, with receipts.</h3><p>Policy answers cite their source document, page, and supporting quotation. General responses are labeled separately.</p><div className="side-divider" /><div className="side-status"><span className="status-dot" /><span><b>Grounding check</b><small>Policy quotes are verified against source text</small></span></div></div><div className="side-card side-card-light"><h3>Try asking</h3><div className="side-prompts">{suggestions.map((item) => <button key={item} onClick={() => submit(item)}>{item}<ArrowRight size={14} /></button>)}</div><button className="browse-link" onClick={() => navigate("library")}>Browse policy library <ArrowRight size={14} /></button></div><div className="side-footnote"><Info size={14} /><span>{collection === "official" ? "Official documents may be dated; check the academic year and source PDF." : "Fictional demonstration content. Not official university guidance."}</span></div></aside></div>
  </div>;
}

function AnswerCard({ answer }) {
  const responses = answer.segments?.length ? answer.segments : [answer];
  return <div className="assistant-message"><span className="assistant-avatar"><Sparkles size={15} /></span><div className="answer-stack" style={{ display: "grid", flex: 1, gap: 12, minWidth: 0 }}>{responses.map((response, index) => <AnswerCardBody key={`${response.response_type}-${index}`} answer={response} />)}</div></div>;
}

function AnswerCardBody({ answer }) {
  const responseType = answer.response_type || (answer.collection === "demo" ? "demo_policy" : "verified_policy");
  const responseLabels = {
    general_conversation: "General conversation",
    general_knowledge: "General AI knowledge",
    verified_policy: "Verified university policy",
    policy_unavailable: "Policy information unavailable",
    demo_policy: "Fictional policy demonstration",
    mixed: "Mixed response",
  };
  const responseLabel = answer.response_label || responseLabels[responseType];
  const isGeneral = responseType === "general_conversation" || responseType === "general_knowledge";
  const cls = answer.status === "supported" ? "answer-supported" : "answer-caution";
  const modeLabel = answer.collection === "official"
    ? answer.mode === "gemini" ? "OFFICIAL · GEMINI" : "OFFICIAL · LOCAL"
    : answer.mode === "gemini" ? "GEMINI" : "DEMO LOOKUP";
  return <div className={`answer-card ${cls}`}>
    <div className="answer-topline">
      <span className="answer-status"><span />{responseLabel}</span>
      {!isGeneral && <span className={`mode-tag ${answer.mode}`}>{modeLabel}</span>}
    </div>
    <p className="answer-text">{answer.answer}</p>
    {!isGeneral && answer.citations?.map((citation, index) => <div className="citation-card" key={`${citation.source_document}-${citation.source_section}-${index}`}>
      <div className="citation-header"><FileText size={15} /><strong>{citation.source_document}</strong><span>{citation.page ? `Page ${citation.page}` : `§ ${citation.source_section}`}</span></div>
      {citation.collection === "official" && <div className="citation-source-meta"><span>Academic year / date: {citation.academic_year || "not specified"}</span>{citation.source_url && <a href={citation.source_url} target="_blank" rel="noreferrer">Open official PDF <ArrowRight size={12} /></a>}</div>}
      <blockquote>“{citation.source_quote}”</blockquote>
      <div className={`citation-verified${citation.extraction_method === "ocr" ? " is-ocr" : ""}`}><Check size={12} />{citation.extraction_method === "ocr" ? "OCR text — verify against the original PDF page" : "Extracted text from the cited source"}</div>
    </div>)}
    {!isGeneral && <div className="answer-meta">
      {answer.confidence && <span className={`confidence confidence-${answer.confidence.toLowerCase()}`}><span className="confidence-dot" />{answer.confidence} confidence</span>}
      {answer.category !== "out_of_scope" && <span className="category-chip">{answer.category.replace("_", " ")}</span>}
      {answer.contact && <span className="contact-note">Contact: {answer.contact}</span>}
    </div>}
  </div>;
}

function Library({ documents, docError, refreshDocuments, authorizedFetch, isAdmin }) {
  const [query, setQuery] = useState("");
  const [uploadState, setUploadState] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [expanded, setExpanded] = useState({});
  const fileRef = useRef(null);
  const filtered = useMemo(() => documents.filter((document) => `${document.title} ${document.filename}`.toLowerCase().includes(query.toLowerCase())), [documents, query]);
  const upload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploadState("Uploading…"); setUploadError("");
    try {
      const form = new FormData(); form.append("file", file);
      const response = await authorizedFetch(`${API}/api/documents/upload`, { method: "POST", body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Upload failed.");
      setUploadState("Document added to the local demo library."); await refreshDocuments();
    } catch (error) { setUploadState(""); setUploadError(error.message); }
    finally { event.target.value = ""; }
  };
  return <div className="page-content"><div className="page-title-row"><div><div className="eyebrow">YOUR SOURCES</div><h1>Policy library</h1><p>Browse the text CampusAnswer can—and cannot—use to answer questions.</p></div>{isAdmin ? <button className="button-primary upload-button" onClick={() => fileRef.current?.click()}><Upload size={16} /> Upload a document</button> : <span className="admin-upload-note">Admin account required to upload</span>}<input ref={fileRef} type="file" accept=".txt,.pdf,text/plain,application/pdf" hidden onChange={upload} /></div>
    <p className="policy-note" role="note"><Info size={14} />Sample policies — not official university guidance. Official PDFs show their date and source; local uploads are labeled separately.</p>
    {(uploadState || uploadError || docError) && <div className={`upload-feedback ${uploadError || docError ? "is-error" : ""}`}>{uploadError || docError || uploadState}</div>}
    <div className="library-toolbar"><div className="library-count"><strong>{filtered.length}</strong> documents <span>·</span> {filtered.reduce((sum, document) => sum + document.sections.length, 0)} sections</div><div className="search-field"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search documents…" /></div></div>
    {filtered.length ? <div className="document-grid">{filtered.map((document) => {
      const official = document.source_type === "official";
      const badge = official ? "OFFICIAL SOURCE" : document.fictional ? "FICTIONAL SAMPLE" : "LOCAL UPLOAD";
      const badgeClass = official ? "badge-official" : document.fictional ? "badge-fictional" : "badge-uploaded";
      return <article className="document-card" key={`${document.source_type}-${document.filename}`}>
        <div className="document-card-head"><span className={`document-icon ${official ? "official" : document.fictional ? "fictional" : "uploaded"}`}><FileText size={18} /></span><span className={`document-badge ${badgeClass}`}>{badge}</span></div>
        <h3>{document.title}</h3><p className="file-name">{document.filename}</p>
        {official && <div className="official-document-meta"><span>Academic year / date: {document.academic_year || "not specified"}</span>{document.source_url && <a href={document.source_url} target="_blank" rel="noreferrer">Open official PDF <ArrowRight size={12} /></a>}</div>}
        <div className="document-stats"><span><BookOpen size={14} />{official ? `${document.indexed_chunks} indexed chunks · ${document.pages || "?"} pages` : `${document.sections.length} sections`}</span><span><ShieldCheck size={14} />{document.sections.length ? "Source text available" : official ? "Not searchable" : "No parsed sections"}</span></div>
        {official && document.indexed_chunks === 0 && <p className="official-index-status">{document.extraction_status === "needs_ocr" ? "Scanned pages need OCR review before indexing." : "No searchable text has been indexed for this PDF."}</p>}
        <div className="section-list">{document.sections.map((section) => <div className="section-item" key={`${document.filename}-${section.section}`}><button onClick={() => setExpanded((state) => ({ ...state, [`${document.filename}-${section.section}`]: !state[`${document.filename}-${section.section}`] }))}><span className="section-index">{section.section}</span><span>{section.title}</span><ChevronDown className={expanded[`${document.filename}-${section.section}`] ? "rotated" : ""} size={15} /></button>{expanded[`${document.filename}-${section.section}`] && <p className="section-text">{section.text}</p>}</div>)}</div>
      </article>;
    })}</div> : <div className="empty-state"><Search size={22} /><strong>No matching documents</strong><span>Try a different title or keyword.</span></div>}
    <div className="upload-hint"><Upload size={17} /><span><b>Adding local demo documents</b><small>Upload TXT or text-based PDF (max 5 MB). TXT section headings: “## Section 1.2 | Title”.</small></span></div>
  </div>;
}

function Evaluation({ evaluation, evaluationError }) {
  const [typeFilter, setTypeFilter] = useState("All tests");
  const [statusFilter, setStatusFilter] = useState("All results");
  const [versionFilter, setVersionFilter] = useState("v3");
  if (!evaluation) return <div className="page-content"><div className="page-title-row"><div><div className="eyebrow">PROMPT ENGINEERING</div><h1>Prompt evaluation</h1><p>Results are shown only after test cases have actually run.</p></div></div><div className="empty-state evaluation-empty"><FlaskConical size={24} /><strong>{evaluationError || "Loading executed test results…"}</strong><span>Run <code>python backend/run_evaluation.py</code> to generate genuine evaluation results.</span></div></div>;
  const versionRows = evaluation.results.filter((row) => row.prompt_version === versionFilter);
  const versionPassed = versionRows.filter((row) => row.outcome === "pass").length;
  const versionFailed = versionRows.filter((row) => row.outcome === "fail").length;
  const versionBlocked = versionRows.filter((row) => row.outcome === "blocked").length;
  const evaluable = versionPassed + versionFailed;
  const passPercentage = evaluable ? `${(100 * versionPassed / evaluable).toFixed(1)}%` : "N/A";
  const rows = versionRows.filter((row) => (
    (typeFilter === "All tests" || row.test_type === typeFilter)
    && (statusFilter === "All results" || row.outcome === statusFilter.toLowerCase())
  ));
  const categoryStats = Object.entries(versionRows.reduce((acc, row) => {
    const key = row.actual_output.category || "unavailable";
    acc[key] ||= { total: 0, passed: 0, blocked: 0 };
    acc[key].total++;
    acc[key].passed += row.outcome === "pass" ? 1 : 0;
    acc[key].blocked += row.outcome === "blocked" ? 1 : 0;
    return acc;
  }, {}));
  const isLive = evaluation.evaluation_mode === "live_gemini";
  const evaluationTitle = isLive
    ? "Live Gemini evaluation"
    : evaluation.evaluation_mode === "gemini_unavailable"
      ? "Gemini generation unavailable"
      : "Local routing and retrieval checks";
  const evaluationDescription = isLive
    ? "Gemini was used for cases that require generation; greetings, local conflict checks, and missing-evidence decisions remain deterministic."
    : evaluation.evaluation_mode === "gemini_unavailable"
      ? "Generation cases were recorded as blocked because Gemini could not be reached or is not configured. Blocked runs are excluded from pass percentages; these results do not compare prompt quality."
      : "These local checks validate deterministic routing and evidence behavior. They do not measure live model quality or show that one prompt is better.";
  return <div className="page-content"><div className="page-title-row"><div><div className="eyebrow">PROMPT ENGINEERING</div><h1>Test & learn</h1><p>Executed checks for grounded answers, uncertainty, and safe boundaries.</p></div><span className="executed-badge"><span /> EXECUTED RESULTS</span></div>
    <div className="evaluation-banner"><span className="evaluation-icon"><FlaskConical size={19} /></span><div><strong>{evaluationTitle}</strong><p>{evaluationDescription}</p><p>{evaluation.prompt_comparison_note}</p></div><span className="evaluation-version">{versionFilter.toUpperCase()} · SELECTED PROMPT</span></div>
    <div className="metric-grid"><Metric label="Test attempts" value={versionRows.length} note={`${versionFilter.toUpperCase()} · ${evaluation.test_case_count} inputs`} icon={FlaskConical} /><Metric label="Passed" value={versionPassed} note={`of ${evaluable} evaluable runs`} icon={Check} /><Metric label="Pass rate" value={passPercentage} note="Blocked runs excluded" icon={ShieldCheck} /><Metric label="Blocked" value={versionBlocked} note={evaluation.gemini_configured ? "Gemini service unavailable" : "Gemini key not configured"} icon={CircleHelp} /></div>
    <section className="category-results"><div className="section-heading compact-heading"><div><h2>Results by category</h2><p>Blocked runs are separated from evaluated outcomes.</p></div></div><div className="category-bars">{categoryStats.map(([name, stats]) => <div className="category-row" key={name}><span className="cat-name">{name.replace("_", " ")}</span><div className="bar-track"><span style={{ width: `${stats.total ? stats.passed / stats.total * 100 : 0}%` }} /></div><span className="cat-count">{stats.passed}/{stats.total} · {stats.blocked} blocked</span></div>)}</div></section>
    <section className="test-results"><div className="section-heading compact-heading"><div><h2>Test cases</h2><p>Expected behavior compared with the response actually returned.</p></div><div className="filter-controls"><select aria-label="Prompt version" value={versionFilter} onChange={(event) => setVersionFilter(event.target.value)}><option value="v1">V1 · Baseline</option><option value="v2">V2 · Improved</option><option value="v3">V3 · Final</option></select><select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option>All tests</option><option>Normal</option><option>Edge</option><option>Invalid</option></select><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option>All results</option><option>Pass</option><option>Fail</option><option>Blocked</option></select></div></div><div className="test-table-wrap"><table className="test-table"><thead><tr><th>NO.</th><th>TEST INPUT</th><th>VERSION</th><th>TYPE</th><th>ACTUAL STATUS</th><th>RESULT</th></tr></thead><tbody>{rows.map((row) => <tr key={`${row.prompt_version}-${row.test_number}`}><td className="test-num">#{String(row.test_number).padStart(2, "0")}</td><td><strong className="test-input">{row.input}</strong><small className="test-expect">Expected: {row.expected_output.status} · Actual: {row.actual_output.status}</small><details className="test-details"><summary>Inspect expected and actual output</summary><div className="test-output-pair"><div><b>Expected</b><pre>{JSON.stringify(row.expected_output, null, 2)}</pre></div><div><b>Actual</b><pre>{JSON.stringify(row.actual_output, null, 2)}</pre></div></div></details></td><td>{row.prompt_version.toUpperCase()}</td><td><span className={`type-label type-${row.test_type.toLowerCase()}`}>{row.test_type}</span></td><td><span className={`status-label ${row.actual_output.status === "supported" ? "status-ok" : row.outcome === "blocked" ? "status-blocked" : "status-neutral"}`}>{row.actual_output.status.replace("_", " ")}</span></td><td><span className={`result-label ${row.outcome === "pass" ? "result-pass" : row.outcome === "blocked" ? "result-blocked" : "result-fail"}`}><span />{row.outcome.toUpperCase()}</span></td></tr>)}</tbody></table>{rows.length === 0 && <div className="empty-filter">No tests match these filters.</div>}</div></section>
    <div className="evaluation-foot"><Clock3 size={14} /> Executed {new Date(evaluation.executed_at_utc).toLocaleString()} · JSON and CSV results saved in <code>test-data/</code>; dashboard copy in <code>frontend/public/</code>.</div>
  </div>;
}

function Metric({ label, value, note, icon: Icon }) {
  return <div className="metric-card"><span className="metric-icon"><Icon size={17} /></span><span className="metric-label">{label}</span><strong>{value}</strong><small>{note}</small></div>;
}

function About() {
  const [activeStep, setActiveStep] = useState(0);
  const intelligence = [
    { icon: FileText, title: "Document-grounded answers", body: "Answers are shaped by retrieved policy sections, not outside policy knowledge." },
    { icon: Search, title: "Smart policy search", body: "Finds supplied sections that are relevant to the question being asked." },
    { icon: Check, title: "Citation verification", body: "Checks supporting quotations against the source text before showing them." },
    { icon: ShieldCheck, title: "Hallucination safeguards", body: "Grounding rules and evidence checks help reduce unsupported claims." },
    { icon: CircleHelp, title: "Context-aware questions", body: "Recognizes supported policy topics and surfaces missing or unclear evidence." },
  ];
  const architecture = [
    { icon: MessageCircle, title: "Student question", body: "A question in natural language" },
    { icon: Search, title: "Policy retrieval", body: "Relevant supplied sections" },
    { icon: Sparkles, title: "AI processing", body: "Gemini for generation; local evidence checks for conflicts and missing information" },
    { icon: ShieldCheck, title: "Evidence verification", body: "Citation checked against source text" },
    { icon: Check, title: "Final answer", body: "A grounded response or clear uncertainty" },
  ];
  const features = [
    { icon: MessageCircle, title: "AI Policy Assistant", body: "Ask policy questions in plain language and get responses tied to supplied sources." },
    { icon: LibraryBig, title: "Intelligent Document Library", body: "Search available documents, inspect sections, and distinguish local uploads from samples." },
    { icon: ShieldCheck, title: "Verified Source Citations", body: "Review source documents, sections, and supporting quotations." },
    { icon: FlaskConical, title: "Prompt Evaluation Lab", body: "Run saved test cases and inspect recorded results after execution." },
    { icon: Search, title: "Multi-Category Policy Search", body: "Explore attendance, exam, fee, hostel, scholarship, and campus policy topics." },
    { icon: CircleHelp, title: "Confidence & Uncertainty", body: "See confidence and a clear response when the available evidence is incomplete." },
  ];
  const steps = [
    { icon: MessageCircle, title: "Ask a question", body: "Type a policy question naturally. CampusAnswer checks its topic and scope before looking for evidence." },
    { icon: Search, title: "Find relevant policy", body: "The assistant searches the supplied policy library for sections related to the question." },
    { icon: ShieldCheck, title: "Verify the evidence", body: "Supporting quotations are checked against source text; gaps or conflicts are surfaced rather than hidden." },
    { icon: FileText, title: "Get a clear answer", body: "Read a grounded response with its source—or an honest explanation when the documents do not answer." },
  ];
  const ActiveStepIcon = steps[activeStep].icon;

  return <div className="page-content about-page platform-overview">
    <header className="overview-intro">
      <div className="overview-intro-copy">
        <div className="eyebrow">CAMPUSANSWER PLATFORM</div>
        <h1>Policy intelligence,<br /><span>grounded in evidence.</span></h1>
        <p>A clearer way to find answers in campus policy documents—with sources and uncertainty kept in view.</p>
        <p className="policy-note" role="note"><Info size={14} />Sample policies — not official university guidance.</p>
      </div>
      <div className="overview-visual" aria-hidden="true">
        <div className="overview-visual-glow" />
        <div className="overview-visual-card">
          <div className="overview-visual-label"><span className="overview-pulse" /> EVIDENCE WORKFLOW</div>
          <div className="overview-visual-row"><span className="overview-visual-icon"><FileText size={17} /></span><span><b>Relevant section</b><small>Retrieved from supplied documents</small></span></div>
          <div className="overview-visual-quote"><span />Supporting text stays connected to its source.</div>
          <div className="overview-visual-footer"><ShieldCheck size={15} /> Source checked before citation</div>
        </div>
        <span className="overview-float-icon"><Sparkles size={18} /></span>
      </div>
    </header>

    <section className="overview-section" aria-labelledby="intelligence-heading">
      <div className="overview-section-heading">
        <div><div className="eyebrow">AI INTELLIGENCE ENGINE</div><h2 id="intelligence-heading">Designed to answer with evidence.</h2></div>
        <p>Each response starts with the documents available to CampusAnswer and stays transparent about what they do—and do not—say.</p>
      </div>
      <div className="intelligence-grid">{intelligence.map(({ icon: Icon, title, body }, index) =>
        <article className="intelligence-card" key={title}>
          <span className={`overview-icon overview-icon-${index}`}><Icon size={18} /></span>
          <h3>{title}</h3><p>{body}</p>
        </article>
      )}</div>
    </section>

    <section className="architecture-panel" aria-labelledby="architecture-heading">
      <div className="overview-section-heading architecture-heading">
        <div><div className="eyebrow">PLATFORM ARCHITECTURE</div><h2 id="architecture-heading">A traceable path from question to answer.</h2></div>
        <p>Policy sources remain at the center of the workflow.</p>
      </div>
      <div className="architecture-flow">{architecture.map(({ icon: Icon, title, body }, index) =>
        <div className="architecture-step" key={title}>
          <span className="architecture-icon"><Icon size={18} /></span>
          <span className="architecture-index">0{index + 1}</span>
          <h3>{title}</h3><p>{body}</p>
          {index < architecture.length - 1 && <ArrowRight className="architecture-arrow" size={17} aria-hidden="true" />}
        </div>
      )}</div>
    </section>

    <section className="overview-section" aria-labelledby="features-heading">
      <div className="overview-section-heading">
        <div><div className="eyebrow">ADVANCED PLATFORM FEATURES</div><h2 id="features-heading">Everything you need to follow the evidence.</h2></div>
        <p>Tools for asking, inspecting, and evaluating policy answers in one place.</p>
      </div>
      <div className="platform-feature-grid">{features.map(({ icon: Icon, title, body }) =>
        <article className="platform-feature-card" key={title}>
          <span className="platform-feature-icon"><Icon size={19} /></span>
          <div><h3>{title}</h3><p>{body}</p></div>
          <ArrowRight className="feature-arrow" size={15} aria-hidden="true" />
        </article>
      )}</div>
    </section>

    <section className="overview-section how-overview" aria-labelledby="how-overview-heading">
      <div className="overview-section-heading">
        <div><div className="eyebrow">HOW CAMPUSANSWER WORKS</div><h2 id="how-overview-heading">Four steps. One source-led workflow.</h2></div>
        <p>Select a step to see how a question becomes a cited answer—or an honest information gap.</p>
      </div>
      <div className="interactive-steps">
        <div className="interactive-step-list" role="group" aria-label="How CampusAnswer works">
          {steps.map(({ icon: Icon, title }, index) =>
            <button type="button" className={`interactive-step${activeStep === index ? " is-active" : ""}`} key={title} onClick={() => setActiveStep(index)} aria-pressed={activeStep === index}>
              <span className="interactive-step-icon"><Icon size={18} /></span>
              <span className="interactive-step-copy"><small>STEP 0{index + 1}</small><strong>{title}</strong></span>
              <ArrowRight size={15} className="interactive-step-arrow" />
            </button>
          )}
        </div>
        <div className="interactive-step-detail" key={steps[activeStep].title} aria-live="polite">
          <span className="step-detail-icon"><ActiveStepIcon size={22} /></span>
          <div><div className="eyebrow">STEP 0{activeStep + 1} / 04</div><h3>{steps[activeStep].title}</h3><p>{steps[activeStep].body}</p></div>
          <span className="step-detail-mark"><Check size={17} /></span>
        </div>
      </div>
    </section>
  </div>;
}

export default App;
