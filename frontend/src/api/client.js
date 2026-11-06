/**
 * frontend/src/api/client.js
 * Axios API client communicating with the OneContext FastAPI backend.
 */

import axios from "axios";

const API_BASE_URL = "http://localhost:8000";

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

export default api;
