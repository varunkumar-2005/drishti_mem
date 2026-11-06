import React, { useEffect, useState } from "react";
import { getAudit } from "../api/client";

export default function SearchHistory({ activeProject }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (activeProject?.id) {
      loadAudit();
    }
  }, [activeProject]);

  const loadAudit = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAudit(activeProject.id, 60);
      setEntries(data || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const getActionBadge = (action) => {
    switch (action) {
      case "retain":
        return <span style={{ ...styles.badge, backgroundColor: "#1e3a8a", color: "#60a5fa" }}>RETAIN</span>;
      case "recall":
        return <span style={{ ...styles.badge, backgroundColor: "#14532d", color: "#4ade80" }}>RECALL</span>;
      case "ask":
        return <span style={{ ...styles.badge, backgroundColor: "#581c87", color: "#c084fc" }}>ASK</span>;
      case "validate":
        return <span style={{ ...styles.badge, backgroundColor: "#7c2d12", color: "#fb923c" }}>VALIDATE</span>;
      default:
        return <span style={styles.badge}>{action.toUpperCase()}</span>;
    }
  };

  if (!activeProject) {
    return <div style={{ color: "#a1a1aa", padding: "40px" }}>Please select an active project first.</div>;
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Memory Audit Trail</h1>
          <p style={styles.desc}>
            Chronological log of memory operations for <strong>{activeProject.name}</strong> ({activeProject.id})
          </p>
        </div>
        <button onClick={loadAudit} disabled={loading} style={styles.refreshBtn}>
          🔄 Refresh Log
        </button>
      </div>

      {error && <div style={styles.errorBox}>⚠️ {error}</div>}

      <div style={styles.tableContainer}>
        <table style={styles.table}>
          <thead>
            <tr style={styles.thRow}>
              <th style={styles.th}>Timestamp</th>
              <th style={styles.th}>Action</th>
              <th style={styles.th}>Agent ID</th>
              <th style={styles.th}>Query / Retained Content</th>
              <th style={styles.th}>Matches</th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 && !loading && (
              <tr>
                <td colSpan={5} style={styles.emptyTd}>
                  No audit log entries recorded yet.
                </td>
              </tr>
            )}
            {entries.map((entry) => (
              <tr key={entry.id} style={styles.tr}>
                <td style={styles.tdTime}>
                  {new Date(entry.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                </td>
                <td style={styles.tdAction}>{getActionBadge(entry.action)}</td>
                <td style={styles.tdAgent}>🤖 {entry.agent_id}</td>
                <td style={styles.tdQuery}>
                  <div style={styles.queryContent}>{entry.query_or_text || "—"}</div>
                </td>
                <td style={styles.tdCount}>{entry.result_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
  refreshBtn: {
    backgroundColor: "#18181b",
    color: "#e4e4e7",
    border: "1px solid #3f3f46",
    borderRadius: "8px",
    padding: "8px 16px",
    fontSize: "13px",
    cursor: "pointer",
  },
  errorBox: {
    backgroundColor: "#7f1d1d40",
    color: "#fca5a5",
    padding: "12px",
    borderRadius: "8px",
    border: "1px solid #ef444450",
  },
  tableContainer: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "14px",
    overflow: "hidden",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    textAlign: "left",
  },
  thRow: {
    backgroundColor: "#09090b",
    borderBottom: "1px solid #27272a",
  },
  th: {
    padding: "14px 18px",
    color: "#a1a1aa",
    fontSize: "12px",
    fontWeight: "700",
    letterSpacing: "0.5px",
    textTransform: "uppercase",
  },
  tr: {
    borderBottom: "1px solid #27272a",
  },
  tdTime: {
    padding: "14px 18px",
    color: "#71717a",
    fontSize: "13px",
    whiteSpace: "nowrap",
  },
  tdAction: {
    padding: "14px 18px",
  },
  badge: {
    padding: "4px 8px",
    borderRadius: "4px",
    fontSize: "11px",
    fontWeight: "700",
    letterSpacing: "0.5px",
  },
  tdAgent: {
    padding: "14px 18px",
    color: "#38bdf8",
    fontSize: "13px",
    fontWeight: "600",
    whiteSpace: "nowrap",
  },
  tdQuery: {
    padding: "14px 18px",
    color: "#e4e4e7",
    fontSize: "13px",
  },
  queryContent: {
    maxWidth: "500px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  tdCount: {
    padding: "14px 18px",
    color: "#fbbf24",
    fontSize: "13px",
    fontWeight: "600",
  },
  emptyTd: {
    padding: "40px",
    textAlign: "center",
    color: "#71717a",
    fontSize: "14px",
  },
};
