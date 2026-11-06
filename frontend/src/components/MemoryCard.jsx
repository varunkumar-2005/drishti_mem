import React, { useState } from "react";

export default function MemoryCard({ item }) {
  const [expanded, setExpanded] = useState(false);
  const text = item.text || "";
  const isLong = text.length > 140;
  const author = item.agent_id || item.metadata?.agent_id || "general";
  const source = item.source || item.metadata?.source || "note";
  const type = item.type || "memory";

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div style={styles.badges}>
          <span style={styles.authorBadge}>🤖 {author}</span>
          <span style={styles.sourceBadge}>{source}</span>
          {type && <span style={styles.typeBadge}>{type}</span>}
        </div>
        {item.score !== undefined && item.score !== null && (
          <span style={styles.scoreBadge}>
            {(item.score * 100).toFixed(0)}% match
          </span>
        )}
      </div>

      <div style={styles.content}>
        {expanded || !isLong ? text : `${text.slice(0, 140)}...`}
      </div>

      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          style={styles.expandBtn}
        >
          {expanded ? "Show less" : "Read full memory"}
        </button>
      )}

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
  timestamp: {
    fontSize: "11px",
    color: "#71717a",
    marginTop: "4px",
  },
};
