import React, { useEffect, useState } from "react";
import { recallMemory, retainMemory } from "../api/client";
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

  useEffect(() => {
    if (activeProject?.id) {
      handleSearch("architecture decisions");
    }
  }, [activeProject]);

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
      await retainMemory(activeProject.id, {
        text: newText,
        source: newSource,
        agent_id: newAgentId,
      });
      setShowRetainModal(false);
      setNewText("");
      setSuccessMsg("Memory successfully retained into Hindsight bank!");
      setTimeout(() => setSuccessMsg(null), 4000);
      handleSearch(newText.slice(0, 40));
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setRetaining(false);
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

      {/* Search Input Bar */}
      <div style={styles.searchBar}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Semantic search memories (e.g. 'dual officer approval', 'connection pool', 'PostgreSQL')..."
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
            <MemoryCard key={item.id || idx} item={item} />
          ))}
        </div>
      </div>

      {/* Retain Memory Modal */}
      {showRetainModal && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h3>Retain Memory into {activeProject.name}</h3>
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
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: "28px",
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
    fontSize: "13px",
    fontWeight: "600",
    cursor: "pointer",
  },
  successBox: {
    backgroundColor: "#14532d30",
    color: "#4ade80",
    border: "1px solid #22c55e40",
    padding: "12px",
    borderRadius: "8px",
    fontSize: "14px",
  },
  errorBox: {
    backgroundColor: "#7f1d1d40",
    color: "#fca5a5",
    padding: "12px",
    borderRadius: "8px",
    border: "1px solid #ef444450",
  },
  searchBar: {
    display: "flex",
    gap: "12px",
  },
  searchInput: {
    flex: 1,
    backgroundColor: "#18181b",
    border: "1px solid #3f3f46",
    borderRadius: "8px",
    padding: "12px 16px",
    color: "#f4f4f5",
    fontSize: "14px",
    outline: "none",
  },
  searchBtn: {
    backgroundColor: "#2563eb",
    color: "#ffffff",
    border: "none",
    borderRadius: "8px",
    padding: "12px 24px",
    fontWeight: "600",
    cursor: "pointer",
  },
  resultsSection: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  resultsCount: {
    color: "#a1a1aa",
    fontSize: "13px",
  },
  cardsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
    gap: "18px",
  },
  emptyState: {
    color: "#71717a",
    textAlign: "center",
    padding: "40px",
    backgroundColor: "#18181b",
    borderRadius: "10px",
  },
  modalOverlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.75)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 1000,
  },
  modalContent: {
    backgroundColor: "#18181b",
    border: "1px solid #3f3f46",
    borderRadius: "14px",
    padding: "24px",
    width: "550px",
    color: "#f4f4f5",
  },
  modalInput: {
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "8px",
    padding: "10px 12px",
    color: "#f4f4f5",
    fontSize: "14px",
    outline: "none",
    width: "100%",
    boxSizing: "border-box",
  },
  fieldLabel: {
    color: "#a1a1aa",
    fontSize: "11px",
    fontWeight: "600",
    display: "block",
    marginBottom: "4px",
  },
  cancelBtn: {
    backgroundColor: "transparent",
    color: "#a1a1aa",
    border: "1px solid #3f3f46",
    borderRadius: "8px",
    padding: "8px 16px",
    cursor: "pointer",
  },
  submitBtn: {
    backgroundColor: "#2563eb",
    color: "#ffffff",
    border: "none",
    borderRadius: "8px",
    padding: "8px 20px",
    fontWeight: "600",
    cursor: "pointer",
  },
};
