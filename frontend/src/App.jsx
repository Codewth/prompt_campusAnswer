import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDown, ArrowLeft, ArrowRight, BookOpen, Check, ChevronDown, CircleHelp,
  Clock3, FileText, FlaskConical, GraduationCap, Home, Info, LibraryBig, LoaderCircle,
  Menu, MessageCircle, Plus, Search, Send, ShieldCheck, Sparkles, Upload, X,
} from "lucide-react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const links = [
  { id: "home", label: "Overview", icon: Home },
  { id: "chat", label: "Ask CampusAnswer", icon: MessageCircle },
  { id: "library", label: "Policy library", icon: LibraryBig },
  { id: "evaluation", label: "Prompt evaluation", icon: FlaskConical },
  { id: "about", label: "About the project", icon: Info },
];
const suggestions = [
  "What is the minimum attendance requirement?",
  "When are semester fees due?",
  "What time should hostel residents return?",
];

function Logo({ small = false }) {
  return <div className={`brand ${small ? "brand-small" : ""}`}><span className="brand-mark"><GraduationCap size={21} /></span><span>Campus<span className="brand-accent">Answer</span></span></div>;
}

function App() {
  const [page, setPage] = useState("home");
  const [menuOpen, setMenuOpen] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [docError, setDocError] = useState("");
  const [history, setHistory] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem("campusanswer-chat") || "[]"); } catch { return []; }
  });
  const [evaluation, setEvaluation] = useState(null);
  const [evaluationError, setEvaluationError] = useState("");

  useEffect(() => {
    fetch(`${API}/api/documents`).then((res) => {
      if (!res.ok) throw new Error("Could not load policy documents.");
      return res.json();
    }).then(setDocuments).catch((error) => setDocError(error.message));
    fetch("/demo-evaluation-results.json").then((res) => {
      if (!res.ok) throw new Error("Evaluation results are not available yet.");
      return res.json();
    }).then(setEvaluation).catch((error) => setEvaluationError(error.message));
  }, []);

  useEffect(() => sessionStorage.setItem("campusanswer-chat", JSON.stringify(history)), [history]);

  const navigate = (next) => {
    setPage(next);
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const common = { navigate, documents, docError, history, setHistory, evaluation, evaluationError };

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
          <div className="sidebar-user"><span className="avatar">GU</span><span><strong>GroundTruth</strong><small>Student project · SCSE4041</small></span><ChevronDown size={16} className="muted-icon" /></div>
        </div>
      </aside>
      {menuOpen && <button className="mobile-backdrop" onClick={() => setMenuOpen(false)} aria-label="Close navigation" />}
      <main className="main-area">
        <header className="topbar"><button className="icon-btn mobile-menu" onClick={() => setMenuOpen(true)} aria-label="Open menu"><Menu size={21} /></button><div className="breadcrumb"><span>CampusAnswer</span><ArrowRight size={14} /><strong>{links.find((item) => item.id === page)?.label}</strong></div><div className="topbar-right"><span className="demo-pill"><span /> DEMO ENVIRONMENT</span><button className="help-button" onClick={() => navigate("about")}><CircleHelp size={17} /><span>Help</span></button></div></header>
        {page === "home" && <Landing {...common} />}
        {page === "chat" && <Chat {...common} />}
        {page === "library" && <Library {...common} refreshDocuments={() => fetch(`${API}/api/documents`).then((r) => r.json()).then(setDocuments).catch((error) => setDocError(error.message))} />}
        {page === "evaluation" && <Evaluation {...common} />}
        {page === "about" && <About />}
        <footer className="page-footer"><span>CampusAnswer · A SCSE4041 Prompt Engineering project</span><span>Fictional demo policies · Not official university guidance</span></footer>
      </main>
    </div>
  );
}

function Landing({ navigate, documents }) {
  return <div className="page-content landing-page">
    <section className="hero-panel">
      <div className="hero-copy"><div className="eyebrow"><span className="eyebrow-line" /> A CLEARER WAY TO FIND YOUR WAY</div><h1>Your campus policies,<br /><span>clearly answered.</span></h1><p>Ask a question. Get an answer grounded in the documents that matter—with the exact source to back it up.</p><div className="hero-actions"><button className="button-primary" onClick={() => navigate("chat")}>Ask a question <ArrowRight size={17} /></button><button className="button-quiet" onClick={() => navigate("library")}>Browse policies</button></div><div className="hero-proof"><span className="proof-check"><Check size={13} /></span> No source? No guess.</div></div>
      <div className="hero-art" aria-hidden="true"><div className="art-glow" /><div className="art-ring ring-one" /><div className="art-ring ring-two" /><div className="orbit-dot dot-a" /><div className="orbit-dot dot-b" /><div className="orbit-dot dot-c" /><div className="art-document"><div className="document-top"><span className="doc-stamp"><FileText size={17} /></span><span className="doc-dots">•••</span></div><div className="doc-heading">POLICY EXCERPT</div><div className="doc-title">Attendance & eligibility</div><div className="doc-line line-long" /><div className="doc-line line-short" /><div className="doc-quote"><span>“</span> Students must maintain a minimum of 75% attendance in each course.</div><div className="doc-citation"><span className="citation-check"><Check size={11} /></span><span><b>Source verified</b><small>Sample Policy · Section 4.2</small></span></div></div><div className="art-chip"><Sparkles size={14} /><span>Evidence-backed</span></div></div>
      <div className="hero-bottom"><span>BUILT FOR CAMPUS QUESTIONS</span><div><span>Attendance</span><i /> <span>Exams</span><i /> <span>Fees</span><i /> <span>Hostel</span></div></div>
    </section>
    <section className="trust-strip"><div><span className="strip-icon"><ShieldCheck size={19} /></span><span><strong>Grounded answers</strong><small>Only from supplied documents</small></span></div><div><span className="strip-icon"><BookOpen size={19} /></span><span><strong>Traceable sources</strong><small>Quotes, sections, and documents</small></span></div><div><span className="strip-icon"><Sparkles size={19} /></span><span><strong>Honest uncertainty</strong><small>Clear when evidence is missing</small></span></div></section>
    <section className="section-block"><div className="section-heading"><div><div className="eyebrow">YOUR CAMPUS, LESS COMPLICATED</div><h2>One place for the answers you need.</h2></div><button className="text-link" onClick={() => navigate("chat")}>Explore the assistant <ArrowRight size={15} /></button></div><div className="feature-grid">{[
      { icon: MessageCircle, title: "Ask in plain language", body: "No digging through long PDFs. Just ask the question the way you'd ask a person.", tint: "teal" },
      { icon: FileText, title: "See where it came from", body: "Every supported answer includes its document, section, and exact supporting quote.", tint: "blue" },
      { icon: ShieldCheck, title: "No made-up policies", body: "If the supplied documents don't say, CampusAnswer says so—and points you to an office.", tint: "violet" },
    ].map(({ icon: Icon, title, body, tint }) => <article className="feature-card" key={title}><span className={`feature-icon ${tint}`}><Icon size={19} /></span><h3>{title}</h3><p>{body}</p><button className="card-link" onClick={() => navigate("chat")}>Learn more <ArrowRight size={14} /></button></article>)}</div></section>
    <section className="how-section"><div className="how-intro"><div className="eyebrow">SIMPLE BY DESIGN</div><h2>From question<br />to clarity.</h2><p>A careful workflow that puts the source before the answer.</p><button className="button-outline" onClick={() => navigate("about")}>How it works <ArrowRight size={15} /></button></div><div className="steps">{[
      ["01", "Ask", "Type your question in everyday language."],
      ["02", "Find evidence", "Relevant sections are retrieved from the supplied policy library."],
      ["03", "Verify", "The response is checked against its exact supporting quote."],
      ["04", "Understand", "Get a clear answer, confidence, and source—or an honest gap."],
    ].map(([num, title, text], index) => <div className="step" key={num}><span className={`step-num ${index === 0 ? "step-current" : ""}`}>{num}</span><div><strong>{title}</strong><p>{text}</p></div>{index < 3 && <ArrowDown className="step-down" size={14} />}</div>)}</div></section>
    <section className="team-strip"><span className="team-icon"><GraduationCap size={20} /></span><div><strong>Built by Team GroundTruth</strong><p>SCSE4041 · Prompt Engineering · Bennett University student project</p></div><button className="text-link" onClick={() => navigate("about")}>Meet the team <ArrowRight size={15} /></button></section>
    <div className="fictional-banner"><Info size={16} /><span><b>Demonstration only.</b> This prototype uses clearly labeled fictional sample policies—not official Bennett University rules.</span><button onClick={() => navigate("library")}>View sample library <ArrowRight size={14} /></button></div>
  </div>;
}

function Chat({ history, setHistory, navigate }) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [version, setVersion] = useState("v3");
  const scrollRef = useRef(null);
  useEffect(() => scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }), [history, loading]);
  const submit = async (value = question) => {
    const text = value.trim();
    if (!text || loading) return;
    setQuestion(""); setError(""); setLoading(true);
    const id = `${Date.now()}-${Math.random()}`;
    setHistory((items) => [...items, { id, question: text, pending: true }]);
    try {
      const response = await fetch(`${API}/api/ask`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: text, prompt_version: version }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "The assistant could not answer right now.");
      setHistory((items) => items.map((item) => item.id === id ? { ...item, answer: data, pending: false } : item));
    } catch (requestError) {
      setHistory((items) => items.filter((item) => item.id !== id));
      setError(`${requestError.message} Is the backend running?`);
    } finally { setLoading(false); }
  };
  return <div className="page-content chat-page">
    <div className="page-title-row"><div><div className="eyebrow">THE POLICY ASSISTANT</div><h1>Ask CampusAnswer</h1><p>Get a clear answer, grounded in your campus policy documents.</p></div><button className="button-outline clear-button" onClick={() => setHistory([])} disabled={!history.length}><Plus size={16} /> New conversation</button></div>
    <div className="chat-layout"><section className="chat-panel"><div className="chat-panel-head"><div className="assistant-identity"><span className="assistant-avatar"><Sparkles size={18} /></span><span><strong>CampusAnswer</strong><small><i className="online-dot" /> Ready to help</small></span></div><label className="version-select">Prompt <select value={version} onChange={(event) => setVersion(event.target.value)}><option value="v1">Version 1 · Baseline</option><option value="v2">Version 2 · Improved</option><option value="v3">Version 3 · Final</option></select><ChevronDown size={13} /></label></div>
      <div className="chat-messages">{history.length === 0 ? <div className="chat-empty"><span className="empty-art"><MessageCircle size={25} /><Sparkles size={15} /></span><h2>What would you like to know?</h2><p>Ask about attendance, exams, fees, or hostel policies.</p><div className="suggestion-list">{suggestions.map((item) => <button key={item} onClick={() => submit(item)}>{item}<ArrowRight size={14} /></button>)}</div><div className="chat-disclaimer"><ShieldCheck size={14} /> Answers use supplied policy documents only</div></div> : <div className="message-list">{history.map((item) => <div className="conversation-turn" key={item.id}><div className="user-message"><span className="user-avatar">Y</span><span>{item.question}</span></div>{item.pending ? <div className="assistant-message"><span className="assistant-avatar"><Sparkles size={15} /></span><span className="typing-indicator"><i /><i /><i /> Checking policy sources…</span></div> : <AnswerCard answer={item.answer} />}</div>)}
      {error && <div className="inline-error"><Info size={16} />{error}</div>}<div ref={scrollRef} /></div>}</div>
      <form className="composer" onSubmit={(event) => { event.preventDefault(); submit(); }}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } }} placeholder="Ask a policy question…" rows={1} maxLength={2000} /><div className="composer-bottom"><span><ShieldCheck size={13} /> Grounded answers only</span><button className="send-button" type="submit" disabled={!question.trim() || loading} aria-label="Send question">{loading ? <LoaderCircle size={17} className="spin" /> : <Send size={16} />}</button></div></form><div className="composer-footnote">CampusAnswer can make mistakes. Check the cited document and contact the relevant office for official guidance.</div>
    </section><aside className="chat-side"><div className="side-card"><div className="side-card-icon"><ShieldCheck size={18} /></div><h3>Trust, with receipts.</h3><p>Every supported response includes a source document, section, and exact quotation.</p><div className="side-divider" /><div className="side-status"><span className="status-dot" /><span><b>Grounding check</b><small>Quotes are verified against source text</small></span></div></div><div className="side-card side-card-light"><h3>Try asking</h3><div className="side-prompts">{suggestions.map((item) => <button key={item} onClick={() => submit(item)}>{item}<ArrowRight size={14} /></button>)}</div><button className="browse-link" onClick={() => navigate("library")}>Browse policy library <ArrowRight size={14} /></button></div><div className="side-footnote"><Info size={14} /><span>Fictional demonstration content. Not official university guidance.</span></div></aside></div>
  </div>;
}

function AnswerCard({ answer }) {
  const statusLabels = { supported: "Evidence found", unsupported: "Not in the supplied documents", conflict: "Conflicting sources", clarification_needed: "One question at a time", refused: "Outside supported topics" };
  const cls = answer.status === "supported" ? "answer-supported" : "answer-caution";
  return <div className="assistant-message"><span className="assistant-avatar"><Sparkles size={15} /></span><div className={`answer-card ${cls}`}><div className="answer-topline"><span className="answer-status"><span />{statusLabels[answer.status] || answer.status}</span><span className={`mode-tag ${answer.mode}`}>{answer.mode === "gemini" ? "GEMINI" : "DEMO LOOKUP"}</span></div><p className="answer-text">{answer.answer}</p>{answer.citations?.map((citation, index) => <div className="citation-card" key={`${citation.source_document}-${citation.source_section}-${index}`}><div className="citation-header"><FileText size={15} /><strong>{citation.source_document}</strong><span>§ {citation.source_section}</span></div><blockquote>“{citation.source_quote}”</blockquote><div className="citation-verified"><Check size={12} /> Exact text from supplied document</div></div>)}<div className="answer-meta"><span className={`confidence confidence-${answer.confidence.toLowerCase()}`}><span className="confidence-dot" />{answer.confidence} confidence</span><span className="category-chip">{answer.category.replace("_", " ")}</span>{answer.contact && <span className="contact-note">Contact: {answer.contact}</span>}</div></div></div>;
}

function Library({ documents, docError, refreshDocuments }) {
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
      const response = await fetch(`${API}/api/documents/upload`, { method: "POST", body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Upload failed.");
      setUploadState("Document added to the local demo library."); await refreshDocuments();
    } catch (error) { setUploadState(""); setUploadError(error.message); }
    finally { event.target.value = ""; }
  };
  return <div className="page-content"><div className="page-title-row"><div><div className="eyebrow">YOUR SOURCES</div><h1>Policy library</h1><p>Browse the text CampusAnswer can—and cannot—use to answer questions.</p></div><button className="button-primary upload-button" onClick={() => fileRef.current?.click()}><Upload size={16} /> Upload a document</button><input ref={fileRef} type="file" accept=".txt,.pdf,text/plain,application/pdf" hidden onChange={upload} /></div>
    <div className="library-notice"><Info size={17} /><div><strong>Demo documents are fictional</strong><p>Sample policies below are for testing only and are not Bennett University policies. Uploaded documents are stored locally and labeled separately.</p></div></div>
    {(uploadState || uploadError || docError) && <div className={`upload-feedback ${uploadError || docError ? "is-error" : ""}`}>{uploadError || docError || uploadState}</div>}
    <div className="library-toolbar"><div className="library-count"><strong>{filtered.length}</strong> documents <span>·</span> {filtered.reduce((sum, document) => sum + document.sections.length, 0)} sections</div><div className="search-field"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search documents…" /></div></div>
    {filtered.length ? <div className="document-grid">{filtered.map((document) => <article className="document-card" key={document.filename}><div className="document-card-head"><span className={`document-icon ${document.fictional ? "fictional" : "uploaded"}`}><FileText size={18} /></span><span className={`document-badge ${document.fictional ? "badge-fictional" : "badge-uploaded"}`}>{document.fictional ? "FICTIONAL SAMPLE" : "LOCAL UPLOAD"}</span></div><h3>{document.title}</h3><p className="file-name">{document.filename}</p><div className="document-stats"><span><BookOpen size={14} />{document.sections.length} sections</span><span><ShieldCheck size={14} />Source text available</span></div><div className="section-list">{document.sections.map((section) => <div className="section-item" key={`${document.filename}-${section.section}`}><button onClick={() => setExpanded((state) => ({ ...state, [`${document.filename}-${section.section}`]: !state[`${document.filename}-${section.section}`] }))}><span className="section-index">{section.section}</span><span>{section.title}</span><ChevronDown className={expanded[`${document.filename}-${section.section}`] ? "rotated" : ""} size={15} /></button>{expanded[`${document.filename}-${section.section}`] && <p className="section-text">{section.text}</p>}</div>)}</div></article>)}</div> : <div className="empty-state"><Search size={22} /><strong>No matching documents</strong><span>Try a different title or keyword.</span></div>}
    <div className="upload-hint"><Upload size={17} /><span><b>Adding local demo documents</b><small>Upload TXT or text-based PDF (max 5 MB). TXT section headings: “## Section 1.2 | Title”.</small></span></div>
  </div>;
}

function Evaluation({ evaluation, evaluationError }) {
  const [typeFilter, setTypeFilter] = useState("All tests");
  const [statusFilter, setStatusFilter] = useState("All results");
  const [versionFilter, setVersionFilter] = useState("v3");
  if (!evaluation) return <div className="page-content"><div className="page-title-row"><div><div className="eyebrow">PROMPT ENGINEERING</div><h1>Prompt evaluation</h1><p>Results are shown only after test cases have actually run.</p></div></div><div className="empty-state evaluation-empty"><FlaskConical size={24} /><strong>{evaluationError || "Loading executed test results…"}</strong><span>Run <code>python backend/run_evaluation.py</code> to generate genuine demo-mode results.</span></div></div>;
  const versionRows = evaluation.results.filter((row) => row.prompt_version === versionFilter);
  const versionPassed = versionRows.filter((row) => row.pass).length;
  const rows = versionRows.filter((row) => (typeFilter === "All tests" || row.test_type === typeFilter) && (statusFilter === "All results" || (row.pass ? "Pass" : "Fail") === statusFilter));
  const categoryStats = Object.entries(versionRows.reduce((acc, row) => { const key = row.actual_output.category; acc[key] ||= { total: 0, passed: 0 }; acc[key].total++; acc[key].passed += row.pass ? 1 : 0; return acc; }, {}));
  return <div className="page-content"><div className="page-title-row"><div><div className="eyebrow">PROMPT ENGINEERING</div><h1>Test & learn</h1><p>Executed checks for grounded answers, uncertainty, and safe boundaries.</p></div><span className="executed-badge"><span /> EXECUTED RESULTS</span></div>
    <div className="evaluation-banner"><span className="evaluation-icon"><FlaskConical size={19} /></span><div><strong>{evaluation.evaluation_mode === "deterministic_demo" ? "Deterministic demo evaluation" : "Live Gemini evaluation"}</strong><p>{evaluation.evaluation_mode === "deterministic_demo" ? "Each input was run against V1, V2, and V3 using deterministic lookup. These results do not measure live model quality or prove one prompt is better." : "Each input was run against V1, V2, and V3 with the configured Gemini model and settings."}</p></div><span className="evaluation-version">{versionFilter.toUpperCase()} · SELECTED PROMPT</span></div>
    <div className="metric-grid"><Metric label="Tests executed" value={versionRows.length} note={`${versionFilter.toUpperCase()} test cases`} icon={FlaskConical} /><Metric label="Passed" value={versionPassed} note={`of ${versionRows.length} tests`} icon={Check} /><Metric label="Pass rate" value={`${versionRows.length ? (100 * versionPassed / versionRows.length).toFixed(1) : 0}%`} note="This prompt version" icon={ShieldCheck} /><Metric label="Test categories" value={categoryStats.length} note="Policy topics covered" icon={BookOpen} /></div>
    <section className="category-results"><div className="section-heading compact-heading"><div><h2>Results by category</h2><p>Calculated from this recorded run.</p></div></div><div className="category-bars">{categoryStats.map(([name, stats]) => <div className="category-row" key={name}><span className="cat-name">{name.replace("_", " ")}</span><div className="bar-track"><span style={{ width: `${stats.total ? stats.passed / stats.total * 100 : 0}%` }} /></div><span className="cat-count">{stats.passed}/{stats.total}</span></div>)}</div></section>
    <section className="test-results"><div className="section-heading compact-heading"><div><h2>Test cases</h2><p>Expected behavior compared with the response actually returned.</p></div><div className="filter-controls"><select aria-label="Prompt version" value={versionFilter} onChange={(event) => setVersionFilter(event.target.value)}><option value="v1">V1 · Baseline</option><option value="v2">V2 · Improved</option><option value="v3">V3 · Final</option></select><select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option>All tests</option><option>Normal</option><option>Edge</option><option>Invalid</option></select><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option>All results</option><option>Pass</option><option>Fail</option></select></div></div><div className="test-table-wrap"><table className="test-table"><thead><tr><th>NO.</th><th>TEST INPUT</th><th>VERSION</th><th>TYPE</th><th>ACTUAL STATUS</th><th>RESULT</th></tr></thead><tbody>{rows.map((row) => <tr key={row.test_number}><td className="test-num">#{String(row.test_number).padStart(2, "0")}</td><td><strong className="test-input">{row.input}</strong><small className="test-expect">Expected: {row.expected_output.status} · Actual: {row.actual_output.status}</small><details className="test-details"><summary>Inspect expected and actual output</summary><div className="test-output-pair"><div><b>Expected</b><pre>{JSON.stringify(row.expected_output, null, 2)}</pre></div><div><b>Actual</b><pre>{JSON.stringify(row.actual_output, null, 2)}</pre></div></div></details></td><td>{row.prompt_version.toUpperCase()}</td><td><span className={`type-label type-${row.test_type.toLowerCase()}`}>{row.test_type}</span></td><td><span className={`status-label ${row.actual_output.status === "supported" ? "status-ok" : "status-neutral"}`}>{row.actual_output.status.replace("_", " ")}</span></td><td><span className={`result-label ${row.pass ? "result-pass" : "result-fail"}`}><span />{row.pass ? "PASS" : "FAIL"}</span></td></tr>)}</tbody></table>{rows.length === 0 && <div className="empty-filter">No tests match these filters.</div>}</div></section>
    <div className="evaluation-foot"><Clock3 size={14} /> Executed {new Date(evaluation.executed_at_utc).toLocaleString()} · Results saved in <code>test-data/demo-evaluation-results.json</code></div>
  </div>;
}

function Metric({ label, value, note, icon: Icon }) {
  return <div className="metric-card"><span className="metric-icon"><Icon size={17} /></span><span className="metric-label">{label}</span><strong>{value}</strong><small>{note}</small></div>;
}

function About() {
  return <div className="page-content about-page"><div className="page-title-row"><div><div className="eyebrow">THE STORY BEHIND THE TOOL</div><h1>About CampusAnswer</h1><p>A student-built exploration of trustworthy, document-grounded policy Q&A.</p></div><span className="project-id">PROJECT C1 <span>·</span> MILESTONE 2</span></div>
    <section className="about-hero"><div className="about-icon"><GraduationCap size={23} /></div><div><div className="eyebrow">FULL TITLE</div><h2>CampusAnswer: A Document-Grounded Prompt Workflow for University Policy Q&amp;A</h2><p>CampusAnswer explores how prompt design, source retrieval, structured outputs, and quotation verification can make a university helpdesk assistant more transparent and cautious.</p></div></section>
    <div className="about-grid"><section className="content-card"><h3><span className="card-heading-icon"><CircleHelp size={17} /></span>The problem</h3><p>University policies can be spread across documents, making it difficult for students to quickly find reliable answers. A generative system can also sound confident when source information is incomplete.</p></section><section className="content-card"><h3><span className="card-heading-icon"><Sparkles size={17} /></span>Our approach</h3><p>Retrieve relevant supplied sections, constrain answers to that evidence, return structured citations, and verify quoted text. When the evidence is missing or conflicting, the assistant should say so instead of guessing.</p></section><section className="content-card"><h3><span className="card-heading-icon"><BookOpen size={17} /></span>Tools & technology</h3><div className="tech-tags">{["React", "Vite", "Tailwind CSS", "FastAPI", "Pydantic", "Gemini API", "Python"].map((item) => <span key={item}>{item}</span>)}</div><p className="tech-note">Gemini is optional; deterministic local lookup is clearly labeled in demo mode.</p></section><section className="content-card"><h3><span className="card-heading-icon"><ShieldCheck size={17} /></span>Prompt engineering focus</h3><p>Three saved prompt iterations progress from a short baseline to explicit scope, evidence, uncertainty, conflict, injection-resistance, and JSON rules. The recorded demo tests exercise behavior—not comparative model quality.</p></section></div>
    <section className="milestone-section"><div className="section-heading compact-heading"><div><div className="eyebrow">PROJECT PROGRESS</div><h2>Milestone 1 → Milestone 2</h2></div></div><div className="milestone-track"><div className="milestone-item"><span className="milestone-dot done"><Check size={13} /></span><div><span className="milestone-label">MILESTONE 1</span><h3>Prompt foundations</h3><p>Baseline helpdesk prompt and problem framing.</p></div></div><div className="milestone-connector" /><div className="milestone-item"><span className="milestone-dot current"><span /></span><div><span className="milestone-label">MILESTONE 2</span><h3>Working prototype</h3><p>Full-stack workflow, document library, verification, and executed evaluation harness.</p></div></div></div></section>
    <section className="team-section"><div className="section-heading compact-heading"><div><div className="eyebrow">TEAM GROUNDTRUTH</div><h2>Built as a team project.</h2></div><span className="course-badge">SCSE4041 · Prompt Engineering</span></div><div className="team-grid">{[
      ["DM", "Devansh Mishra", "S24CSEU1328", "Team Leader"],
      ["PA", "Pranav Agrawal", "S24CSEU1336", "Team Member"],
      ["AS", "Ansh Sharma", "S24CSEU1332", "Team Member"],
      ["NS", "Nirnay Pratap Singh", "S24CSEU1368", "Team Member"],
    ].map(([initials, name, id, role]) => <div className="team-card" key={id}><span className="team-avatar">{initials}</span><strong>{name}</strong><small>{id}</small><span className="team-role">{role}</span></div>)}</div></section>
    <div className="fictional-banner"><Info size={16} /><span><b>Important:</b> the included policy documents are fictional demonstration examples and are not Bennett University policies.</span></div>
  </div>;
}

export default App;
