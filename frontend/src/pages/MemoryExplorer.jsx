import React, { useEffect, useState } from "react";
import { recallMemory, retainMemory, correctMemory, getConflicts } from "../api/client";
import MemoryCard from "../components/MemoryCard";

export default function MemoryExplorer({ activeProject }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Retain memory modal / form state
  const [showRetainModal, setShowRetainModal] = useState(false);
  const [newText, setNewText] = useState("");
  const [newSource, setNewSource] = useState("architecture_decision");
  const [newAgentId, setNewAgentId] = useState("lead-architect");
  const [retaining, setRetaining] = useState(false);
  const [successMsg, setSuccessMsg] = useState(null);

  // Conflict state
  const [activeConflict, setActiveConflict] = useState(null);
  const [conflictLogs, setConflictLogs] = useState([]);

  // Correction modal state
  const [showCorrectModal, setShowCorrectModal] = useState(false);
  const [targetMemory, setTargetMemory] = useState(null);
  const [correctionText, setCorrectionText] = useState("");
  const [correctionReason, setCorrectionReason] = useState("");
  const [correcting, setCorrecting] = useState(false);

  useEffect(() => {
    if (activeProject?.id) {
      handleSearch("architecture decisions");
      loadConflicts();
    }
  }, [activeProject]);

  const loadConflicts = async () => {
    if (!activeProject?.id) return;
    try {
      const data = await getConflicts(activeProject.id);
      setConflictLogs(data.conflicts || []);
    } catch {
      // Non-critical, ignore
    }
  };

  const handleSearch = async (qToSearch = query) => {
    if (!activeProject?.id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await recallMemory(activeProject.id, {
        query: qToSearch || "decisions and rules",
        max_results: 15,
      });
      setResults(res.results || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRetain = async (e) => {
    e.preventDefault();
    if (!newText.trim() || !activeProject?.id) return;
    setRetaining(true);
    setError(null);
    try {
      const res = await retainMemory(activeProject.id, {
        text: newText,
        source: newSource,
        agent_id: newAgentId,
      });

      if (res.conflict?.has_conflict) {
        setActiveConflict(res.conflict);
      } else {
        setActiveConflict(null);
      }

      setShowRetainModal(false);
      setNewText("");
      setSuccessMsg("Memory successfully retained into Hindsight bank!");
      setTimeout(() => setSuccessMsg(null), 4000);
      handleSearch(newText.slice(0, 40));
      loadConflicts();
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setRetaining(false);
    }
  };

  const openCorrectionModal = (memItem) => {
    setTargetMemory(memItem);
    setCorrectionText(memItem.text);
    setCorrectionReason("");
    setShowCorrectModal(true);
  };

  const handleCorrectSubmit = async (e) => {
    e.preventDefault();
    if (!targetMemory || !correctionText.trim()) return;
    setCorrecting(true);
    setError(null);
    try {
      await correctMemory(activeProject.id, {
        old_memory_id: targetMemory.id,
        new_text: correctionText,
        agent_id: "lead-architect",
        reason: correctionReason || "Policy update / supersession",
      });
      setShowCorrectModal(false);
      setActiveConflict(null);
      setSuccessMsg(`Decision updated! Memory #${targetMemory.id.slice(0, 8)} superseded.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      handleSearch(correctionText.slice(0, 40));
      loadConflicts();
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setCorrecting(false);
    }
  };

  if (!activeProject) {
    return <div style={{ color: "#a1a1aa", padding: "40px" }}>Please select an active project first.</div>;
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Memory Explorer</h1>
          <p style={styles.desc}>
            Explore and search long-term memories in <strong>{activeProject.name}</strong> ({activeProject.bank_id})
          </p>
        </div>
        <button onClick={() => setShowRetainModal(true)} style={styles.retainBtn}>
          + Retain New Memory
        </button>
      </div>

      {successMsg && <div style={styles.successBox}>✅ {successMsg}</div>}
      {error && <div style={styles.errorBox}>⚠️ {error}</div>}

      {/* Conflict Warning Card */}
      {activeConflict && (
        <div style={styles.conflictCard}>
          <div style={styles.conflictHeader}>
            <span style={styles.conflictBadge}>⚠️ Policy Conflict Detected</span>
            <span style={styles.conflictSubtitle}>
              New memory contradicts an established project policy
            </span>
          </div>

          <p style={styles.conflictExplanation}>{activeConflict.explanation}</p>

          <div style={styles.conflictCompareGrid}>
            <div style={styles.conflictColOld}>
              <div style={styles.colHeader}>ESTABLISHED RECORDED DECISION</div>
              <div style={styles.colBody}>
                {activeConflict.conflicting_memory?.text || "Recorded decision"}
              </div>
              <div style={styles.colMeta}>
                Author: {activeConflict.conflicting_memory?.agent_id || "system"}
              </div>
            </div>

            <div style={styles.conflictColNew}>
              <div style={styles.colHeader}>NEW PROPOSED MEMORY</div>
              <div style={styles.colBody}>{activeConflict.new_text}</div>
              <div style={styles.colMeta}>Pending alignment</div>
            </div>
          </div>

          <div style={styles.conflictActionRow}>
            {activeConflict.conflicting_memory && (
              <button
                onClick={() => openCorrectionModal(activeConflict.conflicting_memory)}
                style={styles.correctActionBtn}
              >
                ✏️ Correct / Supersede Established Memory
              </button>
            )}
            <button
              onClick={() => setActiveConflict(null)}
              style={styles.dismissBtn}
            >
              Dismiss Alert
            </button>
          </div>
        </div>
      )}

      {/* Search Input Bar */}
      <div style={styles.searchBar}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Semantic search memories (e.g. 'dual officer approval', 'REST to GraphQL', 'PostgreSQL')..."
          style={styles.searchInput}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
        />
        <button onClick={() => handleSearch()} disabled={loading} style={styles.searchBtn}>
          {loading ? "Searching Hindsight..." : "🔍 Recall Memory"}
        </button>
      </div>

      {/* Memory Results Grid */}
      <div style={styles.resultsSection}>
        <div style={styles.resultsCount}>
          Found <strong>{results.length}</strong> memories in this bank
        </div>

        {results.length === 0 && !loading && (
          <div style={styles.emptyState}>No memories matched your query in this project bank.</div>
        )}

        <div style={styles.cardsGrid}>
          {results.map((item, idx) => (
            <MemoryCard
              key={item.id || idx}
              item={item}
              onCorrect={openCorrectionModal}
            />
          ))}
        </div>
      </div>

      {/* Retain Memory Modal */}
      {showRetainModal && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h3>Retain Memory into {activeProject.name}</h3>
            <p style={{ color: "#a1a1aa", fontSize: "13px", marginTop: "-6px" }}>
              OneContext will automatically run LLM conflict detection against existing policies.
            </p>
            <form onSubmit={handleRetain} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <textarea
                required
                rows={4}
                placeholder="State the decision, architecture standard, or lesson learned..."
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
                style={styles.modalInput}
              />
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                <div>
                  <label style={styles.fieldLabel}>Author Agent ID</label>
                  <input
                    type="text"
                    value={newAgentId}
                    onChange={(e) => setNewAgentId(e.target.value)}
                    placeholder="e.g. lead-architect, security-lead"
                    style={styles.modalInput}
                  />
                </div>
                <div>
                  <label style={styles.fieldLabel}>Source Category</label>
                  <select
                    value={newSource}
                    onChange={(e) => setNewSource(e.target.value)}
                    style={styles.modalInput}
                  >
                    <option value="architecture_decision">Architecture Decision</option>
                    <option value="compliance_rule">Compliance Rule</option>
                    <option value="incident_postmortem">Incident Postmortem</option>
                    <option value="convention">Convention</option>
                    <option value="note">General Note</option>
                  </select>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "12px" }}>
                <button type="button" onClick={() => setShowRetainModal(false)} style={styles.cancelBtn}>
                  Cancel
                </button>
                <button type="submit" disabled={retaining} style={styles.submitBtn}>
                  {retaining ? "Ingesting to Hindsight..." : "Retain Memory"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Correct Memory Modal */}
      {showCorrectModal && targetMemory && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h3 style={{ margin: "0 0 6px 0", color: "#f4f4f5" }}>
              Supersede & Correct Memory
            </h3>
            <p style={{ color: "#a1a1aa", fontSize: "13px", marginBottom: "16px" }}>
              A new memory will be retained with <code>supersedes</code> metadata pointing to Memory #{targetMemory.id.slice(0, 8)}.
              Subsequent queries will prioritize the updated policy.
            </p>

            <form onSubmit={handleCorrectSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div>
                <label style={styles.fieldLabel}>Original Established Decision (Superseded)</label>
                <div style={styles.readOnlyBox}>{targetMemory.text}</div>
              </div>

              <div>
                <label style={styles.fieldLabel}>New Corrective Policy / Decision *</label>
                <textarea
                  required
                  rows={4}
                  placeholder="State the new, active policy that supersedes the original..."
                  value={correctionText}
                  onChange={(e) => setCorrectionText(e.target.value)}
                  style={styles.modalInput}
                />
              </div>

              <div>
                <label style={styles.fieldLabel}>Reason for Correction / Context</label>
                <input
                  type="text"
                  placeholder="e.g. Reverted GraphQL due to edge cache invalidation issues"
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  style={styles.modalInput}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "12px" }}>
                <button type="button" onClick={() => setShowCorrectModal(false)} style={styles.cancelBtn}>
                  Cancel
                </button>
                <button type="submit" disabled={correcting} style={styles.submitBtn}>
                  {correcting ? "Saving Correction..." : "Save & Supersede Memory"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "16px",
  },
  title: {
    color: "#f4f4f5",
    fontSize: "26px",
    fontWeight: "800",
    margin: "0 0 6px 0",
  },
  desc: {
    color: "#a1a1aa",
    fontSize: "14px",
    margin: 0,
  },
  retainBtn: {
    backgroundColor: "#2563eb",
    color: "#ffffff",
    border: "none",
    borderRadius: "8px",
    padding: "10px 18px",
    fontWeight: "600",
    fontSize: "14px",
    cursor: "pointer",
  },
  successBox: {
    backgroundColor: "#14532d25",
    border: "1px solid #22c55e",
    color: "#86efac",
    padding: "12px 16px",
    borderRadius: "8px",
    fontSize: "14px",
  },
  errorBox: {
    backgroundColor: "#7f1d1d25",
    border: "1px solid #ef4444",
    color: "#fca5a5",
    padding: "12px 16px",
    borderRadius: "8px",
    fontSize: "14px",
  },
  conflictCard: {
    backgroundColor: "#291d14",
    border: "1px solid #f59e0b",
    borderRadius: "10px",
    padding: "20px",
    boxShadow: "0 4px 20px rgba(245, 158, 11, 0.15)",
  },
  conflictHeader: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginBottom: "10px",
  },
  conflictBadge: {
    backgroundColor: "#78350f",
    color: "#fef08a",
    fontSize: "12px",
    fontWeight: "700",
    padding: "3px 8px",
    borderRadius: "4px",
    textTransform: "uppercase",
  },
  conflictSubtitle: {
    color: "#fde68a",
    fontSize: "13px",
  },
  conflictExplanation: {
    color: "#fef3c7",
    fontSize: "14px",
    margin: "0 0 14px 0",
    lineHeight: "1.5",
  },
  conflictCompareGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "14px",
    marginBottom: "16px",
  },
  conflictColOld: {
    backgroundColor: "#18181b",
    border: "1px solid #3f3f46",
    borderRadius: "8px",
    padding: "12px",
  },
  conflictColNew: {
    backgroundColor: "#18181b",
    border: "1px solid #f59e0b80",
    borderRadius: "8px",
    padding: "12px",
  },
  colHeader: {
    fontSize: "11px",
    fontWeight: "700",
    color: "#a1a1aa",
    letterSpacing: "0.5px",
    marginBottom: "6px",
  },
  colBody: {
    color: "#e4e4e7",
    fontSize: "13px",
    lineHeight: "1.45",
    marginBottom: "8px",
  },
  colMeta: {
    fontSize: "11px",
    color: "#71717a",
  },
  conflictActionRow: {
    display: "flex",
    gap: "10px",
    justifyContent: "flex-end",
  },
  correctActionBtn: {
    backgroundColor: "#f59e0b",
    color: "#18181b",
    border: "none",
    borderRadius: "6px",
    padding: "8px 14px",
    fontSize: "13px",
    fontWeight: "700",
    cursor: "pointer",
  },
  dismissBtn: {
    backgroundColor: "transparent",
    color: "#a1a1aa",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "8px 14px",
    fontSize: "13px",
    cursor: "pointer",
  },
  searchBar: {
    display: "flex",
    gap: "10px",
  },
  searchInput: {
    flex: 1,
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    color: "#f4f4f5",
    padding: "12px 16px",
    borderRadius: "8px",
    fontSize: "14px",
    outline: "none",
  },
  searchBtn: {
    backgroundColor: "#27272a",
    border: "1px solid #3f3f46",
    color: "#f4f4f5",
    padding: "12px 20px",
    borderRadius: "8px",
    fontWeight: "600",
    cursor: "pointer",
  },
  resultsSection: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  resultsCount: {
    fontSize: "13px",
    color: "#71717a",
  },
  emptyState: {
    padding: "40px",
    textAlign: "center",
    color: "#71717a",
    backgroundColor: "#18181b",
    borderRadius: "10px",
    border: "1px dashed #27272a",
  },
  cardsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
    gap: "16px",
  },
  modalOverlay: {
    position: "fixed",
    inset: 0,
    backgroundColor: "rgba(0,0,0,0.75)",
    backdropFilter: "blur(4px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 100,
    padding: "20px",
  },
  modalContent: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "12px",
    padding: "24px",
    maxWidth: "540px",
    width: "100%",
  },
  modalInput: {
    width: "100%",
    backgroundColor: "#27272a",
    border: "1px solid #3f3f46",
    color: "#f4f4f5",
    padding: "10px 12px",
    borderRadius: "6px",
    fontSize: "14px",
    outline: "none",
    boxSizing: "border-box",
  },
  readOnlyBox: {
    backgroundColor: "#09090b",
    border: "1px solid #27272a",
    color: "#a1a1aa",
    padding: "10px 12px",
    borderRadius: "6px",
    fontSize: "13px",
    lineHeight: "1.45",
  },
  fieldLabel: {
    display: "block",
    fontSize: "12px",
    color: "#a1a1aa",
    marginBottom: "4px",
    fontWeight: "600",
  },
  cancelBtn: {
    backgroundColor: "transparent",
    border: "1px solid #3f3f46",
    color: "#d4d4d8",
    padding: "8px 16px",
    borderRadius: "6px",
    cursor: "pointer",
  },
  submitBtn: {
    backgroundColor: "#2563eb",
    border: "none",
    color: "#ffffff",
    padding: "8px 16px",
    borderRadius: "6px",
    fontWeight: "600",
    cursor: "pointer",
  },
};
