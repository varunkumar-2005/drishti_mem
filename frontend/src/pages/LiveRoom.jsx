/**
 * frontend/src/pages/LiveRoom.jsx
 * Unified OneContext Live Team Room experience:
 * A. Landing screen: Create Room or Join with Code
 * B. 3-Column Live Room:
 *    - Left: Room details, 6-char Join Code, Live Member Presence, GitHub Sync
 *    - Center: Live Context Feed (SSE + Polling), Filter Row, Conflict Cards
 *    - Right: 3 Tabs (Catch Me Up, Context Pack, Add to Memory)
 */

import React, { useState, useEffect, useRef } from "react";
import {
  createTeam,
  joinTeam,
  listProjects,
  createProject,
  getRoomEvents,
  getRoomMembers,
  sendHeartbeat,
  catchUpRoom,
  configureGitHub,
  getGitHubConfig,
  syncGitHub,
  getContextPack,
  ingestText,
  ingestFile,
  captureDecision,
  correctMemory,
  BASE_URL,
} from "../api/client";

function formatRelativeTime(dateStr) {
  if (!dateStr) return "recently";
  try {
    const dt = new Date(dateStr);
    const diff = (Date.now() - dt.getTime()) / 1000;
    if (diff < 15) return "just now";
    if (diff < 60) return `${Math.floor(diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch {
    return dateStr;
  }
}

export default function LiveRoom({
  currentTeam,
  setCurrentTeam,
  activeProject,
  setActiveProject,
  currentUser,
  setCurrentUser,
  connectionStatus,
  setConnectionStatus,
}) {
  // --- Landing Screen State ---
  const [projects, setProjects] = useState([]);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [createName, setCreateName] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [githubRepoInput, setGithubRepoInput] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [creatingRoom, setCreatingRoom] = useState(false);
  const [joinCodeInput, setJoinCodeInput] = useState("");
  const [joinNameInput, setJoinNameInput] = useState("");
  const [joiningRoom, setJoiningRoom] = useState(false);
  const [landingError, setLandingError] = useState(null);

  // --- Live Room State ---
  const [events, setEvents] = useState([]);
  const [newEventIds, setNewEventIds] = useState(new Set());
  const [members, setMembers] = useState([]);
  const [activeFilter, setActiveFilter] = useState("all");
  const [githubConfig, setGithubConfig] = useState(null);
  const [syncingGithub, setSyncingGithub] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);

  // --- Right Panel State ---
  const [rightTab, setRightTab] = useState("catchup"); // "catchup" | "pack" | "add"

  // Catch me up state
  const [catchupSummary, setCatchupSummary] = useState(null);
  const [catchupEvents, setCatchupEvents] = useState([]);
  const [loadingCatchup, setLoadingCatchup] = useState(false);

  // Context pack state
  const [packTask, setPackTask] = useState("");
  const [packTarget, setPackTarget] = useState("chatgpt");
  const [packMaxChars, setPackMaxChars] = useState(3000);
  const [packResult, setPackResult] = useState(null);
  const [generatingPack, setGeneratingPack] = useState(false);
  const [copiedPack, setCopiedPack] = useState(false);

  // Add to memory state
  const [memText, setMemText] = useState("");
  const [memType, setMemType] = useState("decision"); // "decision" | "document" | "note"
  const [memSourceName, setMemSourceName] = useState("");
  const [capturingMem, setCapturingMem] = useState(false);
  const [captureFeedback, setCaptureFeedback] = useState(null);
  const [selectedUploadFile, setSelectedUploadFile] = useState(null);
  const [uploadingFile, setUploadingFile] = useState(false);

  // Correction Modal State (for conflict cards)
  const [correctingEvent, setCorrectingEvent] = useState(null);
  const [correctText, setCorrectText] = useState("");
  const [correctReason, setCorrectReason] = useState("");
  const [submittingCorrection, setSubmittingCorrection] = useState(false);

  // Refs for polling & SSE
  const sseRef = useRef(null);
  const pollIntervalRef = useRef(null);
  const heartbeatIntervalRef = useRef(null);

  // 1. Initial Load of Projects on Mount
  useEffect(() => {
    loadProjectsList();
  }, []);

  const loadProjectsList = async () => {
    setLoadingProjects(true);
    try {
      const data = await listProjects();
      setProjects(data);
      if (data.length > 0 && !selectedProjectId) {
        setSelectedProjectId(data[0].id);
      }
    } catch (err) {
      console.error("Failed to fetch projects:", err);
    } finally {
      setLoadingProjects(false);
    }
  };

  // 2. Room Event Streaming & Polling Setup
  useEffect(() => {
    if (!currentTeam?.id) {
      if (sseRef.current) {
        sseRef.current.close();
        sseRef.current = null;
      }
      clearInterval(pollIntervalRef.current);
      clearInterval(heartbeatIntervalRef.current);
      return;
    }

    // Initial fetch of events, members, and github config
    fetchInitialRoomData(currentTeam.id);

    // Setup SSE connection
    setupEventStream(currentTeam.id);

    // Setup heartbeat interval (every 20s)
    const displayName = currentUser || "Teammate";
    sendHeartbeat(currentTeam.id, displayName).catch(() => {});
    heartbeatIntervalRef.current = setInterval(() => {
      sendHeartbeat(currentTeam.id, displayName)
        .then(() => fetchRoomMembers(currentTeam.id))
        .catch(() => {});
    }, 20000);

    return () => {
      if (sseRef.current) {
        sseRef.current.close();
        sseRef.current = null;
      }
      clearInterval(pollIntervalRef.current);
      clearInterval(heartbeatIntervalRef.current);
    };
  }, [currentTeam?.id, currentUser]);

  const fetchInitialRoomData = async (teamId) => {
    try {
      const [evts, mems] = await Promise.all([
        getRoomEvents(teamId),
        getRoomMembers(teamId),
      ]);
      setEvents(evts);
      setMembers(mems);
      if (currentTeam?.project_id) {
        const gh = await getGitHubConfig(currentTeam.project_id);
        setGithubConfig(gh);
      }
    } catch (err) {
      console.error("Error loading room data:", err);
    }
  };

  const fetchRoomMembers = async (teamId) => {
    try {
      const mems = await getRoomMembers(teamId);
      setMembers(mems);
    } catch (err) {
      console.error("Error refreshing members:", err);
    }
  };

  // Setup Server-Sent Events with Polling Fallback
  const setupEventStream = (teamId) => {
    const sseUrl = `${BASE_URL}/rooms/${teamId}/stream`;

    try {
      const es = new EventSource(sseUrl);
      sseRef.current = es;

      es.onopen = () => {
        setConnectionStatus("live");
        clearInterval(pollIntervalRef.current);
      };

      es.addEventListener("room_event", (e) => {
        try {
          const newEvent = JSON.parse(e.data);
          handleIncomingEvent(newEvent);
        } catch (err) {
          console.error("Error parsing SSE event:", err);
        }
      });

      es.onerror = () => {
        setConnectionStatus("reconnecting");
        es.close();
        sseRef.current = null;

        // Fallback to polling /events every 5 seconds
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = setInterval(() => {
          pollEvents(teamId);
        }, 5000);
      };
    } catch (err) {
      console.warn("EventSource setup failed, falling back to polling:", err);
      setConnectionStatus("reconnecting");
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = setInterval(() => {
        pollEvents(teamId);
      }, 5000);
    }
  };

  const pollEvents = async (teamId) => {
    try {
      const latest = await getRoomEvents(teamId, null);
      setConnectionStatus("live");
      setEvents((prev) => {
        const existingIds = new Set(prev.map((e) => e.id));
        const added = latest.filter((e) => !existingIds.has(e.id));
        if (added.length > 0) {
          const addedIds = new Set(added.map((e) => e.id));
          setNewEventIds(addedIds);
          setTimeout(() => setNewEventIds(new Set()), 4000);
          return [...added, ...prev];
        }
        return latest;
      });
    } catch (err) {
      setConnectionStatus("reconnecting");
    }
  };

  const handleIncomingEvent = (newEvent) => {
    setEvents((prev) => {
      if (prev.some((e) => e.id === newEvent.id)) return prev;
      setNewEventIds((prevIds) => new Set([...prevIds, newEvent.id]));
      setTimeout(() => {
        setNewEventIds((prevIds) => {
          const updated = new Set(prevIds);
          updated.delete(newEvent.id);
          return updated;
        });
      }, 4000);
      return [newEvent, ...prev];
    });
  };

  // --- Handlers: Landing Screen ---
  const handleCreateRoom = async (e) => {
    e.preventDefault();
    if (!createName.trim()) return;
    setCreatingRoom(true);
    setLandingError(null);

    try {
      let targetProjectId = selectedProjectId;

      if (isCreatingProject) {
        if (!newProjectName.trim()) {
          setLandingError("Please enter a name for the new project.");
          setCreatingRoom(false);
          return;
        }
        const newProj = await createProject({
          name: newProjectName.trim(),
          description: "Created with Team Room",
        });
        targetProjectId = newProj.id;
        setActiveProject(newProj);
      } else {
        const found = projects.find((p) => p.id === targetProjectId);
        if (found) setActiveProject(found);
      }

      // 1. Create Team
      const team = await createTeam({
        name: createName.trim(),
        project_id: targetProjectId,
      });

      // 2. If GitHub repo specified, configure it
      if (githubRepoInput.trim()) {
        try {
          await configureGitHub(targetProjectId, githubRepoInput.trim());
        } catch (ghErr) {
          console.warn("Could not attach GitHub repo:", ghErr);
        }
      }

      // 3. Auto-join as room creator
      const creatorName = "Host (" + (currentUser || "Admin") + ")";
      await joinTeam({
        join_code: team.join_code,
        display_name: creatorName,
      });

      setCurrentUser(creatorName);
      setCurrentTeam(team);
      localStorage.setItem("onecontext_room", JSON.stringify(team));
      localStorage.setItem("onecontext_user", creatorName);
    } catch (err) {
      setLandingError(err.response?.data?.detail || err.message || "Failed to create room");
    } finally {
      setCreatingRoom(false);
    }
  };

  const handleJoinWithCode = async (e) => {
    e.preventDefault();
    if (!joinCodeInput.trim() || !joinNameInput.trim()) return;
    setJoiningRoom(true);
    setLandingError(null);

    try {
      const res = await joinTeam({
        join_code: joinCodeInput.trim().toUpperCase(),
        display_name: joinNameInput.trim(),
      });

      setCurrentUser(joinNameInput.trim());
      setCurrentTeam(res.team);
      localStorage.setItem("onecontext_room", JSON.stringify(res.team));
      localStorage.setItem("onecontext_user", joinNameInput.trim());

      // Set active project
      const proj = projects.find((p) => p.id === res.project_id) || {
        id: res.project_id,
        name: res.team.name,
      };
      setActiveProject(proj);
    } catch (err) {
      setLandingError(err.response?.data?.detail || err.message || "Invalid join code");
    } finally {
      setJoiningRoom(false);
    }
  };

  const handleLeaveRoom = () => {
    setCurrentTeam(null);
    localStorage.removeItem("onecontext_room");
    setEvents([]);
    setMembers([]);
  };

  const handleCopyCode = () => {
    if (!currentTeam?.join_code) return;
    navigator.clipboard.writeText(currentTeam.join_code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2500);
  };

  // --- Handlers: GitHub Sync ---
  const handleSyncGithub = async () => {
    if (!currentTeam?.project_id) return;
    setSyncingGithub(true);
    try {
      const res = await syncGitHub(currentTeam.project_id);
      const updated = await getGitHubConfig(currentTeam.project_id);
      setGithubConfig(updated);
      await fetchInitialRoomData(currentTeam.id);
    } catch (err) {
      console.error("GitHub sync failed:", err);
    } finally {
      setSyncingGithub(false);
    }
  };

  // --- Handlers: Right Panel Catch Up ---
  const handleRunCatchup = async () => {
    if (!currentTeam?.id) return;
    setLoadingCatchup(true);
    try {
      const data = await catchUpRoom(currentTeam.id, currentUser || "Teammate");
      setCatchupSummary(data.summary);
      setCatchupEvents(data.events || []);
    } catch (err) {
      console.error("Catch up failed:", err);
    } finally {
      setLoadingCatchup(false);
    }
  };

  // --- Handlers: Right Panel Context Pack ---
  const handleGeneratePack = async (e) => {
    e.preventDefault();
    if (!packTask.trim() || !currentTeam?.project_id) return;
    setGeneratingPack(true);
    setCopiedPack(false);
    try {
      const res = await getContextPack(currentTeam.project_id, {
        task: packTask.trim(),
        target: packTarget,
        max_chars: parseInt(packMaxChars, 10) || 3000,
      });
      setPackResult(res);
    } catch (err) {
      console.error("Context pack failed:", err);
    } finally {
      setGeneratingPack(false);
    }
  };

  const handleCopyPack = () => {
    if (!packResult?.pack) return;
    navigator.clipboard.writeText(packResult.pack);
    setCopiedPack(true);
    setTimeout(() => setCopiedPack(false), 2000);
  };

  // --- Handlers: Right Panel Add to Memory ---
  const handleCaptureMemory = async (e) => {
    e.preventDefault();
    if (!memText.trim() || !currentTeam?.project_id) return;
    setCapturingMem(true);
    setCaptureFeedback(null);

    try {
      const res = await captureDecision(currentTeam.project_id, {
        text: memText.trim(),
        source_name: memSourceName.trim() || `${currentUser || "team"}_${memType}`,
      });
      setCaptureFeedback(res);
      setMemText("");
      setMemSourceName("");
    } catch (err) {
      console.error("Capture memory error:", err);
    } finally {
      setCapturingMem(false);
    }
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!selectedUploadFile || !currentTeam?.project_id) return;
    setUploadingFile(true);
    setCaptureFeedback(null);

    const formData = new FormData();
    formData.append("file", selectedUploadFile);
    formData.append("source_type", memType);

    try {
      const res = await ingestFile(currentTeam.project_id, formData);
      setCaptureFeedback({
        has_conflict: false,
        detail: `Successfully ingested '${selectedUploadFile.name}' (${res.chunks_retained} chunks retained).`,
      });
      setSelectedUploadFile(null);
    } catch (err) {
      console.error("File upload error:", err);
    } finally {
      setUploadingFile(false);
    }
  };

  // --- Handlers: Memory Correction (Conflict Card) ---
  const handleOpenCorrection = (eventItem) => {
    setCorrectingEvent(eventItem);
    setCorrectText("");
    setCorrectReason("Resolving contradictory logic in Live Room");
  };

  const handleSubmitCorrection = async (e) => {
    e.preventDefault();
    if (!correctText.trim() || !currentTeam?.project_id) return;
    setSubmittingCorrection(true);

    try {
      await correctMemory(currentTeam.project_id, {
        old_memory_id: correctingEvent.source_ref || "prior-conflict-statement",
        new_text: correctText.trim(),
        agent_id: currentUser || "teammate",
        reason: correctReason,
        old_memory_text: correctingEvent.body,
      });
      setCorrectingEvent(null);
      setCorrectText("");
    } catch (err) {
      console.error("Correction failed:", err);
    } finally {
      setSubmittingCorrection(false);
    }
  };

  // Filter events
  const filteredEvents = events.filter((e) => {
    if (activeFilter === "all") return true;
    if (activeFilter === "commits") return e.type === "commit";
    if (activeFilter === "decisions") return e.type === "decision";
    if (activeFilter === "docs") return e.type === "document";
    if (activeFilter === "conflicts") return e.type === "conflict";
    return true;
  });

  // Render type icon
  const getEventIcon = (type) => {
    switch (type) {
      case "commit":
        return "💻";
      case "document":
        return "📄";
      case "decision":
        return "💡";
      case "correction":
        return "✏️";
      case "conflict":
        return "⚠️";
      case "member_joined":
        return "👤";
      default:
        return "📌";
    }
  };

  // ==========================================
  // VIEW A: LANDING SCREEN (NO ROOM YET)
  // ==========================================
  if (!currentTeam) {
    return (
      <div style={styles.landingContainer}>
        {/* Pitch Banner */}
        <div style={styles.landingHeader}>
          <div style={styles.badgeRow}>
            <span style={styles.livePill}>LIVE COLLABORATION</span>
            <span style={styles.memoryPill}>HINDSIGHT MEMORY</span>
          </div>
          <h1 style={styles.heroTitle}>One project. One memory. Every AI assistant.</h1>
          <p style={styles.heroSubtitle}>
            Join your teammates in a shared live room. When anyone records a decision, ingests a doc,
            or pushes code, everyone builds with the exact same verified context.
          </p>
        </div>

        {landingError && (
          <div style={styles.errorBanner}>
            ⚠️ {landingError}
          </div>
        )}

        {/* Side-by-Side Cards */}
        <div style={styles.cardsGrid}>
          {/* Card 1: Create a Room */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <span style={styles.cardIcon}>🚀</span>
              <h2 style={styles.cardTitle}>Create a Room</h2>
            </div>
            <p style={styles.cardDesc}>
              Spin up a shared project memory bank and invite your team with a 6-character code.
            </p>

            <form onSubmit={handleCreateRoom} style={styles.form}>
              <label style={styles.label}>
                Room Name:
                <input
                  type="text"
                  placeholder="e.g. Payments Core Room"
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  style={styles.input}
                  required
                />
              </label>

              <div style={styles.toggleRow}>
                <button
                  type="button"
                  onClick={() => setIsCreatingProject(false)}
                  style={!isCreatingProject ? styles.toggleBtnActive : styles.toggleBtn}
                >
                  Existing Project
                </button>
                <button
                  type="button"
                  onClick={() => setIsCreatingProject(true)}
                  style={isCreatingProject ? styles.toggleBtnActive : styles.toggleBtn}
                >
                  New Project
                </button>
              </div>

              {!isCreatingProject ? (
                <label style={styles.label}>
                  Attach to Project Memory:
                  <select
                    value={selectedProjectId}
                    onChange={(e) => setSelectedProjectId(e.target.value)}
                    style={styles.select}
                  >
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.id})
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <label style={styles.label}>
                  New Project Name:
                  <input
                    type="text"
                    placeholder="e.g. ApexPay Platform"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    style={styles.input}
                  />
                </label>
              )}

              <label style={styles.label}>
                GitHub Repository (optional):
                <input
                  type="text"
                  placeholder="e.g. acme/payments-api"
                  value={githubRepoInput}
                  onChange={(e) => setGithubRepoInput(e.target.value)}
                  style={styles.input}
                />
                <span style={styles.inputHint}>Polls commits every 45s into project memory.</span>
              </label>

              <button
                type="submit"
                disabled={creatingRoom || !createName.trim()}
                style={styles.primaryBtn}
              >
                {creatingRoom ? "Creating Room..." : "Create Room & Get Code"}
              </button>
            </form>
          </div>

          {/* Card 2: Join with a Code */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <span style={styles.cardIcon}>🔑</span>
              <h2 style={styles.cardTitle}>Join with a Code</h2>
            </div>
            <p style={styles.cardDesc}>
              Enter the 6-character room code shared by your teammate to sync with their memory.
            </p>

            <form onSubmit={handleJoinWithCode} style={styles.form}>
              <label style={styles.label}>
                Join Code:
                <input
                  type="text"
                  maxLength={6}
                  placeholder="e.g. 7X9K2B"
                  value={joinCodeInput}
                  onChange={(e) => setJoinCodeInput(e.target.value.toUpperCase())}
                  style={{ ...styles.input, textTransform: "uppercase", letterSpacing: "3px", fontSize: "1.2rem", fontWeight: "bold" }}
                  required
                />
              </label>

              <label style={styles.label}>
                Your Display Name:
                <input
                  type="text"
                  placeholder="e.g. Alice"
                  value={joinNameInput}
                  onChange={(e) => setJoinNameInput(e.target.value)}
                  style={styles.input}
                  required
                />
              </label>

              <div style={styles.infoCallout}>
                💡 <strong>Single Memory:</strong> Once joined, any context pack you generate pulls from the exact same Hindsight bank your teammates are updating.
              </div>

              <button
                type="submit"
                disabled={joiningRoom || !joinCodeInput.trim() || !joinNameInput.trim()}
                style={styles.secondaryBtn}
              >
                {joiningRoom ? "Joining..." : "Join Team Room"}
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  // ==========================================
  // VIEW B: LIVE ROOM SCREEN (3 COLUMNS)
  // ==========================================
  return (
    <div style={styles.roomContainer}>
      {/* COLUMN 1: LEFT SIDEBAR */}
      <aside style={styles.leftCol}>
        {/* Room Header */}
        <div style={styles.sidebarSection}>
          <div style={styles.roomHeaderTop}>
            <span style={styles.roomIcon}>🏢</span>
            <div>
              <h2 style={styles.roomName}>{currentTeam.name}</h2>
              <span style={styles.bankTag}>Bank: {currentTeam.project_id}</span>
            </div>
          </div>

          {/* Join Code Display */}
          <div style={styles.joinCodeBox}>
            <span style={styles.codeLabel}>ROOM JOIN CODE</span>
            <div style={styles.codeRow}>
              <span style={styles.codeText}>{currentTeam.join_code}</span>
              <button onClick={handleCopyCode} style={styles.copyCodeBtn}>
                {copiedCode ? "Copied! ✓" : "Copy"}
              </button>
            </div>
            <span style={styles.codeSubtext}>Teammates enter this code on the landing page</span>
          </div>
        </div>

        {/* Member Presence */}
        <div style={styles.sidebarSection}>
          <div style={styles.sectionHeaderRow}>
            <h3 style={styles.sidebarHeading}>Teammates</h3>
            <span style={styles.countBadge}>{members.length}</span>
          </div>

          <div style={styles.memberList}>
            {members.length === 0 ? (
              <div style={styles.emptySmall}>No teammates registered yet.</div>
            ) : (
              members.map((m, idx) => (
                <div key={idx} style={styles.memberItem}>
                  <div style={styles.memberLeft}>
                    <span
                      style={{
                        ...styles.statusDot,
                        backgroundColor: m.online ? "#10b981" : "#71717a",
                        boxShadow: m.online ? "0 0 8px #10b981" : "none",
                      }}
                    />
                    <span style={styles.memberName}>
                      {m.display_name} {m.display_name === currentUser && "(you)"}
                    </span>
                  </div>
                  <span style={styles.lastSeenText}>
                    {m.online ? "online" : formatRelativeTime(m.last_seen)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* GitHub Integration */}
        <div style={styles.sidebarSection}>
          <div style={styles.sectionHeaderRow}>
            <h3 style={styles.sidebarHeading}>GitHub Sync</h3>
            <button
              onClick={handleSyncGithub}
              disabled={syncingGithub || !githubConfig?.repo}
              style={styles.syncBtn}
            >
              {syncingGithub ? "Syncing..." : "Sync Now"}
            </button>
          </div>

          {githubConfig?.repo ? (
            <div style={styles.githubStatusCard}>
              <div style={styles.ghRow}>
                <span style={styles.ghIcon}>🐙</span>
                <span style={styles.ghRepoName}>{githubConfig.repo}</span>
              </div>
              <div style={styles.ghMeta}>
                <span>Status: <strong style={{ color: "#10b981" }}>{githubConfig.last_status || "connected"}</strong></span>
                <span>Last sync: {formatRelativeTime(githubConfig.last_sync)}</span>
              </div>
            </div>
          ) : (
            <div style={styles.emptySmall}>
              No repo connected.
              <button
                onClick={() => {
                  const repo = prompt("Enter GitHub repository (owner/repo):");
                  if (repo) configureGitHub(currentTeam.project_id, repo).then(setGithubConfig);
                }}
                style={styles.connectGhBtn}
              >
                + Connect GitHub Repo
              </button>
            </div>
          )}
        </div>

        {/* Leave Room Action */}
        <div style={styles.sidebarFooter}>
          <button onClick={handleLeaveRoom} style={styles.leaveBtn}>
            ← Leave Room
          </button>
        </div>
      </aside>

      {/* COLUMN 2: CENTER LIVE CONTEXT FEED */}
      <main style={styles.centerCol}>
        {/* Top Header of Feed */}
        <div style={styles.feedHeader}>
          <div style={styles.feedTitleRow}>
            <h2 style={styles.colTitle}>Live Context Feed</h2>
            <div style={styles.feedStatusIndicator}>
              <span
                style={{
                  ...styles.statusDot,
                  backgroundColor: connectionStatus === "live" ? "#10b981" : "#f59e0b",
                }}
              />
              <span style={styles.feedStatusText}>
                {connectionStatus === "live" ? "Real-time updates active" : "Reconnecting stream..."}
              </span>
            </div>
          </div>

          {/* Filter Pills */}
          <div style={styles.filterRow}>
            {["all", "commits", "decisions", "docs", "conflicts"].map((f) => (
              <button
                key={f}
                onClick={() => setActiveFilter(f)}
                style={activeFilter === f ? styles.filterPillActive : styles.filterPill}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Timeline Events List */}
        <div style={styles.timelineWrapper}>
          {filteredEvents.length === 0 ? (
            <div style={styles.feedEmptyState}>
              <span style={styles.emptyIcon}>📡</span>
              <h3>No activity yet in this room</h3>
              <p>Add a decision in the right panel, ingest a document, or connect a GitHub repository.</p>
            </div>
          ) : (
            filteredEvents.map((e) => {
              const isNew = newEventIds.has(e.id);
              const isConflict = e.type === "conflict";

              return (
                <div
                  key={e.id}
                  style={{
                    ...styles.eventCard,
                    borderLeft: isConflict
                      ? "4px solid #ef4444"
                      : e.type === "decision"
                      ? "4px solid #6366f1"
                      : e.type === "commit"
                      ? "4px solid #10b981"
                      : "4px solid #3b82f6",
                    backgroundColor: isNew ? "#1e1b4b" : isConflict ? "#261314" : "#18181b",
                    transition: "background-color 1s ease",
                  }}
                >
                  {/* Event Top Bar */}
                  <div style={styles.eventCardHeader}>
                    <div style={styles.eventMetaLeft}>
                      <span style={styles.eventIcon}>{getEventIcon(e.type)}</span>
                      <span style={styles.eventBadge}>{e.type.toUpperCase()}</span>
                      <span style={styles.eventAuthor}>{e.author}</span>
                      {isNew && <span style={styles.newBadge}>NEW</span>}
                    </div>
                    <span style={styles.eventTime}>{formatRelativeTime(e.created_at)}</span>
                  </div>

                  {/* Title & Body */}
                  <h4 style={styles.eventTitle}>{e.title}</h4>
                  <div style={styles.eventBody}>{e.body}</div>

                  {/* Special Conflict Warning Card Action */}
                  {isConflict && (
                    <div style={styles.conflictActionRow}>
                      <span style={styles.conflictWarningText}>
                        ⚠️ This memory contradicts an existing rule in project memory.
                      </span>
                      <button
                        onClick={() => handleOpenCorrection(e)}
                        style={styles.correctConflictBtn}
                      >
                        Correct this memory
                      </button>
                    </div>
                  )}

                  {e.source_ref && (
                    <div style={styles.eventRef}>Ref: {e.source_ref}</div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </main>

      {/* COLUMN 3: RIGHT PANEL (3 TABS) */}
      <section style={styles.rightCol}>
        {/* Tab Navigation */}
        <div style={styles.tabNav}>
          <button
            onClick={() => setRightTab("catchup")}
            style={rightTab === "catchup" ? styles.tabBtnActive : styles.tabBtn}
          >
            Catch Me Up
          </button>
          <button
            onClick={() => setRightTab("pack")}
            style={rightTab === "pack" ? styles.tabBtnActive : styles.tabBtn}
          >
            Context Pack
          </button>
          <button
            onClick={() => setRightTab("add")}
            style={rightTab === "add" ? styles.tabBtnActive : styles.tabBtn}
          >
            Add to Memory
          </button>
        </div>

        {/* TAB 1: CATCH ME UP */}
        {rightTab === "catchup" && (
          <div style={styles.tabContent}>
            <div style={styles.catchupHero}>
              <h3 style={styles.tabSectionTitle}>AI Catch-Up Summary</h3>
              <p style={styles.tabSectionDesc}>
                Get an instant grounded summary of everything that changed in this room since you last checked.
              </p>
              <button
                onClick={handleRunCatchup}
                disabled={loadingCatchup}
                style={styles.catchupBigBtn}
              >
                {loadingCatchup ? "Generating Catch-Up..." : "⚡ Catch Me Up Now"}
              </button>
            </div>

            {catchupSummary && (
              <div style={styles.summaryResultBox}>
                <div style={styles.summaryResultHeader}>
                  <h4>What changed in {currentTeam.name}:</h4>
                  <span style={styles.coveredCount}>
                    {catchupEvents.length} events analyzed
                  </span>
                </div>
                <div style={styles.summaryMarkdown}>
                  {catchupSummary.split("\n").map((line, idx) => (
                    <p key={idx} style={{ margin: "4px 0" }}>{line}</p>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: CONTEXT PACK */}
        {rightTab === "pack" && (
          <div style={styles.tabContent}>
            <h3 style={styles.tabSectionTitle}>Cross-Assistant Context Pack</h3>
            <p style={styles.tabSectionDesc}>
              Generate a compact project memory block formatted to paste or pipe directly into your AI assistant.
            </p>

            <form onSubmit={handleGeneratePack} style={styles.form}>
              <label style={styles.label}>
                What task are you working on?
                <input
                  type="text"
                  placeholder="e.g. Implement webhook retry queue"
                  value={packTask}
                  onChange={(e) => setPackTask(e.target.value)}
                  style={styles.input}
                  required
                />
              </label>

              <div style={styles.rowTwoCol}>
                <label style={styles.label}>
                  Target Assistant:
                  <select
                    value={packTarget}
                    onChange={(e) => setPackTarget(e.target.value)}
                    style={styles.select}
                  >
                    <option value="chatgpt">ChatGPT</option>
                    <option value="claude">Claude</option>
                    <option value="cursor">Cursor (Rules format)</option>
                    <option value="codex">Codex</option>
                    <option value="generic">Generic (System Prompt)</option>
                  </select>
                </label>

                <label style={styles.label}>
                  Max Characters:
                  <input
                    type="number"
                    value={packMaxChars}
                    onChange={(e) => setPackMaxChars(e.target.value)}
                    min={500}
                    max={10000}
                    step={500}
                    style={styles.input}
                  />
                </label>
              </div>

              <button
                type="submit"
                disabled={generatingPack || !packTask.trim()}
                style={styles.primaryBtn}
              >
                {generatingPack ? "Recalling Memories..." : "Generate Context Pack"}
              </button>
            </form>

            {packResult && (
              <div style={styles.packResultArea}>
                <div style={styles.packTopBar}>
                  <span>{packResult.char_count} chars • {packResult.sources_used?.length || 0} facts recalled</span>
                  <button onClick={handleCopyPack} style={styles.copyPackBtn}>
                    {copiedPack ? "Copied! ✓" : "Copy Context Pack"}
                  </button>
                </div>
                <pre style={styles.packCodeBlock}>{packResult.pack}</pre>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: ADD TO MEMORY */}
        {rightTab === "add" && (
          <div style={styles.tabContent}>
            <h3 style={styles.tabSectionTitle}>Add to Room Memory</h3>
            <p style={styles.tabSectionDesc}>
              Add decisions, notes, or ingest markdown documents into the shared bank.
            </p>

            {captureFeedback && (
              <div
                style={{
                  ...styles.feedbackBanner,
                  backgroundColor: captureFeedback.has_conflict ? "#450a0a" : "#064e3b",
                  border: captureFeedback.has_conflict ? "1px solid #ef4444" : "1px solid #10b981",
                }}
              >
                {captureFeedback.has_conflict ? (
                  <div>
                    <strong>⚠️ Conflict Warning:</strong> Memory recorded, but a contradiction was detected!
                  </div>
                ) : (
                  <div>
                    <strong>✓ Recorded:</strong> {captureFeedback.detail || "Saved to project memory and broadcasted to team."}
                  </div>
                )}
              </div>
            )}

            {/* Quick Capture Form */}
            <form onSubmit={handleCaptureMemory} style={styles.form}>
              <div style={styles.rowTwoCol}>
                <label style={styles.label}>
                  Memory Type:
                  <select
                    value={memType}
                    onChange={(e) => setMemType(e.target.value)}
                    style={styles.select}
                  >
                    <option value="decision">Architecture Decision</option>
                    <option value="document">Document / Spec</option>
                    <option value="note">Developer Note</option>
                  </select>
                </label>

                <label style={styles.label}>
                  Source Reference:
                  <input
                    type="text"
                    placeholder="e.g. ADR-014 or Slack"
                    value={memSourceName}
                    onChange={(e) => setMemSourceName(e.target.value)}
                    style={styles.input}
                  />
                </label>
              </div>

              <label style={styles.label}>
                Decision or Context to Retain:
                <textarea
                  rows={4}
                  placeholder="e.g. All API authentication must use Ed25519 signed JWTs with 15-minute expiration."
                  value={memText}
                  onChange={(e) => setMemText(e.target.value)}
                  style={styles.textarea}
                  required
                />
              </label>

              <button
                type="submit"
                disabled={capturingMem || !memText.trim()}
                style={styles.primaryBtn}
              >
                {capturingMem ? "Capturing..." : "Capture Decision (with conflict check)"}
              </button>
            </form>

            <div style={styles.divider}>OR UPLOAD SPEC (.md / .txt)</div>

            {/* Document Ingestion Form */}
            <form onSubmit={handleFileUpload} style={styles.form}>
              <input
                type="file"
                accept=".md,.txt"
                onChange={(e) => setSelectedUploadFile(e.target.files[0])}
                style={styles.fileInput}
              />
              <button
                type="submit"
                disabled={uploadingFile || !selectedUploadFile}
                style={styles.secondaryBtn}
              >
                {uploadingFile ? "Chunking & Retaining..." : "Ingest Document (~500 word chunks)"}
              </button>
            </form>
          </div>
        )}
      </section>

      {/* MODAL: RESOLVE CONFLICT */}
      {correctingEvent && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalCard}>
            <h3 style={styles.modalTitle}>Resolve Contradictory Memory</h3>
            <p style={styles.modalDesc}>
              A conflict was detected between room decisions. Retain a corrective memory to supersede the older rule.
            </p>

            <div style={styles.modalConflictBox}>
              <strong>Current Statement:</strong>
              <div style={styles.modalConfText}>{correctingEvent.body}</div>
            </div>

            <form onSubmit={handleSubmitCorrection} style={styles.form}>
              <label style={styles.label}>
                Correct Truth (New Decision):
                <textarea
                  rows={3}
                  value={correctText}
                  onChange={(e) => setCorrectText(e.target.value)}
                  placeholder="Enter the updated, definitive policy..."
                  style={styles.textarea}
                  required
                />
              </label>

              <label style={styles.label}>
                Reason for Supersession:
                <input
                  type="text"
                  value={correctReason}
                  onChange={(e) => setCorrectReason(e.target.value)}
                  style={styles.input}
                />
              </label>

              <div style={styles.modalActions}>
                <button
                  type="button"
                  onClick={() => setCorrectingEvent(null)}
                  style={styles.cancelBtn}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingCorrection || !correctText.trim()}
                  style={styles.primaryBtn}
                >
                  {submittingCorrection ? "Correcting..." : "Retain Correction"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// ==========================================
// STYLES (Clean Dark Theme, Readable Fonts)
// ==========================================
const styles = {
  // Landing
  landingContainer: {
    maxWidth: "1100px",
    margin: "0 auto",
    padding: "40px 24px",
  },
  landingHeader: {
    textAlign: "center",
    marginBottom: "36px",
  },
  badgeRow: {
    display: "flex",
    justifyContent: "center",
    gap: "10px",
    marginBottom: "12px",
  },
  livePill: {
    backgroundColor: "#1e1b4b",
    color: "#818cf8",
    fontSize: "0.75rem",
    fontWeight: "700",
    padding: "4px 10px",
    borderRadius: "12px",
    letterSpacing: "1px",
  },
  memoryPill: {
    backgroundColor: "#14281d",
    color: "#34d399",
    fontSize: "0.75rem",
    fontWeight: "700",
    padding: "4px 10px",
    borderRadius: "12px",
    letterSpacing: "1px",
  },
  heroTitle: {
    fontSize: "2.4rem",
    fontWeight: "800",
    color: "#f4f4f5",
    margin: "0 0 12px 0",
    lineHeight: 1.2,
  },
  heroSubtitle: {
    fontSize: "1.1rem",
    color: "#a1a1aa",
    maxWidth: "680px",
    margin: "0 auto",
    lineHeight: 1.5,
  },
  cardsGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "24px",
  },
  card: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "12px",
    padding: "28px",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.4)",
  },
  cardHeader: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    marginBottom: "8px",
  },
  cardIcon: {
    fontSize: "1.8rem",
  },
  cardTitle: {
    fontSize: "1.4rem",
    fontWeight: "700",
    color: "#f4f4f5",
    margin: 0,
  },
  cardDesc: {
    fontSize: "0.95rem",
    color: "#a1a1aa",
    margin: "0 0 20px 0",
    lineHeight: 1.4,
  },

  // 3-Column Room Screen
  roomContainer: {
    display: "grid",
    gridTemplateColumns: "280px 1fr 380px",
    height: "calc(100vh - 60px)",
    backgroundColor: "#09090b",
    color: "#f4f4f5",
    overflow: "hidden",
  },

  // Left Sidebar
  leftCol: {
    backgroundColor: "#121215",
    borderRight: "1px solid #27272a",
    display: "flex",
    flexDirection: "column",
    overflowY: "auto",
  },
  sidebarSection: {
    padding: "18px",
    borderBottom: "1px solid #1f1f23",
  },
  roomHeaderTop: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginBottom: "14px",
  },
  roomIcon: {
    fontSize: "1.6rem",
  },
  roomName: {
    fontSize: "1.15rem",
    fontWeight: "700",
    margin: 0,
    color: "#fafafa",
  },
  bankTag: {
    fontSize: "0.75rem",
    color: "#71717a",
  },
  joinCodeBox: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "8px",
    padding: "12px",
    textAlign: "center",
  },
  codeLabel: {
    fontSize: "0.7rem",
    color: "#a1a1aa",
    fontWeight: "700",
    letterSpacing: "1px",
    display: "block",
    marginBottom: "4px",
  },
  codeRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
    margin: "4px 0",
  },
  codeText: {
    fontSize: "1.6rem",
    fontWeight: "800",
    fontFamily: "monospace",
    letterSpacing: "4px",
    color: "#6366f1",
  },
  copyCodeBtn: {
    backgroundColor: "#27272a",
    border: "none",
    borderRadius: "6px",
    color: "#f4f4f5",
    fontSize: "0.75rem",
    padding: "4px 8px",
    cursor: "pointer",
  },
  codeSubtext: {
    fontSize: "0.72rem",
    color: "#71717a",
  },
  sectionHeaderRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "10px",
  },
  sidebarHeading: {
    fontSize: "0.85rem",
    fontWeight: "700",
    color: "#a1a1aa",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
    margin: 0,
  },
  countBadge: {
    backgroundColor: "#27272a",
    color: "#a1a1aa",
    fontSize: "0.75rem",
    padding: "2px 6px",
    borderRadius: "10px",
  },
  memberList: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  memberItem: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "6px 8px",
    backgroundColor: "#18181b",
    borderRadius: "6px",
  },
  memberLeft: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  statusDot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    display: "inline-block",
  },
  memberName: {
    fontSize: "0.88rem",
    fontWeight: "500",
    color: "#e4e4e7",
  },
  lastSeenText: {
    fontSize: "0.75rem",
    color: "#71717a",
  },
  syncBtn: {
    backgroundColor: "#1e1b4b",
    color: "#818cf8",
    border: "1px solid #3730a3",
    borderRadius: "4px",
    fontSize: "0.75rem",
    padding: "3px 8px",
    cursor: "pointer",
  },
  githubStatusCard: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "6px",
    padding: "10px",
  },
  ghRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginBottom: "6px",
  },
  ghIcon: {
    fontSize: "1.1rem",
  },
  ghRepoName: {
    fontSize: "0.88rem",
    fontWeight: "600",
    color: "#f4f4f5",
  },
  ghMeta: {
    display: "flex",
    flexDirection: "column",
    fontSize: "0.75rem",
    color: "#71717a",
    gap: "2px",
  },
  connectGhBtn: {
    marginTop: "8px",
    backgroundColor: "transparent",
    color: "#6366f1",
    border: "1px dashed #6366f1",
    borderRadius: "4px",
    padding: "6px 10px",
    fontSize: "0.8rem",
    cursor: "pointer",
    width: "100%",
  },
  sidebarFooter: {
    marginTop: "auto",
    padding: "16px",
    borderTop: "1px solid #1f1f23",
  },
  leaveBtn: {
    width: "100%",
    backgroundColor: "transparent",
    border: "1px solid #3f3f46",
    color: "#a1a1aa",
    borderRadius: "6px",
    padding: "8px",
    cursor: "pointer",
    fontSize: "0.85rem",
  },

  // Center Column: Live Context Feed
  centerCol: {
    backgroundColor: "#0d0d10",
    display: "flex",
    flexDirection: "column",
    borderRight: "1px solid #27272a",
    overflow: "hidden",
  },
  feedHeader: {
    padding: "18px 24px 14px",
    borderBottom: "1px solid #1f1f23",
    backgroundColor: "#111114",
  },
  feedTitleRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "12px",
  },
  colTitle: {
    fontSize: "1.3rem",
    fontWeight: "700",
    margin: 0,
    color: "#fafafa",
  },
  feedStatusIndicator: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  feedStatusText: {
    fontSize: "0.78rem",
    color: "#a1a1aa",
  },
  filterRow: {
    display: "flex",
    gap: "8px",
  },
  filterPill: {
    backgroundColor: "#18181b",
    color: "#a1a1aa",
    border: "1px solid #27272a",
    borderRadius: "14px",
    padding: "4px 12px",
    fontSize: "0.8rem",
    cursor: "pointer",
  },
  filterPillActive: {
    backgroundColor: "#6366f1",
    color: "#ffffff",
    border: "1px solid #6366f1",
    borderRadius: "14px",
    padding: "4px 12px",
    fontSize: "0.8rem",
    fontWeight: "600",
    cursor: "pointer",
  },
  timelineWrapper: {
    padding: "20px 24px",
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: "14px",
    flex: 1,
  },
  eventCard: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "8px",
    padding: "14px 16px",
    boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
  },
  eventCardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "6px",
  },
  eventMetaLeft: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  eventIcon: {
    fontSize: "1.1rem",
  },
  eventBadge: {
    fontSize: "0.68rem",
    fontWeight: "700",
    padding: "2px 6px",
    backgroundColor: "#27272a",
    borderRadius: "4px",
    color: "#e4e4e7",
  },
  eventAuthor: {
    fontSize: "0.82rem",
    color: "#a1a1aa",
    fontWeight: "500",
  },
  newBadge: {
    fontSize: "0.65rem",
    fontWeight: "800",
    color: "#ffffff",
    backgroundColor: "#6366f1",
    padding: "1px 6px",
    borderRadius: "4px",
  },
  eventTime: {
    fontSize: "0.78rem",
    color: "#71717a",
  },
  eventTitle: {
    fontSize: "0.98rem",
    fontWeight: "600",
    margin: "4px 0 6px 0",
    color: "#f4f4f5",
  },
  eventBody: {
    fontSize: "0.88rem",
    color: "#d4d4d8",
    whiteSpace: "pre-wrap",
    lineHeight: 1.45,
  },
  eventRef: {
    fontSize: "0.75rem",
    color: "#71717a",
    marginTop: "6px",
    fontFamily: "monospace",
  },
  conflictActionRow: {
    marginTop: "10px",
    paddingTop: "8px",
    borderTop: "1px solid #3f1515",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  conflictWarningText: {
    fontSize: "0.82rem",
    color: "#f87171",
  },
  correctConflictBtn: {
    backgroundColor: "#ef4444",
    color: "#ffffff",
    border: "none",
    borderRadius: "4px",
    padding: "5px 10px",
    fontSize: "0.8rem",
    fontWeight: "600",
    cursor: "pointer",
  },
  feedEmptyState: {
    textAlign: "center",
    padding: "60px 20px",
    color: "#71717a",
  },
  emptyIcon: {
    fontSize: "2.4rem",
    display: "block",
    marginBottom: "12px",
  },

  // Right Column: 3 Tabs
  rightCol: {
    backgroundColor: "#121215",
    display: "flex",
    flexDirection: "column",
    overflowY: "auto",
  },
  tabNav: {
    display: "flex",
    borderBottom: "1px solid #27272a",
    backgroundColor: "#16161a",
  },
  tabBtn: {
    flex: 1,
    padding: "14px 8px",
    backgroundColor: "transparent",
    border: "none",
    borderBottom: "2px solid transparent",
    color: "#a1a1aa",
    fontSize: "0.85rem",
    fontWeight: "600",
    cursor: "pointer",
  },
  tabBtnActive: {
    flex: 1,
    padding: "14px 8px",
    backgroundColor: "transparent",
    border: "none",
    borderBottom: "2px solid #6366f1",
    color: "#f4f4f5",
    fontSize: "0.85rem",
    fontWeight: "700",
    cursor: "pointer",
  },
  tabContent: {
    padding: "20px",
    flex: 1,
  },
  tabSectionTitle: {
    fontSize: "1.1rem",
    fontWeight: "700",
    color: "#fafafa",
    margin: "0 0 6px 0",
  },
  tabSectionDesc: {
    fontSize: "0.85rem",
    color: "#a1a1aa",
    margin: "0 0 16px 0",
    lineHeight: 1.4,
  },

  // Catchup specific
  catchupHero: {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "8px",
    padding: "18px",
    textAlign: "center",
    marginBottom: "18px",
  },
  catchupBigBtn: {
    width: "100%",
    backgroundColor: "#6366f1",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    padding: "12px",
    fontSize: "0.95rem",
    fontWeight: "700",
    cursor: "pointer",
    marginTop: "8px",
  },
  summaryResultBox: {
    backgroundColor: "#18181b",
    border: "1px solid #3730a3",
    borderRadius: "8px",
    padding: "16px",
  },
  summaryResultHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "10px",
  },
  coveredCount: {
    fontSize: "0.75rem",
    color: "#818cf8",
  },
  summaryMarkdown: {
    fontSize: "0.88rem",
    color: "#e4e4e7",
    lineHeight: 1.5,
  },

  // Pack specific
  rowTwoCol: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "10px",
  },
  packResultArea: {
    marginTop: "16px",
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "8px",
    overflow: "hidden",
  },
  packTopBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "8px 12px",
    backgroundColor: "#202024",
    fontSize: "0.78rem",
    color: "#a1a1aa",
  },
  copyPackBtn: {
    backgroundColor: "#6366f1",
    color: "#ffffff",
    border: "none",
    borderRadius: "4px",
    padding: "4px 10px",
    fontSize: "0.75rem",
    fontWeight: "600",
    cursor: "pointer",
  },
  packCodeBlock: {
    margin: 0,
    padding: "12px",
    fontSize: "0.82rem",
    fontFamily: "monospace",
    color: "#a5b4fc",
    maxHeight: "260px",
    overflowY: "auto",
    whiteSpace: "pre-wrap",
  },

  // Forms & Inputs
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  label: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    fontSize: "0.85rem",
    fontWeight: "600",
    color: "#d4d4d8",
  },
  input: {
    backgroundColor: "#27272a",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    color: "#f4f4f5",
    padding: "10px 12px",
    fontSize: "0.92rem",
    outline: "none",
  },
  select: {
    backgroundColor: "#27272a",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    color: "#f4f4f5",
    padding: "10px 12px",
    fontSize: "0.92rem",
    outline: "none",
  },
  textarea: {
    backgroundColor: "#27272a",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    color: "#f4f4f5",
    padding: "10px 12px",
    fontSize: "0.9rem",
    outline: "none",
    resize: "vertical",
    fontFamily: "inherit",
  },
  inputHint: {
    fontSize: "0.75rem",
    color: "#71717a",
  },
  toggleRow: {
    display: "flex",
    gap: "8px",
  },
  toggleBtn: {
    flex: 1,
    padding: "8px",
    backgroundColor: "#27272a",
    border: "1px solid #3f3f46",
    color: "#a1a1aa",
    borderRadius: "6px",
    fontSize: "0.82rem",
    cursor: "pointer",
  },
  toggleBtnActive: {
    flex: 1,
    padding: "8px",
    backgroundColor: "#3b82f6",
    border: "1px solid #3b82f6",
    color: "#ffffff",
    borderRadius: "6px",
    fontSize: "0.82rem",
    fontWeight: "600",
    cursor: "pointer",
  },
  primaryBtn: {
    backgroundColor: "#6366f1",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    padding: "10px 16px",
    fontSize: "0.92rem",
    fontWeight: "600",
    cursor: "pointer",
  },
  secondaryBtn: {
    backgroundColor: "#27272a",
    color: "#f4f4f5",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "10px 16px",
    fontSize: "0.92rem",
    fontWeight: "600",
    cursor: "pointer",
  },
  infoCallout: {
    backgroundColor: "#1e1b4b",
    border: "1px solid #3730a3",
    borderRadius: "6px",
    padding: "10px 12px",
    fontSize: "0.82rem",
    color: "#c7d2fe",
    lineHeight: 1.4,
  },
  errorBanner: {
    backgroundColor: "#450a0a",
    border: "1px solid #ef4444",
    color: "#fca5a5",
    borderRadius: "6px",
    padding: "10px 14px",
    fontSize: "0.88rem",
    marginBottom: "20px",
    textAlign: "center",
  },
  divider: {
    textAlign: "center",
    fontSize: "0.75rem",
    fontWeight: "700",
    color: "#71717a",
    margin: "18px 0 10px 0",
    letterSpacing: "1px",
  },
  fileInput: {
    backgroundColor: "#27272a",
    color: "#a1a1aa",
    padding: "8px",
    borderRadius: "6px",
    fontSize: "0.82rem",
  },
  feedbackBanner: {
    padding: "10px 12px",
    borderRadius: "6px",
    fontSize: "0.85rem",
    marginBottom: "14px",
    color: "#f4f4f5",
  },
  emptySmall: {
    fontSize: "0.82rem",
    color: "#71717a",
    textAlign: "center",
    padding: "10px 0",
  },

  // Modal
  modalOverlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0, 0, 0, 0.75)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modalCard: {
    backgroundColor: "#18181b",
    border: "1px solid #3f3f46",
    borderRadius: "10px",
    padding: "24px",
    width: "500px",
    maxWidth: "90%",
  },
  modalTitle: {
    fontSize: "1.2rem",
    fontWeight: "700",
    margin: "0 0 6px 0",
    color: "#f87171",
  },
  modalDesc: {
    fontSize: "0.85rem",
    color: "#a1a1aa",
    margin: "0 0 16px 0",
  },
  modalConflictBox: {
    backgroundColor: "#261314",
    border: "1px solid #7f1d1d",
    borderRadius: "6px",
    padding: "10px 12px",
    fontSize: "0.85rem",
    color: "#fca5a5",
    marginBottom: "16px",
  },
  modalConfText: {
    marginTop: "4px",
    fontSize: "0.82rem",
    color: "#fecaca",
  },
  modalActions: {
    display: "flex",
    justifyContent: "flex-end",
    gap: "10px",
    marginTop: "10px",
  },
  cancelBtn: {
    backgroundColor: "transparent",
    color: "#a1a1aa",
    border: "1px solid #3f3f46",
    borderRadius: "6px",
    padding: "8px 14px",
    cursor: "pointer",
  },
};
