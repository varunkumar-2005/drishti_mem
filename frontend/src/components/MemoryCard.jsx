import React, { useState } from "react";

export default function MemoryCard({ item, onCorrect }) {
  const [expanded, setExpanded] = useState(false);
  const text = item.text || "";
  const isLong = text.length > 140;
  const author = item.agent_id || item.metadata?.agent_id || "general";
  const source = item.source || item.metadata?.source || "note";
  const type = item.type || "memory";
  const isSuperseded = item.is_superseded;
  const supersedes = item.supersedes || item.metadata?.supersedes;

  return (
    <div style={{ ...styles.card, opacity: isSuperseded ? 0.7 : 1, border: isSuperseded ? "1px dashed #ef4444" : "1px solid #2e2e38" }}>
      <div style={styles.header}>
        <div style={styles.badges}>
          <span style={styles.authorBadge}>🤖 {author}</span>
          <span style={styles.sourceBadge}>{source}</span>
          {type && <span style={styles.typeBadge}>{type}</span>}
          {isSuperseded && (
            <span style={styles.supersededBadge}>⛔ Superseded</span>
          )}
          {supersedes && (
            <span style={styles.correctiveBadge}>🔄 Corrective Update</span>
          )}
        </div>
        {item.score !== undefined && item.score !== null && (
          <span style={styles.scoreBadge}>
            Score: {Number(item.score).toFixed(2)}
          </span>
        )}
      </div>

      <div style={styles.content}>
        {expanded || !isLong ? text : `${text.slice(0, 140)}...`}
      </div>

      <div style={styles.footerRow}>
        {isLong && (
          <button
            onClick={() => setExpanded(!expanded)}
            style={styles.expandBtn}
          >
            {expanded ? "Show less" : "Read full memory"}
          </button>
        )}

        {onCorrect && !isSuperseded && (
          <button
            onClick={() => onCorrect(item)}
            style={styles.correctBtn}
            title="Supersede and correct this decision"
          >
            ✏️ Correct this memory
          </button>
        )}
      </div>

      {item.timestamp && (
        <div style={styles.timestamp}>
          📅 {new Date(item.timestamp).toLocaleString()}
        </div>
      )}
    </div>
  );
}

const styles = {
  card: {
    backgroundColor: "#1e1e24",
    border: "1px solid #2e2e38",
    borderRadius: "10px",
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "8px",
  },
  badges: {
    display: "flex",
    gap: "6px",
    flexWrap: "wrap",
  },
  authorBadge: {
    backgroundColor: "#2a2b36",
    color: "#60a5fa",
    fontSize: "12px",
    fontWeight: "600",
    padding: "3px 8px",
    borderRadius: "6px",
    border: "1px solid #3b82f640",
  },
  sourceBadge: {
    backgroundColor: "#27272a",
    color: "#a1a1aa",
    fontSize: "11px",
    padding: "3px 8px",
    borderRadius: "6px",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  typeBadge: {
    backgroundColor: "#14532d30",
    color: "#4ade80",
    fontSize: "11px",
    padding: "3px 8px",
    borderRadius: "6px",
  },
  supersededBadge: {
    backgroundColor: "#ef444420",
    color: "#f87171",
    fontSize: "11px",
    padding: "3px 8px",
    borderRadius: "6px",
    border: "1px solid #ef444440",
    fontWeight: "600",
  },
  correctiveBadge: {
    backgroundColor: "#3b82f620",
    color: "#60a5fa",
    fontSize: "11px",
    padding: "3px 8px",
    borderRadius: "6px",
    border: "1px solid #3b82f640",
  },
  scoreBadge: {
    fontSize: "11px",
    color: "#fbbf24",
    backgroundColor: "#78350f30",
    padding: "2px 6px",
    borderRadius: "4px",
  },
  content: {
    color: "#e4e4e7",
    fontSize: "14px",
    lineHeight: "1.55",
    whiteSpace: "pre-wrap",
  },
  footerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: "4px",
  },
  expandBtn: {
    alignSelf: "flex-start",
    background: "none",
    border: "none",
    color: "#38bdf8",
    fontSize: "12px",
    cursor: "pointer",
    padding: "0",
    textDecoration: "underline",
  },
  correctBtn: {
    background: "#27272a",
    border: "1px solid #3f3f46",
    color: "#a1a1aa",
    fontSize: "11px",
    padding: "3px 8px",
    borderRadius: "6px",
    cursor: "pointer",
    transition: "all 0.15s ease",
  },
  timestamp: {
    fontSize: "11px",
    color: "#71717a",
    marginTop: "4px",
  },
};
