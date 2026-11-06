import React, { useEffect, useState } from "react";
import { listAgents, registerAgent, runAgent, validateDraft } from "../api/client";
import MemoryCard from "../components/MemoryCard";

export default function Agents({ activeProject }) {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [taskInput, setTaskInput] = useState("");
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [validationResult, setValidationResult] = useState(null);

  // New agent form state
  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState("Planner");
  const [showNewModal, setShowNewModal] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (activeProject?.id) {
      loadAgents();
    }
  }, [activeProject]);

  const loadAgents = async () => {
    try {
      const list = await listAgents(activeProject.id);
      setAgents(list);
      if (list.length > 0 && !selectedAgent) {
        setSelectedAgent(list[0].id);
      }
    } catch (err) {
      console.error("Failed to load agents", err);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    if (!newName) return;
    try {
      await registerAgent(activeProject.id, {
        id: newId || undefined,
        name: newName,
        role: newRole,
      });
      setShowNewModal(false);
      setNewId("");
      setNewName("");
      loadAgents();
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
  };

  const handleRunTask = async () => {
    if (!taskInput.trim() || !selectedAgent) return;
    setRunning(true);
    setError(null);
    setRunResult(null);
    setValidationResult(null);

    const isValidator = selectedAgent.toLowerCase().includes("validator");

    try {
      if (isValidator) {
        const valRes = await validateDraft(activeProject.id, { draft: taskInput });
        setValidationResult(valRes);
      } else {
        const res = await runAgent(activeProject.id, selectedAgent, { task: taskInput });
        setRunResult(res);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setRunning(false);
    }
  };

  if (!activeProject) {
    return <div style={{ color: "#a1a1aa", padding: "40px" }}>Please select an active project first.</div>;
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Multi-Agent Console</h1>
          <p style={styles.desc}>
            Registered agents for <strong>{activeProject.name}</strong>. All agents collaborate over the same Hindsight
            memory bank without manual context handoffs.
          </p>
        </div>
        <button onClick={() => setShowNewModal(true)} style={styles.addBtn}>
          + Register New Agent
        </button>
      </div>

      {error && <div style={styles.errorBox}>⚠️ {error}</div>}

      {/* Agents Roster */}
      <div style={styles.rosterGrid}>
        {agents.map((a) => (
          <div
            key={a.id}
            onClick={() => setSelectedAgent(a.id)}
            style={{
              ...styles.agentCard,
              borderColor: selectedAgent === a.id ? "#3b82f6" : "#27272a",
              backgroundColor: selectedAgent === a.id ? "#1e293b" : "#18181b",
            }}
          >
            <div style={styles.agentAvatar}>🤖</div>
            <div>
              <div style={styles.agentName}>{a.name}</div>
              <div style={styles.agentRole}>{a.role || "General"}</div>
              <div style={styles.agentIdTag}>{a.id}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Interactive Execution Console */}
      <div style={styles.consoleBox}>
        <h3 style={styles.consoleTitle}>
          Run Task with: <span style={{ color: "#60a5fa" }}>{selectedAgent || "Select Agent"}</span>
        </h3>

        <div style={styles.taskForm}>
          <textarea
            value={taskInput}
            onChange={(e) => setTaskInput(e.target.value)}
            placeholder={
              selectedAgent.toLowerCase().includes("validator")
                ? "Paste a PR description or architectural claim to validate against memory..."
                : selectedAgent.toLowerCase().includes("planner")
                ? "Enter architecture requirement (e.g. 'Standardize caching strategy')..."
                : "Enter implementation task (e.g. 'Implement User authentication repository')..."
            }
            rows={3}
            style={styles.taskInput}
          />
          <button onClick={handleRunTask} disabled={running} style={styles.runBtn}>
            {running ? "Agent Running..." : "Execute Task"}
          </button>
        </div>

        {/* Validator Results */}
        {validationResult && (
          <div
            style={{
              ...styles.resultBox,
              borderLeft: validationResult.valid ? "4px solid #22c55e" : "4px solid #ef4444",
            }}
          >
            <div style={styles.valHeader}>
              <span
                style={{
                  ...styles.valStatus,
                  backgroundColor: validationResult.valid ? "#14532d" : "#7f1d1d",
                  color: validationResult.valid ? "#4ade80" : "#f87171",
                }}
              >
                {validationResult.valid ? "VALID (COMPLIANT)" : "INVALID (CONTRADICTION DETECTED)"}
              </span>
            </div>

            {validationResult.contradictions?.length > 0 && (
              <div style={styles.contradictionsList}>
                <strong>Contradictions Caught:</strong>
                <ul>
                  {validationResult.contradictions.map((c, i) => (
                    <li key={i} style={{ color: "#fca5a5" }}>
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div style={styles.outputText}>
              <strong>Analysis:</strong> {validationResult.analysis}
            </div>

            {validationResult.citations?.length > 0 && (
              <div style={styles.sourcesSection}>
                <div style={styles.sourcesHeading}>Citations from Memory:</div>
                {validationResult.citations.map((c, i) => (
                  <MemoryCard key={c.id || i} item={c} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Planner / Builder Output */}
        {runResult && (
          <div style={styles.resultBox}>
            <div style={styles.resultHeader}>
              <span>Role: <strong>{runResult.role}</strong></span>
              <span>Project: <strong>{runResult.project_id}</strong></span>
            </div>

            <div style={styles.outputText}>{runResult.output}</div>

            {runResult.memories_retained?.length > 0 && (
              <div style={styles.retainedBanner}>
                ✅ Stored into Hindsight: <strong>{runResult.memories_retained.join(", ")}</strong>
              </div>
            )}

            {runResult.memories_recalled?.length > 0 && (
              <div style={styles.sourcesSection}>
                <div style={styles.sourcesHeading}>
                  Memories Recalled by Agent ({runResult.memories_recalled.length}):
                </div>
                {runResult.memories_recalled.map((m, i) => (
                  <MemoryCard key={m.id || i} item={m} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modal to Register Agent */}
      {showNewModal && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h3>Register Agent for {activeProject.name}</h3>
            <form onSubmit={handleRegister} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <input
                type="text"
                placeholder="Agent ID (e.g. security-lead, coder-two)"
                value={newId}
                onChange={(e) => setNewId(e.target.value)}
                style={styles.modalInput}
              />
              <input
                type="text"
                required
                placeholder="Display Name (e.g. Chief Security Officer)"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                style={styles.modalInput}
              />
              <select value={newRole} onChange={(e) => setNewRole(e.target.value)} style={styles.modalInput}>
                <option value="Planner">Planner / Architect</option>
                <option value="Builder">Builder / Coder</option>
                <option value="Validator">Validator / QA</option>
                <option value="Specialist">Domain Specialist</option>
              </select>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
                <button type="button" onClick={() => setShowNewModal(false)} style={styles.cancelBtn}>
                  Cancel
                </button>
                <button type="submit" style={styles.submitBtn}>
                  Register Agent
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
  addBtn: {
    backgroundColor: "#2563eb",
    color: "#ffffff",
    border: "none",
    borderRadius: "8px",
    padding: "10px 18px",
    fontSize: "13px",
    fontWeight: "600",
    cursor: "pointer",
  },
  errorBox: {
    backgroundColor: "#7f1d1d40",
    color: "#fca5a5",
    padding: "12px",
    borderRadius: "8px",
    border: "1px solid #ef444450",
  },
  rosterGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
    gap: "14px",
  },
  agentCard: {
    border: "1px solid",
    borderRadius: "10px",
    padding: "14px",
    display: "flex",
    alignItems: "center",
    gap: "12px",
    cursor: "pointer",
    transition: "all 0.15s ease",
  },
  agentAvatar: {
    fontSize: "24px",
  },
  agentName: {
    color: "#f4f4f5",
    fontSize: "14px",
    fontWeight: "600",
  },
  agentRole: {
    color: "#a1a1aa",
    fontSize: "12px",
  },
  agentIdTag: {
    color: "#60a5fa",
    fontSize: "11px",
    marginTop: "2px",
  },
  consoleBox: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "14px",
    padding: "24px",
    display: "flex",
    flexDirection: "column",
    gap: "18px",
  },
  consoleTitle: {
    color: "#f4f4f5",
    fontSize: "18px",
    fontWeight: "700",
    margin: 0,
  },
  taskForm: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  taskInput: {
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "8px",
    padding: "12px 16px",
    color: "#f4f4f5",
    fontSize: "14px",
    outline: "none",
    resize: "vertical",
  },
  runBtn: {
    alignSelf: "flex-end",
    backgroundColor: "#2563eb",
    color: "#ffffff",
    border: "none",
    borderRadius: "8px",
    padding: "10px 22px",
    fontWeight: "600",
    cursor: "pointer",
  },
  resultBox: {
    backgroundColor: "#09090b",
    border: "1px solid #27272a",
    borderRadius: "10px",
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  resultHeader: {
    display: "flex",
    justifyContent: "space-between",
    color: "#a1a1aa",
    fontSize: "12px",
    paddingBottom: "8px",
    borderBottom: "1px solid #27272a",
  },
  valHeader: {
    marginBottom: "4px",
  },
  valStatus: {
    display: "inline-block",
    padding: "4px 10px",
    borderRadius: "4px",
    fontSize: "12px",
    fontWeight: "700",
    letterSpacing: "0.5px",
  },
  contradictionsList: {
    backgroundColor: "#7f1d1d20",
    border: "1px solid #ef444430",
    padding: "12px 16px",
    borderRadius: "8px",
    fontSize: "13px",
  },
  outputText: {
    color: "#e4e4e7",
    fontSize: "14px",
    lineHeight: "1.6",
    whiteSpace: "pre-wrap",
  },
  retainedBanner: {
    backgroundColor: "#14532d30",
    color: "#4ade80",
    border: "1px solid #22c55e40",
    padding: "10px 14px",
    borderRadius: "6px",
    fontSize: "13px",
  },
  sourcesSection: {
    marginTop: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  sourcesHeading: {
    fontSize: "12px",
    fontWeight: "700",
    color: "#38bdf8",
    textTransform: "uppercase",
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
    borderRadius: "12px",
    padding: "24px",
    width: "400px",
    color: "#f4f4f5",
  },
  modalInput: {
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "10px 12px",
    color: "#f4f4f5",
    fontSize: "14px",
    outline: "none",
  },
  cancelBtn: {
    backgroundColor: "transparent",
    color: "#a1a1aa",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "8px 14px",
    cursor: "pointer",
  },
  submitBtn: {
    backgroundColor: "#2563eb",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    padding: "8px 16px",
    fontWeight: "600",
    cursor: "pointer",
  },
};
