import React, { useState } from "react";
import { askMemory } from "../api/client";
import MemoryCard from "./MemoryCard";

export default function ChatBox({ projectId }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I am your OneContext Project Assistant. Ask me anything about project architecture, compliance rules, incident post-mortems, or technical standards.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading || !projectId) return;

    const userQ = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userQ }]);
    setLoading(true);

    try {
      const res = await askMemory(projectId, { question: userQ, agent_id: "chat-user" });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.answer,
          sources: res.sources,
          model_used: res.model_used,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ Error answering query: ${err.response?.data?.detail || err.message}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.chatContainer}>
      <div style={styles.messagesList}>
        {messages.map((m, i) => (
          <div
            key={i}
            style={m.role === "user" ? styles.userRow : styles.assistantRow}
          >
            <div style={m.role === "user" ? styles.userBubble : styles.assistantBubble}>
              <div style={styles.bubbleText}>{m.content}</div>

              {m.model_used && (
                <div style={styles.modelTag}>Generated with {m.model_used}</div>
              )}

              {m.sources?.length > 0 && (
                <div style={styles.sourcesContainer}>
                  <div style={styles.sourcesTitle}>
                    CITED {m.sources.length} MEMORY {m.sources.length === 1 ? "SOURCE" : "SOURCES"}:
                  </div>
                  {m.sources.map((s, idx) => (
                    <MemoryCard key={s.id || idx} item={s} />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div style={styles.assistantRow}>
            <div style={styles.assistantBubble}>
              <span style={styles.thinking}>🧠 Recalling Hindsight memory & synthesizing answer...</span>
            </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSend} style={styles.inputForm}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about this project's decisions..."
          style={styles.chatInput}
          disabled={loading}
        />
        <button type="submit" disabled={loading} style={styles.sendBtn}>
          Send
        </button>
      </form>
    </div>
  );
}

const styles = {
  chatContainer: {
    display: "flex",
    flexDirection: "column",
    height: "550px",
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "14px",
    overflow: "hidden",
  },
  messagesList: {
    flex: 1,
    overflowY: "auto",
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
  },
  userRow: {
    display: "flex",
    justifyContent: "flex-end",
  },
  assistantRow: {
    display: "flex",
    justifyContent: "flex-start",
  },
  userBubble: {
    backgroundColor: "#2563eb",
    color: "#ffffff",
    padding: "12px 18px",
    borderRadius: "18px 18px 4px 18px",
    maxWidth: "80%",
    fontSize: "14px",
    lineHeight: "1.5",
  },
  assistantBubble: {
    backgroundColor: "#27272a",
    color: "#f4f4f5",
    padding: "14px 18px",
    borderRadius: "18px 18px 18px 4px",
    maxWidth: "85%",
    fontSize: "14px",
    lineHeight: "1.55",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  bubbleText: {
    whiteSpace: "pre-wrap",
  },
  modelTag: {
    fontSize: "11px",
    color: "#a1a1aa",
    borderTop: "1px solid #3f3f46",
    paddingTop: "6px",
  },
  sourcesContainer: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    marginTop: "8px",
    borderTop: "1px solid #3f3f46",
    paddingTop: "8px",
  },
  sourcesTitle: {
    fontSize: "11px",
    fontWeight: "700",
    color: "#4ade80",
  },
  thinking: {
    color: "#38bdf8",
    fontSize: "13px",
    fontStyle: "italic",
  },
  inputForm: {
    display: "flex",
    padding: "14px 20px",
    backgroundColor: "#09090b",
    borderTop: "1px solid #27272a",
    gap: "10px",
  },
  chatInput: {
    flex: 1,
    backgroundColor: "#18181b",
    border: "1px solid #3f3f46",
    borderRadius: "8px",
    padding: "10px 14px",
    color: "#f4f4f5",
    fontSize: "14px",
    outline: "none",
  },
  sendBtn: {
    backgroundColor: "#2563eb",
    color: "#ffffff",
    border: "none",
    borderRadius: "8px",
    padding: "10px 20px",
    fontWeight: "600",
    cursor: "pointer",
  },
};
