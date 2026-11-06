import React, { useState } from "react";
import { askMemory, askWithoutMemory } from "../api/client";
import MemoryCard from "./MemoryCard";

const SAMPLE_QUESTIONS = [
  "What approval is needed for a $15,000 transfer?",
  "Which database engine and primary key convention do we standardize on?",
  "What was the lesson from the database connection pool exhaustion incident?",
  "Why did we choose RabbitMQ over Kafka?",
];

export default function BeforeAfterPanel({ projectId }) {
  const [question, setQuestion] = useState(SAMPLE_QUESTIONS[0]);
  const [loading, setLoading] = useState(false);
  const [withMemResult, setWithMemResult] = useState(null);
  const [noMemResult, setNoMemResult] = useState(null);
  const [error, setError] = useState(null);

  const handleRunComparison = async (qToAsk = question) => {
    if (!projectId) {
      setError("Please select or create an active project first.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [withMem, withoutMem] = await Promise.all([
        askMemory(projectId, { question: qToAsk, agent_id: "demo-auditor" }),
        askWithoutMemory(projectId, { question: qToAsk, agent_id: "demo-auditor" }),
      ]);
      setWithMemResult(withMem);
      setNoMemResult(withoutMem);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to run comparison");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.badge}>DEMO CENTERPIECE</div>
        <h2 style={styles.title}>The Before / After Comparison</h2>
        <p style={styles.subtitle}>
          Compare an LLM answering <strong>without project memory</strong> against the same question answered using{" "}
          <strong>OneContext + Hindsight shared memory</strong>.
        </p>
      </div>

      <div style={styles.inputArea}>
        <div style={styles.inputRow}>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a technical or architectural question..."
            style={styles.input}
            onKeyDown={(e) => e.key === "Enter" && handleRunComparison()}
          />
          <button
            onClick={() => handleRunComparison()}
            disabled={loading}
            style={styles.runBtn}
          >
            {loading ? "Recalling & Comparing..." : "⚡ Run Comparison"}
          </button>
        </div>

        <div style={styles.samplesRow}>
          <span style={styles.sampleLabel}>Try preset:</span>
          {SAMPLE_QUESTIONS.map((q, idx) => (
            <button
              key={idx}
              onClick={() => {
                setQuestion(q);
                handleRunComparison(q);
              }}
              style={styles.samplePill}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {error && <div style={styles.errorBox}>⚠️ {error}</div>}

      {/* Comparison Grid */}
      <div style={styles.grid}>
        {/* Left: Without Memory */}
        <div style={styles.columnNoMem}>
          <div style={styles.colHeader}>
            <div style={styles.colBadgeNo}>BEFORE</div>
            <h3 style={styles.colTitle}>Without Memory</h3>
            <span style={styles.colDesc}>Generic AI Guesswork & Hallucination</span>
          </div>

          <div style={styles.answerBox}>
            {noMemResult ? (
              <>
                <div style={styles.metaBar}>
                  <span>Model: <strong>{noMemResult.model_used}</strong></span>
                  <span style={styles.noSourcesTag}>0 Sources Found</span>
                </div>
                <div style={styles.answerText}>{noMemResult.answer}</div>
              </>
            ) : (
              <div style={styles.placeholder}>
                Click <strong>Run Comparison</strong> to generate the unassisted answer.
              </div>
            )}
          </div>
        </div>

        {/* Right: With OneContext Memory */}
        <div style={styles.columnWithMem}>
          <div style={styles.colHeader}>
            <div style={styles.colBadgeYes}>AFTER</div>
            <h3 style={styles.colTitle}>With OneContext Memory</h3>
            <span style={styles.colDesc}>Grounded via Hindsight & Dual Verification</span>
          </div>

          <div style={styles.answerBox}>
            {withMemResult ? (
              <>
                <div style={styles.metaBar}>
                  <span>Model: <strong>{withMemResult.model_used}</strong></span>
                  <span style={styles.sourcesCountBadge}>
                    🎯 {withMemResult.sources?.length || 0} Recalled Sources Cited
                  </span>
                </div>
                <div style={styles.groundedAnswerText}>{withMemResult.answer}</div>

                {withMemResult.sources?.length > 0 && (
                  <div style={styles.sourcesSection}>
                    <div style={styles.sourcesHeading}>Recalled Hindsight Memory Sources:</div>
                    <div style={styles.sourcesGrid}>
                      {withMemResult.sources.map((src, i) => (
                        <MemoryCard key={src.id || i} item={src} />
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div style={styles.placeholder}>
                Click <strong>Run Comparison</strong> to see grounded memory in action.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
    width: "100%",
  },
  header: {
    textAlign: "center",
  },
  badge: {
    display: "inline-block",
    backgroundColor: "#3b82f620",
    color: "#60a5fa",
    border: "1px solid #3b82f640",
    padding: "4px 12px",
    borderRadius: "20px",
    fontSize: "11px",
    fontWeight: "700",
    letterSpacing: "1px",
    marginBottom: "8px",
  },
  title: {
    color: "#f4f4f5",
    fontSize: "28px",
    fontWeight: "800",
    margin: "0 0 8px 0",
  },
  subtitle: {
    color: "#a1a1aa",
    fontSize: "15px",
    maxWidth: "700px",
    margin: "0 auto",
    lineHeight: "1.5",
  },
  inputArea: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    padding: "18px",
    borderRadius: "14px",
  },
  inputRow: {
    display: "flex",
    gap: "12px",
  },
  input: {
    flex: 1,
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "8px",
    padding: "12px 16px",
    color: "#f4f4f5",
    fontSize: "15px",
    outline: "none",
  },
  runBtn: {
    backgroundColor: "#2563eb",
    color: "#ffffff",
    border: "none",
    borderRadius: "8px",
    padding: "12px 24px",
    fontSize: "15px",
    fontWeight: "600",
    cursor: "pointer",
    transition: "background 0.2s",
  },
  samplesRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flexWrap: "wrap",
  },
  sampleLabel: {
    fontSize: "12px",
    color: "#71717a",
  },
  samplePill: {
    backgroundColor: "#27272a",
    color: "#d4d4d8",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "4px 10px",
    fontSize: "12px",
    cursor: "pointer",
  },
  errorBox: {
    backgroundColor: "#7f1d1d40",
    color: "#fca5a5",
    padding: "12px",
    borderRadius: "8px",
    border: "1px solid #ef444450",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "24px",
  },
  columnNoMem: {
    backgroundColor: "#18181b",
    border: "1px solid #ef444440",
    borderRadius: "14px",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
  },
  columnWithMem: {
    backgroundColor: "#18181b",
    border: "1px solid #22c55e50",
    borderRadius: "14px",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
  },
  colHeader: {
    padding: "16px 20px",
    borderBottom: "1px solid #27272a",
    backgroundColor: "#09090b80",
  },
  colBadgeNo: {
    display: "inline-block",
    backgroundColor: "#ef444420",
    color: "#ef4444",
    padding: "2px 8px",
    borderRadius: "4px",
    fontSize: "10px",
    fontWeight: "700",
    marginBottom: "4px",
  },
  colBadgeYes: {
    display: "inline-block",
    backgroundColor: "#22c55e20",
    color: "#22c55e",
    padding: "2px 8px",
    borderRadius: "4px",
    fontSize: "10px",
    fontWeight: "700",
    marginBottom: "4px",
  },
  colTitle: {
    color: "#f4f4f5",
    fontSize: "18px",
    fontWeight: "700",
    margin: "0 0 2px 0",
  },
  colDesc: {
    fontSize: "12px",
    color: "#71717a",
  },
  answerBox: {
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "14px",
    flex: 1,
  },
  metaBar: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "12px",
    color: "#a1a1aa",
    paddingBottom: "8px",
    borderBottom: "1px solid #27272a",
  },
  noSourcesTag: {
    color: "#ef4444",
    fontWeight: "600",
  },
  sourcesCountBadge: {
    color: "#4ade80",
    fontWeight: "600",
  },
  answerText: {
    color: "#d4d4d8",
    fontSize: "14px",
    lineHeight: "1.6",
    whiteSpace: "pre-wrap",
  },
  groundedAnswerText: {
    color: "#f4f4f5",
    fontSize: "14px",
    lineHeight: "1.65",
    whiteSpace: "pre-wrap",
    fontWeight: "400",
  },
  sourcesSection: {
    marginTop: "16px",
    paddingTop: "14px",
    borderTop: "1px solid #27272a",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  sourcesHeading: {
    fontSize: "12px",
    fontWeight: "700",
    color: "#4ade80",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  sourcesGrid: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  placeholder: {
    color: "#71717a",
    textAlign: "center",
    padding: "40px 20px",
    fontSize: "14px",
  },
};
