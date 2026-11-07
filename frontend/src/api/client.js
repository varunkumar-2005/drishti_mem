/**
 * frontend/src/api/client.js
 * Axios API client communicating with the OneContext FastAPI backend.
 */

import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export const getHealth = async () => {
  const res = await api.get("/health");
  return res.data;
};

// --- Projects ---
export const listProjects = async () => {
  const res = await api.get("/projects");
  return res.data;
};

export const createProject = async ({ name, description }) => {
  const res = await api.post("/projects", { name, description });
  return res.data;
};

// --- Agents ---
export const listAgents = async (projectId) => {
  const res = await api.get(`/projects/${projectId}/agents`);
  return res.data;
};

export const registerAgent = async (projectId, { id, name, role }) => {
  const res = await api.post(`/projects/${projectId}/agents`, { id, name, role });
  return res.data;
};

export const runAgent = async (projectId, agentId, { task, context }) => {
  const res = await api.post(`/projects/${projectId}/agents/${agentId}/run`, {
    task,
    context,
  });
  return res.data;
};

// --- Memory & RAG ---
export const retainMemory = async (projectId, { text, source, agent_id }) => {
  const res = await api.post(`/projects/${projectId}/retain`, {
    text,
    source: source || "note",
    agent_id: agent_id || "user",
  });
  return res.data;
};

export const recallMemory = async (projectId, { query, max_results = 5 }) => {
  const res = await api.post(`/projects/${projectId}/recall`, {
    query,
    max_results,
  });
  return res.data;
};

export const askMemory = async (projectId, { question, agent_id = "user" }) => {
  const res = await api.post(`/projects/${projectId}/ask`, {
    question,
    agent_id,
  });
  return res.data;
};

export const askWithoutMemory = async (projectId, { question, agent_id = "user" }) => {
  const res = await api.post(`/projects/${projectId}/ask-without-memory`, {
    question,
    agent_id,
  });
  return res.data;
};

// --- Corrections & Conflict Detection (Phase 5) ---
export const correctMemory = async (projectId, { old_memory_id, new_text, agent_id = "user", reason = "", old_memory_text = "" }) => {
  const res = await api.post(`/projects/${projectId}/correct`, {
    old_memory_id,
    new_text,
    agent_id,
    reason,
    old_memory_text,
  });
  return res.data;
};

export const checkConflict = async (projectId, { text }) => {
  const res = await api.post(`/projects/${projectId}/check-conflict`, { text });
  return res.data;
};

export const getConflicts = async (projectId) => {
  const res = await api.get(`/projects/${projectId}/conflicts`);
  return res.data;
};

// --- Validator ---
export const validateDraft = async (projectId, { draft, check_topic }) => {
  const res = await api.post(`/projects/${projectId}/validate`, {
    draft,
    check_topic,
  });
  return res.data;
};

// --- Audit Trail ---
export const getAudit = async (projectId, limit = 50) => {
  const res = await api.get(`/projects/${projectId}/audit?limit=${limit}`);
  return res.data;
};

// --- Team Rooms ---
export const createTeam = async ({ name, project_id }) => {
  const res = await api.post("/teams", { name, project_id });
  return res.data;
};

export const joinTeam = async ({ join_code, display_name }) => {
  const res = await api.post("/teams/join", { join_code, display_name });
  return res.data;
};

export const listTeamMembers = async (teamId) => {
  const res = await api.get(`/teams/${teamId}/members`);
  return res.data;
};

export const sendTeamMessage = async (teamId, { sender, role, message, message_type = "chat", retain_as_memory = false }) => {
  const res = await api.post(`/teams/${teamId}/messages`, {
    sender,
    role,
    message,
    message_type,
    retain_as_memory,
  });
  return res.data;
};

export const listTeamMessages = async (teamId, limit = 100) => {
  const res = await api.get(`/teams/${teamId}/messages?limit=${limit}`);
  return res.data;
};

export const seedTeamDemo = async (teamId) => {
  const res = await api.post(`/teams/${teamId}/seed-demo`);
  return res.data;
};

export const generateTeamCode = async (teamId, { instruction, current_code, filename, author }) => {
  const res = await api.post(`/teams/${teamId}/generate-code`, {
    instruction,
    current_code,
    filename,
    author,
  });
  return res.data;
};

// --- Context Packs & Ingestion ---
export const getContextPack = async (projectId, { task, target = "generic", max_chars = 3000 }) => {
  const res = await api.post(`/projects/${projectId}/context-pack`, {
    task,
    target,
    max_chars,
  });
  return res.data;
};

export const ingestText = async (projectId, { text, source_type = "doc", source_name }) => {
  const res = await api.post(`/projects/${projectId}/ingest`, {
    text,
    source_type,
    source_name,
  });
  return res.data;
};

export const ingestFile = async (projectId, formData) => {
  const res = await api.post(`/projects/${projectId}/ingest-file`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};

export const captureDecision = async (projectId, { text, source_name = "manual_capture" }) => {
  const res = await api.post(`/projects/${projectId}/capture`, {
    text,
    source_name,
  });
  return res.data;
};

export default api;
