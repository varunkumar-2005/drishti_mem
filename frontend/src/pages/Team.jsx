import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  listProjects,
  createTeam,
  joinTeam,
  listTeamMembers,
  getRoomMembers,
  sendHeartbeat,
  sendTeamMessage,
  listTeamMessages,
  seedTeamDemo,
  generateTeamCode,
} from "../api/client";

// Starter active file templates
const INITIAL_FILES = {
  "auth/login_service.py": `"""
auth/login_service.py
Core authentication handler for OneContext users.
"""
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, status

TOKEN_ALGORITHM = "RS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
MFA_ENFORCED = False

def authenticate_user(credentials, db_session):
    """
    Standard login logic.
    All team members and agents follow this shared policy.
    """
    user = db_session.get_user(credentials.username)
    if not user or not user.verify_password(credentials.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials."
        )
    
    token = jwt.encode(
        {"sub": user.id, "role": user.role, "exp": datetime.now(timezone.utc) + timedelta(minutes=60)},
        key="PRIVATE_KEY_PEM",
        algorithm=TOKEN_ALGORITHM
    )
    return {"access_token": token, "token_type": "bearer"}
`,
  "models/user_session.py": `"""
models/user_session.py
Active session schema synced across all downstream services.
"""
from pydantic import BaseModel
from typing import Optional

class UserSession(BaseModel):
    user_id: str
    auth_method: str  # 'oauth2_jwt' or 'passkey'
    expires_at: str
    ip_hash: str
    mfa_verified: bool = True
`,
  "docs/ADR-008-auth-policy.md": `# ADR-008: Authentication Standards
- **Protocol**: OAuth2 Bearer with RS256 JWT
- **Expiration**: 15 minutes max lifetime (strictly enforced)
- **MFA**: Compulsory on all privileged and tenant-admin accounts
- **Forbidden**: Plain legacy session cookies on cross-origin API calls.
`,
};

export default function Team({ activeProject, setActiveProject, currentTeam, setCurrentTeam }) {
  const [projects, setProjects] = useState([]);
  const [loadingProjects, setLoadingProjects] = useState(false);

  // Setup / Switch Team state
  const [createName, setCreateName] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [lastCreatedCode, setLastCreatedCode] = useState(null);
  const [copied, setCopied] = useState(false);

  // Join state
  const [joinCode, setJoinCode] = useState("");
  const [displayName, setDisplayName] = useState("Varun");
  const [selectedRole, setSelectedRole] = useState("Lead Architect");
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState(null);

  // Active Team Room state
  const [members, setMembers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [retainAsMemory, setRetainAsMemory] = useState(false);
  const [sendingMsg, setSendingMsg] = useState(false);

  // IDE Editor state
  const [activeFileName, setActiveFileName] = useState("auth/login_service.py");
  const [codeFiles, setCodeFiles] = useState(INITIAL_FILES);
  const [aiPrompt, setAiPrompt] = useState("Update login logic to enforce 15-minute RS256 JWT tokens and mandate TOTP MFA");
  const [generatingCode, setGeneratingCode] = useState(false);
  const [generationStep, setGenerationStep] = useState("");
  const [agentVerdict, setAgentVerdict] = useState(null);

  const messagesEndRef = useRef(null);
  const navigate = useNavigate();

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  // Sync selectedProjectId with activeProject
  useEffect(() => {
    if (activeProject?.id) {
      setSelectedProjectId(activeProject.id);
    } else if (projects.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projects[0].id);
    }
  }, [activeProject, projects]);

  // Polling for live chat and members when inside a team room
  useEffect(() => {
    if (!currentTeam?.id) return;

    const user = displayName || localStorage.getItem("onecontext_user") || "Developer";
    sendHeartbeat(currentTeam.id, user).catch(() => {});

    fetchMembersAndMessages(currentTeam.id);
    const interval = setInterval(() => {
      sendHeartbeat(currentTeam.id, user).catch(() => {});
      fetchMembersAndMessages(currentTeam.id, true);
    }, 2000);

    return () => clearInterval(interval);
  }, [currentTeam, displayName]);

  // Auto scroll chat to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadProjects = async () => {
    setLoadingProjects(true);
    try {
      const data = await listProjects();
      setProjects(data);
      if (data.length > 0 && !selectedProjectId) {
        setSelectedProjectId(activeProject?.id || data[0].id);
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    } finally {
      setLoadingProjects(false);
    }
  };

  const fetchMembersAndMessages = async (teamId, silent = false) => {
    try {
      const [membersData, msgsData] = await Promise.all([
        getRoomMembers(teamId),
        listTeamMessages(teamId),
      ]);
      setMembers(membersData);
      setMessages(msgsData);
    } catch (err) {
      if (!silent) console.error("Error fetching room sync:", err);
    }
  };

  const handleCreateTeam = async (e) => {
    e.preventDefault();
    if (!createName.trim() || !selectedProjectId) return;
    setCreating(true);
    setCreateError(null);

    try {
      const newTeam = await createTeam({
        name: createName.trim(),
        project_id: selectedProjectId,
      });
      setLastCreatedCode(newTeam.join_code);
      if (setCurrentTeam) setCurrentTeam(newTeam);

      // Auto-join creator as initial member
      await joinTeam({
        join_code: newTeam.join_code,
        display_name: displayName || "Varun",
      });

      // Seed 4 teammates for immediate demo readiness
      await seedTeamDemo(newTeam.id);

      const targetProj = projects.find((p) => p.id === newTeam.project_id);
      if (targetProj && setActiveProject) {
        setActiveProject(targetProj);
      }

      fetchMembersAndMessages(newTeam.id);
    } catch (err) {
      setCreateError(err.response?.data?.detail || err.message || "Failed to create team room");
    } finally {
      setCreating(false);
    }
  };

  const handleJoinTeam = async (e) => {
    e.preventDefault();
    if (!joinCode.trim() || !displayName.trim()) return;
    setJoining(true);
    setJoinError(null);

    try {
      const res = await joinTeam({
        join_code: joinCode.trim().toUpperCase(),
        display_name: displayName.trim(),
      });

      if (setCurrentTeam) setCurrentTeam(res.team);

      // Ensure demo members are seeded
      await seedTeamDemo(res.team.id);

      const targetProj = projects.find((p) => p.id === res.project_id) || {
        id: res.project_id,
        name: res.team.name,
        bank_id: `onecontext-${res.project_id}`,
      };
      if (setActiveProject) {
        setActiveProject(targetProj);
      }

      fetchMembersAndMessages(res.team.id);
    } catch (err) {
      setJoinError(err.response?.data?.detail || err.message || "Invalid join code");
    } finally {
      setJoining(false);
    }
  };

  const handleSendMessage = async (e) => {
    e?.preventDefault();
    if (!chatInput.trim() || !currentTeam?.id) return;
    setSendingMsg(true);

    try {
      await sendTeamMessage(currentTeam.id, {
        sender: displayName || "Team Member",
        role: selectedRole || "developer",
        message: chatInput.trim(),
        message_type: retainAsMemory ? "decision" : "chat",
        retain_as_memory: retainAsMemory,
      });
      setChatInput("");
      setRetainAsMemory(false);
      fetchMembersAndMessages(currentTeam.id);
    } catch (err) {
      console.error("Failed to send message:", err);
    } finally {
      setSendingMsg(false);
    }
  };

  // REAL LLM AGENT CODE SYNTHESIS & GUARDRAIL EXECUTION
  const handleRunAgentCodeAction = async (overridePrompt = null) => {
    const promptToUse = overridePrompt || aiPrompt;
    if (!promptToUse.trim() || !currentTeam?.id) return;

    setGeneratingCode(true);
    setAgentVerdict(null);
    setGenerationStep("1. Recalling institutional memory rules from Hindsight bank...");

    try {
      // Step 2 simulation label
      setTimeout(() => {
        setGenerationStep("2. Groq LLM synthesizing new code with policy constraints...");
      }, 900);

      // Step 3 simulation label
      setTimeout(() => {
        setGenerationStep("3. Running Validator Agent to inspect draft against past ADRs...");
      }, 2200);

      const res = await generateTeamCode(currentTeam.id, {
        instruction: promptToUse.trim(),
        current_code: codeFiles[activeFileName],
        filename: activeFileName,
        author: displayName || "Alice (Auth Specialist)",
      });

      // Update actual code in editor!
      if (res.new_code) {
        setCodeFiles((prev) => ({
          ...prev,
          [activeFileName]: res.new_code,
        }));
      }

      setAgentVerdict(res);
      fetchMembersAndMessages(currentTeam.id);
    } catch (err) {
      console.error("Agent code action error:", err);
      setAgentVerdict({
        status: "error",
        explanation: err.response?.data?.detail || err.message || "Failed to execute agent code action.",
        validation: { valid: false, contradictions: ["API connection error"] },
      });
    } finally {
      setGeneratingCode(false);
      setGenerationStep("");
    }
  };

  const handleCopyCode = () => {
    const code = currentTeam?.join_code || lastCreatedCode;
    if (!code) return;
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // SETUP SCREEN: Create or Join
  if (!currentTeam) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <h1 style={styles.title}>Team Room & Vibe Coding Workspace</h1>
          <p style={styles.subtitle}>
            Connect 4 parallel team members to a unified institutional memory bank. Real-time chat, live code sync, and instant policy broadcasts.
          </p>
        </div>

        <div style={styles.setupGrid}>
          {/* Create Team Room */}
          <div style={styles.setupCard}>
            <h2 style={styles.cardTitle}>Create New Team Room</h2>
            <p style={styles.cardDesc}>Provisions an isolated team room with a 6-character code and pre-loaded 4-collaborator demo team.</p>
            {createError && <div style={styles.errorBox}>⚠️ {createError}</div>}

            <form onSubmit={handleCreateTeam} style={styles.form}>
              <div style={styles.field}>
                <label style={styles.label}>Team Room Name *</label>
                <input
                  type="text"
                  required
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  placeholder="e.g. Auth & Payments Squad"
                  style={styles.input}
                />
              </div>

              <div style={styles.field}>
                <label style={styles.label}>Associated Project *</label>
                <select
                  value={selectedProjectId}
                  onChange={(e) => setSelectedProjectId(e.target.value)}
                  style={styles.select}
                  disabled={loadingProjects || projects.length === 0}
                >
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.id})
                    </option>
                  ))}
                </select>
              </div>

              <div style={styles.field}>
                <label style={styles.label}>Your Display Name *</label>
                <input
                  type="text"
                  required
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g. Varun (Lead Architect)"
                  style={styles.input}
                />
              </div>

              <button type="submit" disabled={creating} style={styles.btnPrimary}>
                {creating ? "Setting up Team Workspace..." : "Create Team Room & Launch IDE"}
              </button>
            </form>
          </div>

          {/* Join With Code */}
          <div style={styles.setupCard}>
            <h2 style={styles.cardTitle}>Join Existing Room</h2>
            <p style={styles.cardDesc}>Enter a 6-character code to join your team's live session and sync the shared memory bank.</p>
            {joinError && <div style={styles.errorBox}>⚠️ {joinError}</div>}

            <form onSubmit={handleJoinTeam} style={styles.form}>
              <div style={styles.field}>
                <label style={styles.label}>6-Character Join Code *</label>
                <input
                  type="text"
                  required
                  maxLength={6}
                  value={joinCode}
                  onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                  placeholder="e.g. OCEIQG"
                  style={{ ...styles.input, textTransform: "uppercase", letterSpacing: "3px", fontWeight: "bold" }}
                />
              </div>

              <div style={styles.field}>
                <label style={styles.label}>Your Name *</label>
                <input
                  type="text"
                  required
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g. Alice (Security)"
                  style={styles.input}
                />
              </div>

              <div style={styles.field}>
                <label style={styles.label}>Your Role</label>
                <select
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value)}
                  style={styles.select}
                >
                  <option value="Lead Architect">Lead Architect</option>
                  <option value="Auth Specialist">Auth Specialist</option>
                  <option value="Backend Engineer">Backend Engineer</option>
                  <option value="Frontend Developer">Frontend Developer</option>
                </select>
              </div>

              <button type="submit" disabled={joining} style={styles.btnSuccess}>
                {joining ? "Joining Room..." : "Join Team Room"}
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  // ACTIVE TEAM ROOM: VS CODE STYLE LIVE COLLABORATIVE IDE
  return (
    <div style={styles.ideContainer}>
      {/* Top VS Code Window Bar */}
      <div style={styles.ideTopBar}>
        <div style={styles.ideTitleRow}>
          <span style={styles.windowDots}>
            <span style={{ ...styles.dot, backgroundColor: "#ef4444" }} />
            <span style={{ ...styles.dot, backgroundColor: "#eab308" }} />
            <span style={{ ...styles.dot, backgroundColor: "#22c55e" }} />
          </span>
          <span style={styles.repoName}>
            <strong>OneContext Live Workspace</strong> — Room: <em>{currentTeam.name}</em> (Bank: {currentTeam.project_id})
          </span>
          <div style={styles.joinCodePill}>
            <span>Join Code: <strong style={{ color: "#60a5fa", letterSpacing: "2px" }}>{currentTeam.join_code}</strong></span>
            <button onClick={handleCopyCode} style={styles.copySmallBtn}>
              {copied ? "✓ Copied" : "📋 Copy"}
            </button>
          </div>
        </div>

        {/* Active Collaborators Presence Bar */}
        <div style={styles.presenceBar}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <button onClick={() => navigate("/")} style={styles.backBtn}>
              ← Back to Room Feed
            </button>
            <span style={styles.presenceLabel}>
              ACTIVE TEAMMATES ({members.filter((m) => m.online).length} ONLINE):
            </span>
          </div>

          <div style={styles.avatarList}>
            {members.length === 0 ? (
              <span style={{ fontSize: "0.8rem", color: "#71717a" }}>Loading members...</span>
            ) : (
              members.map((m, idx) => {
                const isOnline = m.online;
                return (
                  <span
                    key={idx}
                    style={{
                      ...styles.avatarBadge,
                      borderColor: isOnline ? "#10b981" : "#3f3f46",
                      backgroundColor: isOnline ? "#064e3b33" : "#18181b",
                    }}
                  >
                    <span
                      style={{
                        ...styles.statusDot,
                        backgroundColor: isOnline ? "#10b981" : "#71717a",
                        boxShadow: isOnline ? "0 0 6px #10b981" : "none",
                      }}
                    />
                    👤 {m.display_name} {isOnline ? "(active)" : "(away)"}
                  </span>
                );
              })
            )}
            <span style={{ ...styles.avatarBadge, borderColor: "#6366f1", backgroundColor: "#1e1b4b33" }}>
              <span style={{ ...styles.statusDot, backgroundColor: "#6366f1" }} /> 🤖 Groq Vibe Agent
            </span>
          </div>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div style={styles.ideBody}>
        {/* Left Column: Code Editor & AI Synthesis */}
        <div style={styles.editorPane}>
          {/* File Tabs */}
          <div style={styles.fileTabs}>
            {Object.keys(codeFiles).map((fname) => (
              <button
                key={fname}
                onClick={() => setActiveFileName(fname)}
                style={{
                  ...styles.fileTab,
                  backgroundColor: activeFileName === fname ? "#1e1e24" : "#131316",
                  borderBottom: activeFileName === fname ? "2px solid #3b82f6" : "none",
                  color: activeFileName === fname ? "#ffffff" : "#71717a",
                }}
              >
                {fname.endsWith(".py") ? "🐍" : "📄"} {fname}
              </button>
            ))}
          </div>

          {/* REAL AI AGENT PROMPT & ACTION BAR */}
          <div style={styles.agentPromptBar}>
            <div style={styles.promptHeader}>
              <span style={styles.aiLabel}>⚡ AUTONOMOUS AGENT REWRITE (GROQ + HINDSIGHT):</span>
              <span style={styles.authorBadge}>Acting as: <strong>{displayName}</strong></span>
            </div>

            <div style={styles.promptInputRow}>
              <input
                type="text"
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                placeholder="Instruct the agent to rewrite logic (e.g. 'Enforce 15-minute RS256 JWT tokens with TOTP MFA')..."
                style={styles.aiInput}
                disabled={generatingCode}
              />
              <button
                onClick={() => handleRunAgentCodeAction()}
                disabled={generatingCode || !aiPrompt.trim()}
                style={styles.runAgentBtn}
              >
                {generatingCode ? "Agent Reasoning..." : "🚀 Synthesize & Validate"}
              </button>
            </div>

            {/* Quick Demo Action Presets that trigger real AI */}
            <div style={styles.presetRow}>
              <span style={{ fontSize: "0.72rem", color: "#a1a1aa" }}>One-Click AI Prompts:</span>
              <button
                onClick={() => {
                  setAiPrompt("Update login to strictly enforce 15-minute RS256 JWT tokens and mandate TOTP MFA");
                  handleRunAgentCodeAction("Update login to strictly enforce 15-minute RS256 JWT tokens and mandate TOTP MFA");
                }}
                style={styles.presetChipBlue}
                disabled={generatingCode}
              >
                1. 🔄 Enforce 15m JWT + TOTP
              </button>
              <button
                onClick={() => {
                  setAiPrompt("Add WebAuthn biometric passkey support and require MFA on all admin logins");
                  handleRunAgentCodeAction("Add WebAuthn biometric passkey support and require MFA on all admin logins");
                }}
                style={styles.presetChipGreen}
                disabled={generatingCode}
              >
                2. 🔐 WebAuthn Passkeys
              </button>
              <button
                onClick={() => {
                  setAiPrompt("Change authentication to store auth tokens in plain unencrypted cookies without expiration");
                  handleRunAgentCodeAction("Change authentication to store auth tokens in plain unencrypted cookies without expiration");
                }}
                style={styles.presetChipRed}
                disabled={generatingCode}
              >
                3. ⚠️ Propose Plain Cookies (Trigger Guardrail)
              </button>
            </div>
          </div>

          {/* Live Agent Reasoning Progress Drawer */}
          {generatingCode && (
            <div style={styles.thinkingDrawer}>
              <div style={styles.spinnerRow}>
                <span style={styles.pulseDot} />
                <strong style={{ color: "#60a5fa" }}>Autonomous Agent Reasoning:</strong>
                <span>{generationStep}</span>
              </div>
            </div>
          )}

          {/* Validator Agent Verdict Banner */}
          {agentVerdict && !generatingCode && (
            <div
              style={{
                ...styles.verdictBanner,
                backgroundColor: agentVerdict.validation?.valid ? "#064e3b" : "#7f1d1d",
                borderColor: agentVerdict.validation?.valid ? "#10b981" : "#ef4444",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>
                  {agentVerdict.validation?.valid ? "✅ VALIDATOR GUARDRAIL: PASSED (ZERO REGRESSIONS)" : "❌ VALIDATOR GUARDRAIL: CONTRADICTION DETECTED"}
                </span>
                <span style={{ fontSize: "0.75rem", opacity: 0.85 }}>Broadcasted to Team Chat & Memory</span>
              </div>
              <div style={{ fontSize: "0.8rem", marginTop: "4px", color: "#f4f4f5" }}>
                {agentVerdict.explanation}
              </div>
              {agentVerdict.validation?.contradictions?.length > 0 && (
                <div style={styles.contradictionList}>
                  {agentVerdict.validation.contradictions.map((c, i) => (
                    <div key={i}>⚠️ {c}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Code Text Area */}
          <div style={styles.codeEditorContainer}>
            <div style={styles.lineNumbers}>
              {Array.from({ length: 34 }).map((_, i) => (
                <div key={i}>{i + 1}</div>
              ))}
            </div>
            <textarea
              value={codeFiles[activeFileName]}
              onChange={(e) => {
                const val = e.target.value;
                setCodeFiles((prev) => ({ ...prev, [activeFileName]: val }));
              }}
              style={styles.codeArea}
              spellCheck={false}
            />
          </div>
        </div>

        {/* Right Column: Real-Time Team Chat & Knowledge Stream */}
        <div style={styles.chatPane}>
          <div style={styles.chatHeader}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "1.1rem" }}>💬</span>
              <strong style={{ fontSize: "0.95rem", color: "#fafafa" }}>Team War Room Chat</strong>
            </div>
            <span style={styles.liveBadge}>● LIVE SYNC</span>
          </div>

          <div style={styles.chatMessages}>
            {messages.length === 0 ? (
              <div style={styles.emptyChat}>
                No messages yet. Send a message or ask <code>@agent</code> to see team context in action!
              </div>
            ) : (
              messages.map((m) => {
                const isDecision = m.message_type === "decision" || m.message_type === "code_change";
                const isAgent = m.role === "agent" || m.sender.toLowerCase().includes("agent") || m.sender.toLowerCase().includes("copilot");

                return (
                  <div
                    key={m.id}
                    style={{
                      ...styles.chatBubble,
                      borderLeft: isDecision
                        ? "4px solid #10b981"
                        : isAgent
                        ? "4px solid #f59e0b"
                        : "4px solid #3b82f6",
                      backgroundColor: isDecision ? "#064e3b26" : isAgent ? "#451a0326" : "#18181b",
                    }}
                  >
                    <div style={styles.chatBubbleHeader}>
                      <span style={styles.senderName}>
                        {isAgent ? "🤖 " : isDecision ? "⚡ " : "👤 "}
                        <strong>{m.sender}</strong>
                        <span style={styles.roleTag}>({m.role})</span>
                      </span>
                      <span style={styles.chatTime}>
                        {new Date(m.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                      </span>
                    </div>

                    {isDecision && (
                      <div style={styles.memoryPill}>
                        🧠 INDEXED IN SHARED HINDSIGHT MEMORY
                      </div>
                    )}

                    <div style={styles.chatBodyText}>
                      {m.message}
                    </div>
                  </div>
                );
              })
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Chat Input Box */}
          <form onSubmit={handleSendMessage} style={styles.chatInputForm}>
            <div style={styles.chatOptionsRow}>
              <label style={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={retainAsMemory}
                  onChange={(e) => setRetainAsMemory(e.target.checked)}
                />
                <span style={{ color: retainAsMemory ? "#34d399" : "#a1a1aa" }}>
                  🧠 Retain as Project Memory Rule
                </span>
              </label>

              <button
                type="button"
                onClick={() => setChatInput((prev) => "@agent " + prev)}
                style={styles.atAgentBtn}
              >
                + @agent
              </button>
            </div>

            <div style={styles.inputRow}>
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder='Type message or "@agent What is our login policy?"...'
                style={styles.chatTextInput}
              />
              <button
                type="submit"
                disabled={sendingMsg || !chatInput.trim()}
                style={{
                  ...styles.sendBtn,
                  opacity: sendingMsg || !chatInput.trim() ? 0.5 : 1,
                }}
              >
                {sendingMsg ? "..." : "Send"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    maxWidth: "1000px",
    margin: "0 auto",
    padding: "32px 16px",
  },
  header: {
    marginBottom: "28px",
  },
  title: {
    fontSize: "1.8rem",
    fontWeight: "700",
    color: "#f4f4f5",
    margin: "0 0 8px 0",
  },
  subtitle: {
    fontSize: "0.95rem",
    color: "#a1a1aa",
    margin: 0,
    lineHeight: "1.5",
  },
  setupGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: "24px",
  },
  setupCard: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "8px",
    padding: "24px",
  },
  cardTitle: {
    fontSize: "1.2rem",
    fontWeight: "600",
    color: "#fafafa",
    margin: "0 0 6px 0",
  },
  cardDesc: {
    fontSize: "0.85rem",
    color: "#a1a1aa",
    margin: "0 0 18px 0",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  label: {
    fontSize: "0.85rem",
    fontWeight: "500",
    color: "#d4d4d8",
  },
  input: {
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "10px 12px",
    color: "#fafafa",
    fontSize: "0.9rem",
    outline: "none",
  },
  select: {
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "10px 12px",
    color: "#fafafa",
    fontSize: "0.9rem",
    outline: "none",
  },
  btnPrimary: {
    backgroundColor: "#3b82f6",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    padding: "10px 16px",
    fontSize: "0.9rem",
    fontWeight: "600",
    cursor: "pointer",
    marginTop: "8px",
  },
  btnSuccess: {
    backgroundColor: "#10b981",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    padding: "10px 16px",
    fontSize: "0.9rem",
    fontWeight: "600",
    cursor: "pointer",
    marginTop: "8px",
  },
  errorBox: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid #ef4444",
    borderRadius: "6px",
    padding: "10px 14px",
    color: "#fca5a5",
    fontSize: "0.85rem",
    marginBottom: "14px",
  },

  // IDE STYLES
  ideContainer: {
    display: "flex",
    flexDirection: "column",
    height: "calc(100vh - 65px)",
    backgroundColor: "#0f0f13",
    color: "#f4f4f5",
  },
  ideTopBar: {
    backgroundColor: "#18181f",
    borderBottom: "1px solid #27272f",
    padding: "8px 16px",
  },
  ideTitleRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: "6px",
  },
  windowDots: {
    display: "flex",
    gap: "6px",
  },
  dot: {
    width: "11px",
    height: "11px",
    borderRadius: "50%",
    display: "inline-block",
  },
  repoName: {
    fontSize: "0.85rem",
    color: "#d4d4d8",
  },
  joinCodePill: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "20px",
    padding: "4px 12px",
    fontSize: "0.8rem",
  },
  copySmallBtn: {
    backgroundColor: "#27272a",
    border: "1px solid #52525b",
    borderRadius: "4px",
    color: "#fafafa",
    padding: "2px 8px",
    fontSize: "0.75rem",
    cursor: "pointer",
  },
  backBtn: {
    backgroundColor: "#18181b",
    border: "1px solid #3f3f46",
    color: "#f4f4f5",
    padding: "4px 10px",
    borderRadius: "6px",
    fontSize: "0.78rem",
    fontWeight: "600",
    cursor: "pointer",
    transition: "background 0.15s ease",
  },
  presenceBar: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    flexWrap: "wrap",
    paddingTop: "6px",
    borderTop: "1px solid #27272f",
  },
  presenceLabel: {
    fontSize: "0.75rem",
    color: "#a1a1aa",
    fontWeight: "700",
    letterSpacing: "0.5px",
  },
  avatarList: {
    display: "flex",
    gap: "10px",
    flexWrap: "wrap",
  },
  avatarBadge: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    backgroundColor: "#121217",
    border: "1px solid #3f3f46",
    borderRadius: "16px",
    padding: "3px 10px",
    fontSize: "0.75rem",
    fontWeight: "600",
  },
  statusDot: {
    width: "7px",
    height: "7px",
    borderRadius: "50%",
    backgroundColor: "#22c55e",
    display: "inline-block",
  },

  ideBody: {
    display: "flex",
    flex: 1,
    overflow: "hidden",
  },

  // Editor Left/Center Pane
  editorPane: {
    flex: "1 1 60%",
    display: "flex",
    flexDirection: "column",
    borderRight: "1px solid #27272f",
    backgroundColor: "#121216",
    overflow: "hidden",
  },
  fileTabs: {
    display: "flex",
    backgroundColor: "#09090c",
    borderBottom: "1px solid #27272f",
    overflowX: "auto",
  },
  fileTab: {
    padding: "8px 16px",
    border: "none",
    borderRight: "1px solid #27272f",
    fontSize: "0.8rem",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  agentPromptBar: {
    backgroundColor: "#171720",
    borderBottom: "1px solid #27272f",
    padding: "10px 14px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  promptHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  aiLabel: {
    fontSize: "0.75rem",
    fontWeight: "800",
    color: "#60a5fa",
    letterSpacing: "0.5px",
  },
  authorBadge: {
    fontSize: "0.72rem",
    color: "#a1a1aa",
  },
  promptInputRow: {
    display: "flex",
    gap: "8px",
  },
  aiInput: {
    flex: 1,
    backgroundColor: "#09090b",
    border: "1px solid #3b82f6",
    borderRadius: "6px",
    padding: "8px 12px",
    color: "#fafafa",
    fontSize: "0.85rem",
    outline: "none",
  },
  runAgentBtn: {
    backgroundColor: "#3b82f6",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    padding: "8px 16px",
    fontSize: "0.85rem",
    fontWeight: "700",
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  presetRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flexWrap: "wrap",
  },
  presetChipBlue: {
    backgroundColor: "#1e3a8a",
    color: "#93c5fd",
    border: "1px solid #2563eb",
    borderRadius: "4px",
    padding: "3px 8px",
    fontSize: "0.72rem",
    cursor: "pointer",
  },
  presetChipGreen: {
    backgroundColor: "#064e3b",
    color: "#6ee7b7",
    border: "1px solid #059669",
    borderRadius: "4px",
    padding: "3px 8px",
    fontSize: "0.72rem",
    cursor: "pointer",
  },
  presetChipRed: {
    backgroundColor: "#7f1d1d",
    color: "#fca5a5",
    border: "1px solid #dc2626",
    borderRadius: "4px",
    padding: "3px 8px",
    fontSize: "0.72rem",
    cursor: "pointer",
  },
  thinkingDrawer: {
    backgroundColor: "#1e293b",
    borderBottom: "1px solid #38bdf8",
    padding: "8px 14px",
    fontSize: "0.8rem",
  },
  spinnerRow: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },
  pulseDot: {
    width: "10px",
    height: "10px",
    borderRadius: "50%",
    backgroundColor: "#38bdf8",
    display: "inline-block",
  },
  verdictBanner: {
    padding: "10px 14px",
    borderBottom: "2px solid",
    fontWeight: "600",
  },
  contradictionList: {
    marginTop: "6px",
    fontSize: "0.75rem",
    color: "#fecaca",
    display: "flex",
    flexDirection: "column",
    gap: "2px",
  },
  codeEditorContainer: {
    display: "flex",
    flex: 1,
    overflow: "hidden",
  },
  lineNumbers: {
    width: "40px",
    backgroundColor: "#0e0e12",
    color: "#52525b",
    padding: "12px 6px",
    textAlign: "right",
    fontSize: "0.85rem",
    fontFamily: "monospace",
    lineHeight: "1.5",
    userSelect: "none",
    borderRight: "1px solid #27272f",
  },
  codeArea: {
    flex: 1,
    backgroundColor: "#121216",
    color: "#e4e4e7",
    padding: "12px 14px",
    fontSize: "0.85rem",
    fontFamily: "'Fira Code', 'Cascadia Code', Consolas, Monaco, monospace",
    lineHeight: "1.5",
    border: "none",
    outline: "none",
    resize: "none",
    overflowY: "auto",
  },

  // Chat Right Pane
  chatPane: {
    flex: "1 1 40%",
    maxWidth: "460px",
    display: "flex",
    flexDirection: "column",
    backgroundColor: "#16161b",
  },
  chatHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "12px 16px",
    backgroundColor: "#1a1a22",
    borderBottom: "1px solid #27272f",
  },
  liveBadge: {
    backgroundColor: "#065f46",
    color: "#34d399",
    padding: "2px 8px",
    borderRadius: "10px",
    fontSize: "0.7rem",
    fontWeight: "700",
    letterSpacing: "0.5px",
  },
  chatMessages: {
    flex: 1,
    overflowY: "auto",
    padding: "14px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  emptyChat: {
    color: "#71717a",
    fontSize: "0.85rem",
    textAlign: "center",
    marginTop: "24px",
    fontStyle: "italic",
  },
  chatBubble: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "6px",
    padding: "10px 12px",
  },
  chatBubbleHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "4px",
  },
  senderName: {
    fontSize: "0.82rem",
    color: "#f4f4f5",
  },
  roleTag: {
    fontSize: "0.72rem",
    color: "#a1a1aa",
    marginLeft: "4px",
  },
  chatTime: {
    fontSize: "0.7rem",
    color: "#71717a",
  },
  memoryPill: {
    display: "inline-block",
    backgroundColor: "#065f46",
    color: "#6ee7b7",
    fontSize: "0.68rem",
    fontWeight: "700",
    padding: "2px 6px",
    borderRadius: "4px",
    marginBottom: "6px",
    letterSpacing: "0.5px",
  },
  chatBodyText: {
    fontSize: "0.82rem",
    color: "#e4e4e7",
    lineHeight: "1.45",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  chatInputForm: {
    padding: "12px",
    backgroundColor: "#1a1a22",
    borderTop: "1px solid #27272f",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  chatOptionsRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  checkboxLabel: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    fontSize: "0.75rem",
    cursor: "pointer",
  },
  atAgentBtn: {
    backgroundColor: "#27272a",
    border: "1px solid #3f3f46",
    color: "#60a5fa",
    padding: "2px 8px",
    borderRadius: "4px",
    fontSize: "0.75rem",
    cursor: "pointer",
  },
  inputRow: {
    display: "flex",
    gap: "8px",
  },
  chatTextInput: {
    flex: 1,
    backgroundColor: "#09090b",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "8px 12px",
    color: "#fafafa",
    fontSize: "0.85rem",
    outline: "none",
  },
  sendBtn: {
    backgroundColor: "#3b82f6",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    padding: "8px 14px",
    fontSize: "0.85rem",
    fontWeight: "600",
    cursor: "pointer",
  },
};
