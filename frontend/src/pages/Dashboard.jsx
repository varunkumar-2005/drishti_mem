import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listProjects, getHealth } from "../api/client";
import BeforeAfterPanel from "../components/BeforeAfterPanel";

export default function Dashboard({ activeProject, setActiveProject }) {
  const [projects, setProjects] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [projList, healthStatus] = await Promise.all([
        listProjects(),
        getHealth().catch(() => ({ status: "offline", hindsight: "offline", groq: "offline" })),
      ]);
      setProjects(projList);
      setHealth(healthStatus);
      if (projList.length > 0 && !activeProject) {
        // Default to seeded project 'apexpay-core' if present, otherwise first
        const defaultProj = projList.find((p) => p.id === "apexpay-core") || projList[0];
        setActiveProject(defaultProj);
      }
    } catch (err) {
      console.error("Failed to load dashboard data", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      {/* Top Banner & Project Selector */}
      <div style={styles.topBar}>
        <div>
          <h1 style={styles.heading}>OneContext Dashboard</h1>
          <p style={styles.subheading}>One Project. One Long-Term Memory. Every Agent.</p>
        </div>

        <div style={styles.projectSelectorBox}>
          <label style={styles.label}>Active Memory Bank:</label>
          <select
            value={activeProject?.id || ""}
            onChange={(e) => {
              const selected = projects.find((p) => p.id === e.target.value);
              setActiveProject(selected);
            }}
            style={styles.select}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.id})
              </option>
            ))}
          </select>
          <Link to="/projects/new" style={styles.newBtn}>
            + New Project
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <div style={styles.metricsGrid}>
        <div style={styles.metricCard}>
          <div style={styles.metricLabel}>ACTIVE PROJECT</div>
          <div style={styles.metricValue}>{activeProject ? activeProject.name : "None"}</div>
          <div style={styles.metricSub}>Bank ID: {activeProject?.bank_id || "N/A"}</div>
        </div>

        <div style={styles.metricCard}>
          <div style={styles.metricLabel}>HINDSIGHT CLOUD</div>
          <div style={{ ...styles.metricValue, color: "#4ade80" }}>
            {health?.hindsight === "connected" ? "Connected" : "Disconnected"}
          </div>
          <div style={styles.metricSub}>Vectorize Multi-Strategy Memory</div>
        </div>

        <div style={styles.metricCard}>
          <div style={styles.metricLabel}>GROQ INFERENCE</div>
          <div style={{ ...styles.metricValue, color: "#38bdf8" }}>
            {health?.groq === "connected" ? "openai/gpt-oss-120b" : "Offline"}
          </div>
          <div style={styles.metricSub}>Fallback: qwen/qwen3.8-27b</div>
        </div>

        <div style={styles.metricCard}>
          <div style={styles.metricLabel}>TOTAL PROJECTS</div>
          <div style={styles.metricValue}>{projects.length}</div>
          <div style={styles.metricSub}>Isolated Memory Banks</div>
        </div>
      </div>

      {/* Quick Navigation Cards */}
      <div style={styles.navCardsRow}>
        <Link to="/memory" style={styles.navCard}>
          <div style={styles.navCardTitle}>🔍 Memory Explorer</div>
          <div style={styles.navCardDesc}>Search recalled decisions and retain new facts with metadata.</div>
        </Link>
        <Link to="/agents" style={styles.navCard}>
          <div style={styles.navCardTitle}>🤖 Multi-Agent Console</div>
          <div style={styles.navCardDesc}>Planner, Builder, and Validator agents sharing project context.</div>
        </Link>
        <Link to="/history" style={styles.navCard}>
          <div style={styles.navCardTitle}>📜 Audit Trail</div>
          <div style={styles.navCardDesc}>Chronological log of every retain, recall, and validation action.</div>
        </Link>
      </div>

      {/* Before / After Demo Centerpiece */}
      <div style={styles.demoSection}>
        <BeforeAfterPanel projectId={activeProject?.id} />
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: "32px",
  },
  topBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "16px",
    borderBottom: "1px solid #27272a",
    paddingBottom: "24px",
  },
  heading: {
    color: "#f4f4f5",
    fontSize: "32px",
    fontWeight: "800",
    margin: "0 0 6px 0",
  },
  subheading: {
    color: "#a1a1aa",
    fontSize: "15px",
    margin: "0",
  },
  projectSelectorBox: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    padding: "8px 14px",
    borderRadius: "10px",
  },
  label: {
    color: "#71717a",
    fontSize: "13px",
    fontWeight: "600",
  },
  select: {
    backgroundColor: "#09090b",
    color: "#f4f4f5",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "8px 12px",
    fontSize: "14px",
    cursor: "pointer",
  },
  newBtn: {
    backgroundColor: "#2563eb",
    color: "#ffffff",
    textDecoration: "none",
    padding: "8px 14px",
    borderRadius: "6px",
    fontSize: "13px",
    fontWeight: "600",
  },
  metricsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: "18px",
  },
  metricCard: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "12px",
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  metricLabel: {
    color: "#71717a",
    fontSize: "11px",
    fontWeight: "700",
    letterSpacing: "0.5px",
  },
  metricValue: {
    color: "#f4f4f5",
    fontSize: "20px",
    fontWeight: "700",
  },
  metricSub: {
    color: "#a1a1aa",
    fontSize: "12px",
  },
  navCardsRow: {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: "18px",
  },
  navCard: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "12px",
    padding: "20px",
    textDecoration: "none",
    transition: "border 0.2s",
  },
  navCardTitle: {
    color: "#f4f4f5",
    fontSize: "16px",
    fontWeight: "700",
    marginBottom: "6px",
  },
  navCardDesc: {
    color: "#a1a1aa",
    fontSize: "13px",
    lineHeight: "1.4",
  },
  demoSection: {
    backgroundColor: "#0f0f12",
    border: "1px solid #27272a",
    borderRadius: "16px",
    padding: "32px",
  },
};
