import React, { useState, useEffect } from "react";
import {
  listProjects,
  getContextPack,
  captureDecision,
  ingestText,
  ingestFile,
} from "../api/client";

export default function ContextPack({ activeProject, setActiveProject }) {
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");

  // Section 1: Context Pack state
  const [task, setTask] = useState("");
  const [target, setTarget] = useState("chatgpt");
  const [maxChars, setMaxChars] = useState(3000);
  const [generatingPack, setGeneratingPack] = useState(false);
  const [packResult, setPackResult] = useState(null);
  const [packError, setPackError] = useState(null);
  const [copied, setCopied] = useState(false);

  // Section 2: Capture Decisions state
  const [captureText, setCaptureText] = useState("");
  const [captureSourceName, setCaptureSourceName] = useState("");
  const [capturing, setCapturing] = useState(false);
  const [captureResult, setCaptureResult] = useState(null);
  const [captureError, setCaptureError] = useState(null);

  // Section 3: Ingest Documents state
  const [ingestContent, setIngestContent] = useState("");
  const [ingestName, setIngestName] = useState("");
  const [ingestType, setIngestType] = useState("doc");
  const [selectedFile, setSelectedFile] = useState(null);
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState(null);
  const [ingestError, setIngestError] = useState(null);

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    if (activeProject?.id) {
      setSelectedProjectId(activeProject.id);
    } else if (projects.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projects[0].id);
    }
  }, [activeProject, projects]);

  const loadProjects = async () => {
    try {
      const data = await listProjects();
      setProjects(data);
      if (data.length > 0 && !selectedProjectId) {
        setSelectedProjectId(activeProject?.id || data[0].id);
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    }
  };

  const handleProjectChange = (e) => {
    const pId = e.target.value;
    setSelectedProjectId(pId);
    const p = projects.find((proj) => proj.id === pId);
    if (p && setActiveProject) {
      setActiveProject(p);
    }
  };

  // 1. Generate Context Pack
  const handleGeneratePack = async (e) => {
    e?.preventDefault();
    if (!task.trim() || !selectedProjectId) return;
    setGeneratingPack(true);
    setPackError(null);
    setCopied(false);

    try {
      const res = await getContextPack(selectedProjectId, {
        task: task.trim(),
        target,
        max_chars: parseInt(maxChars, 10) || 3000,
      });
      setPackResult(res);
    } catch (err) {
      setPackError(err.response?.data?.detail || err.message || "Failed to generate context pack");
    } finally {
      setGeneratingPack(false);
    }
  };

  const handleCopyPack = () => {
    if (!packResult?.pack) return;
    navigator.clipboard.writeText(packResult.pack);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // 2. Capture Decision
  const handleCapture = async (e) => {
    e?.preventDefault();
    if (!captureText.trim() || !selectedProjectId) return;
    setCapturing(true);
    setCaptureError(null);
    setCaptureResult(null);

    try {
      const res = await captureDecision(selectedProjectId, {
        text: captureText.trim(),
        source_name: captureSourceName.trim() || "manual_capture",
      });
      setCaptureResult(res);
      setCaptureText("");
    } catch (err) {
      setCaptureError(err.response?.data?.detail || err.message || "Failed to capture decision");
    } finally {
      setCapturing(false);
    }
  };

  // 3. Ingest Document (Paste or File)
  const handleIngest = async (e) => {
    e?.preventDefault();
    if (!selectedProjectId) return;
    setIngesting(true);
    setIngestError(null);
    setIngestResult(null);

    try {
      if (selectedFile) {
        const formData = new FormData();
        formData.append("file", selectedFile);
        formData.append("source_type", ingestType);
        const res = await ingestFile(selectedProjectId, formData);
        setIngestResult(res);
        setSelectedFile(null);
      } else if (ingestContent.trim()) {
        const res = await ingestText(selectedProjectId, {
          text: ingestContent.trim(),
          source_type: ingestType,
          source_name: ingestName.trim() || "pasted_document.txt",
        });
        setIngestResult(res);
        setIngestContent("");
        setIngestName("");
      }
    } catch (err) {
      setIngestError(err.response?.data?.detail || err.message || "Failed to ingest content");
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div style={styles.container}>
      {/* Hero Header */}
      <div style={styles.header}>
        <div style={styles.tagline}>One project. One memory. Every AI assistant.</div>
        <h1 style={styles.title}>Project Context Packs</h1>
        <p style={styles.subtitle}>
          Generate compact, grounded context blocks to paste or pipe into ChatGPT, Claude, Cursor, or Codex.
          All assistants share the exact same project memory without manual re-explanation.
        </p>

        {/* Global Project Selector */}
        <div style={styles.projectSelectRow}>
          <label style={styles.projectLabel}>Active Project:</label>
          <select
            value={selectedProjectId}
            onChange={handleProjectChange}
            style={styles.select}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.id})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={styles.sectionsGrid}>
        {/* SECTION 1: CONTEXT PACK GENERATOR */}
        <div style={styles.cardPrimary}>
          <div style={styles.cardHeader}>
            <span style={styles.badge}>Step 1</span>
            <h2 style={styles.cardTitle}>Generate Context Pack</h2>
          </div>
          <p style={styles.cardDesc}>
            Enter your task and choose the target assistant. OneContext recalls the most relevant decisions and formats the pack.
          </p>

          {packError && <div style={styles.errorBox}>⚠️ {packError}</div>}

          <form onSubmit={handleGeneratePack} style={styles.form}>
            <div style={styles.field}>
              <label style={styles.label}>Your Task or Prompt *</label>
              <textarea
                required
                rows={3}
                value={task}
                onChange={(e) => setTask(e.target.value)}
                placeholder="e.g. Implement user login authentication and session validation..."
                style={styles.textarea}
              />
            </div>

            <div style={styles.row}>
              <div style={{ ...styles.field, flex: 1 }}>
                <label style={styles.label}>Target AI Assistant</label>
                <select
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  style={styles.select}
                >
                  <option value="chatgpt">ChatGPT</option>
                  <option value="claude">Claude</option>
                  <option value="cursor">Cursor (Rules format)</option>
                  <option value="codex">Codex</option>
                  <option value="generic">Generic Markdown</option>
                </select>
              </div>

              <div style={{ ...styles.field, width: "130px" }}>
                <label style={styles.label}>Max Chars</label>
                <input
                  type="number"
                  min="200"
                  max="10000"
                  step="200"
                  value={maxChars}
                  onChange={(e) => setMaxChars(e.target.value)}
                  style={styles.input}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={generatingPack || !task.trim()}
              style={{
                ...styles.btnPrimary,
                opacity: generatingPack || !task.trim() ? 0.6 : 1,
              }}
            >
              {generatingPack ? "Generating Context Pack..." : "📦 Generate Context Pack"}
            </button>
          </form>

          {/* Context Pack Output Showcase */}
          {packResult && (
            <div style={styles.packOutputContainer}>
              <div style={styles.packOutputHeader}>
                <div>
                  <strong style={{ color: "#60a5fa" }}>Context Pack Ready</strong>
                  <span style={styles.charCount}>({packResult.char_count} chars)</span>
                </div>
                <button onClick={handleCopyPack} style={styles.copyBtn}>
                  {copied ? "✓ Copied to Clipboard!" : "📋 Copy Pack"}
                </button>
              </div>

              <pre style={styles.packCodeBlock}>{packResult.pack}</pre>

              {/* Sources Used List */}
              {packResult.sources_used?.length > 0 && (
                <div style={styles.sourcesUsed}>
                  <strong style={{ fontSize: "0.75rem", color: "#a1a1aa" }}>Sources Cited in Pack:</strong>
                  <ul style={styles.sourcesList}>
                    {packResult.sources_used.map((s, idx) => (
                      <li key={idx} style={styles.sourceItem}>
                        <span style={styles.sourceTypeBadge}>{s.source || "doc"}</span>
                        <span>{s.text?.slice(0, 80)}...</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* SECTION 2 & 3: CAPTURE & INGESTION COLUMN */}
        <div style={styles.sideColumn}>
          {/* SECTION 2: CAPTURE DECISIONS */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <span style={styles.badgeGreen}>Capture</span>
              <h2 style={styles.cardTitle}>Capture New Decision</h2>
            </div>
            <p style={styles.cardDesc}>
              Record an architecture decision or rule into Hindsight. Real-time conflict detection alerts you if it contradicts past decisions.
            </p>

            {captureError && <div style={styles.errorBox}>⚠️ {captureError}</div>}
            {captureResult && (
              <div>
                {captureResult.has_conflict ? (
                  <div style={styles.conflictCard}>
                    <strong>⚠️ Policy Conflict Detected!</strong>
                    <div style={{ marginTop: "4px", fontSize: "0.8rem" }}>
                      {captureResult.conflict?.explanation || "Contradicts an existing project decision."}
                    </div>
                  </div>
                ) : (
                  <div style={styles.successBox}>
                    ✅ Decision captured cleanly (Memory ID: {captureResult.memory_id})
                  </div>
                )}
              </div>
            )}

            <form onSubmit={handleCapture} style={styles.form}>
              <div style={styles.field}>
                <label style={styles.label}>Decision / Policy Text *</label>
                <textarea
                  required
                  rows={3}
                  value={captureText}
                  onChange={(e) => setCaptureText(e.target.value)}
                  placeholder="e.g. All API authentication tokens must use RS256 JWT with 15-minute expiration..."
                  style={styles.textarea}
                />
              </div>

              <div style={styles.field}>
                <label style={styles.label}>Source Identifier</label>
                <input
                  type="text"
                  value={captureSourceName}
                  onChange={(e) => setCaptureSourceName(e.target.value)}
                  placeholder="e.g. ADR-009, security_review, meeting_notes"
                  style={styles.input}
                />
              </div>

              <button
                type="submit"
                disabled={capturing || !captureText.trim()}
                style={{
                  ...styles.btnSuccess,
                  opacity: capturing || !captureText.trim() ? 0.6 : 1,
                }}
              >
                {capturing ? "Capturing..." : "💾 Capture Decision"}
              </button>
            </form>
          </div>

          {/* SECTION 3: INGEST DOCUMENTS */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <span style={styles.badgePurple}>Ingest</span>
              <h2 style={styles.cardTitle}>Ingest Documents</h2>
            </div>
            <p style={styles.cardDesc}>
              Upload a <code>.md</code> or <code>.txt</code> file or paste document text. Automatically chunks and indexes into project memory.
            </p>

            {ingestError && <div style={styles.errorBox}>⚠️ {ingestError}</div>}
            {ingestResult && (
              <div style={styles.successBox}>
                ✅ Ingested "{ingestResult.source_name}": {ingestResult.chunks_retained} chunks retained ({ingestResult.chunks_skipped} duplicates skipped).
              </div>
            )}

            <form onSubmit={handleIngest} style={styles.form}>
              {/* File upload picker */}
              <div style={styles.field}>
                <label style={styles.label}>Upload File (.md, .txt)</label>
                <input
                  type="file"
                  accept=".md,.txt"
                  onChange={(e) => setSelectedFile(e.target.files[0] || null)}
                  style={styles.fileInput}
                />
                {selectedFile && (
                  <span style={{ fontSize: "0.75rem", color: "#60a5fa" }}>
                    Selected: {selectedFile.name}
                  </span>
                )}
              </div>

              <div style={{ textAlign: "center", color: "#52525b", fontSize: "0.75rem" }}>— OR PASTE TEXT —</div>

              <div style={styles.field}>
                <label style={styles.label}>Paste Document Content</label>
                <textarea
                  rows={3}
                  value={ingestContent}
                  onChange={(e) => setIngestContent(e.target.value)}
                  placeholder="Paste specification, README, or engineering design notes..."
                  style={styles.textarea}
                  disabled={Boolean(selectedFile)}
                />
              </div>

              <div style={styles.row}>
                <div style={{ ...styles.field, flex: 1 }}>
                  <label style={styles.label}>Document Name</label>
                  <input
                    type="text"
                    value={ingestName}
                    onChange={(e) => setIngestName(e.target.value)}
                    placeholder="e.g. architecture_spec.md"
                    style={styles.input}
                    disabled={Boolean(selectedFile)}
                  />
                </div>

                <div style={{ ...styles.field, width: "120px" }}>
                  <label style={styles.label}>Type</label>
                  <select
                    value={ingestType}
                    onChange={(e) => setIngestType(e.target.value)}
                    style={styles.select}
                  >
                    <option value="doc">Document</option>
                    <option value="decision">Decision</option>
                    <option value="note">Note</option>
                    <option value="chat_export">Chat Export</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                disabled={ingesting || (!selectedFile && !ingestContent.trim())}
                style={{
                  ...styles.btnPurple,
                  opacity: ingesting || (!selectedFile && !ingestContent.trim()) ? 0.6 : 1,
                }}
              >
                {ingesting ? "Ingesting..." : "📥 Ingest into Project Memory"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    maxWidth: "1200px",
    margin: "0 auto",
    padding: "28px 16px",
  },
  header: {
    marginBottom: "28px",
    borderBottom: "1px solid #27272a",
    paddingBottom: "20px",
  },
  tagline: {
    fontSize: "0.85rem",
    fontWeight: "700",
    color: "#38bdf8",
    letterSpacing: "1px",
    textTransform: "uppercase",
    marginBottom: "6px",
  },
  title: {
    fontSize: "2rem",
    fontWeight: "800",
    color: "#f4f4f5",
    margin: "0 0 8px 0",
  },
  subtitle: {
    fontSize: "0.95rem",
    color: "#a1a1aa",
    margin: 0,
    lineHeight: "1.5",
    maxWidth: "800px",
  },
  projectSelectRow: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginTop: "16px",
  },
  projectLabel: {
    fontSize: "0.85rem",
    fontWeight: "600",
    color: "#d4d4d8",
  },
  sectionsGrid: {
    display: "grid",
    gridTemplateColumns: "1.2fr 1fr",
    gap: "24px",
  },
  cardPrimary: {
    backgroundColor: "#18181b",
    border: "1px solid #3b82f6",
    borderRadius: "8px",
    padding: "24px",
    display: "flex",
    flexDirection: "column",
  },
  sideColumn: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
  },
  card: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "8px",
    padding: "20px",
  },
  cardHeader: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginBottom: "6px",
  },
  badge: {
    backgroundColor: "#1e3a8a",
    color: "#93c5fd",
    fontSize: "0.7rem",
    fontWeight: "700",
    padding: "2px 8px",
    borderRadius: "4px",
  },
  badgeGreen: {
    backgroundColor: "#064e3b",
    color: "#6ee7b7",
    fontSize: "0.7rem",
    fontWeight: "700",
    padding: "2px 8px",
    borderRadius: "4px",
  },
  badgePurple: {
    backgroundColor: "#581c87",
    color: "#d8b4fe",
    fontSize: "0.7rem",
    fontWeight: "700",
    padding: "2px 8px",
    borderRadius: "4px",
  },
  cardTitle: {
    fontSize: "1.15rem",
    fontWeight: "700",
    color: "#fafafa",
    margin: 0,
  },
  cardDesc: {
    fontSize: "0.82rem",
    color: "#a1a1aa",
    margin: "0 0 16px 0",
    lineHeight: "1.4",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  label: {
    fontSize: "0.8rem",
    fontWeight: "600",
    color: "#d4d4d8",
  },
  input: {
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "8px 12px",
    color: "#fafafa",
    fontSize: "0.85rem",
    outline: "none",
  },
  textarea: {
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "10px 12px",
    color: "#fafafa",
    fontSize: "0.85rem",
    outline: "none",
    resize: "vertical",
    fontFamily: "inherit",
  },
  select: {
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "8px 12px",
    color: "#fafafa",
    fontSize: "0.85rem",
    outline: "none",
  },
  fileInput: {
    fontSize: "0.8rem",
    color: "#a1a1aa",
  },
  row: {
    display: "flex",
    gap: "12px",
  },
  btnPrimary: {
    backgroundColor: "#3b82f6",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    padding: "10px 16px",
    fontSize: "0.9rem",
    fontWeight: "700",
    cursor: "pointer",
    marginTop: "6px",
  },
  btnSuccess: {
    backgroundColor: "#10b981",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    padding: "9px 14px",
    fontSize: "0.85rem",
    fontWeight: "700",
    cursor: "pointer",
  },
  btnPurple: {
    backgroundColor: "#8b5cf6",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    padding: "9px 14px",
    fontSize: "0.85rem",
    fontWeight: "700",
    cursor: "pointer",
  },
  errorBox: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid #ef4444",
    borderRadius: "6px",
    padding: "10px 12px",
    color: "#fca5a5",
    fontSize: "0.85rem",
    marginBottom: "12px",
  },
  successBox: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    border: "1px solid #10b981",
    borderRadius: "6px",
    padding: "10px 12px",
    color: "#6ee7b7",
    fontSize: "0.85rem",
    marginBottom: "12px",
  },
  conflictCard: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid #ef4444",
    borderRadius: "6px",
    padding: "10px 12px",
    color: "#fca5a5",
    marginBottom: "12px",
  },
  packOutputContainer: {
    marginTop: "20px",
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "8px",
    padding: "16px",
  },
  packOutputHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "10px",
  },
  charCount: {
    fontSize: "0.75rem",
    color: "#71717a",
    marginLeft: "8px",
  },
  copyBtn: {
    backgroundColor: "#2563eb",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    padding: "6px 14px",
    fontSize: "0.8rem",
    fontWeight: "700",
    cursor: "pointer",
  },
  packCodeBlock: {
    backgroundColor: "#121216",
    border: "1px solid #27272a",
    borderRadius: "6px",
    padding: "12px",
    color: "#e4e4e7",
    fontSize: "0.82rem",
    fontFamily: "monospace",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    maxHeight: "350px",
    overflowY: "auto",
    lineHeight: "1.45",
  },
  sourcesUsed: {
    marginTop: "12px",
    borderTop: "1px solid #27272a",
    paddingTop: "8px",
  },
  sourcesList: {
    listStyle: "none",
    padding: 0,
    margin: "6px 0 0 0",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  sourceItem: {
    fontSize: "0.75rem",
    color: "#d4d4d8",
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  sourceTypeBadge: {
    backgroundColor: "#27272a",
    color: "#a1a1aa",
    fontSize: "0.65rem",
    padding: "1px 6px",
    borderRadius: "3px",
  },
};
