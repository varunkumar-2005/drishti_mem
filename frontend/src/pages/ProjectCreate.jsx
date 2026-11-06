import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createProject } from "../api/client";

export default function ProjectCreate({ setActiveProject }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const proj = await createProject({ name, description });
      setActiveProject(proj);
      navigate("/memory");
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to create project");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>Create New Project Memory Bank</h1>
      <p style={styles.desc}>
        Every project in OneContext gets an isolated Hindsight memory bank. All agents assigned to this project
        share, query, and enforce the same institutional memory.
      </p>

      {error && <div style={styles.errorBox}>⚠️ {error}</div>}

      <form onSubmit={handleSubmit} style={styles.form}>
        <div style={styles.field}>
          <label style={styles.label}>Project Name *</label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Risk Engine Microservice, Crypto Custody Platform"
            style={styles.input}
          />
        </div>

        <div style={styles.field}>
          <label style={styles.label}>Mission / Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the technical domain and mission for the memory bank..."
            rows={4}
            style={styles.textarea}
          />
        </div>

        <div style={styles.actions}>
          <button type="button" onClick={() => navigate("/")} style={styles.cancelBtn}>
            Cancel
          </button>
          <button type="submit" disabled={loading} style={styles.submitBtn}>
            {loading ? "Provisioning Bank in Hindsight..." : "Create Project Memory Bank"}
          </button>
        </div>
      </form>
    </div>
  );
}

const styles = {
  container: {
    maxWidth: "600px",
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    gap: "18px",
  },
  title: {
    color: "#f4f4f5",
    fontSize: "26px",
    fontWeight: "800",
    margin: 0,
  },
  desc: {
    color: "#a1a1aa",
    fontSize: "14px",
    lineHeight: "1.5",
    margin: 0,
  },
  errorBox: {
    backgroundColor: "#7f1d1d40",
    color: "#fca5a5",
    padding: "12px",
    borderRadius: "8px",
    border: "1px solid #ef444450",
  },
  form: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "14px",
    padding: "24px",
    display: "flex",
    flexDirection: "column",
    gap: "18px",
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  label: {
    color: "#d4d4d8",
    fontSize: "13px",
    fontWeight: "600",
  },
  input: {
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "8px",
    padding: "10px 14px",
    color: "#f4f4f5",
    fontSize: "14px",
    outline: "none",
  },
  textarea: {
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "8px",
    padding: "10px 14px",
    color: "#f4f4f5",
    fontSize: "14px",
    outline: "none",
    resize: "vertical",
  },
  actions: {
    display: "flex",
    justifyContent: "flex-end",
    gap: "12px",
    marginTop: "8px",
  },
  cancelBtn: {
    backgroundColor: "transparent",
    color: "#a1a1aa",
    border: "1px solid #3f3f46",
    borderRadius: "8px",
    padding: "10px 18px",
    cursor: "pointer",
  },
  submitBtn: {
    backgroundColor: "#2563eb",
    color: "#ffffff",
    border: "none",
    borderRadius: "8px",
    padding: "10px 22px",
    fontWeight: "600",
    cursor: "pointer",
  },
};
