import React, { useState } from "react";
import { Routes, Route, Link, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import ProjectCreate from "./pages/ProjectCreate";
import Agents from "./pages/Agents";
import MemoryExplorer from "./pages/MemoryExplorer";
import SearchHistory from "./pages/SearchHistory";
import Team from "./pages/Team";
import ContextPack from "./pages/ContextPack";

export default function App() {
  const [activeProject, setActiveProject] = useState(null);
  const [currentTeam, setCurrentTeam] = useState(null);
  const location = useLocation();

  const navLinks = [
    { path: "/", label: "Context Packs" },
    { path: "/dashboard", label: "Dashboard" },
    { path: "/memory", label: "Memory Explorer" },
    { path: "/agents", label: "Simulated Assistants (demo)" },
    { path: "/team", label: "Team Room" },
    { path: "/history", label: "Audit Trail" },
  ];

  return (
    <div style={styles.appWrapper}>
      {/* Top Navbar */}
      <nav style={styles.navbar}>
        <div style={styles.navInner}>
          <Link to="/" style={styles.logo}>
            <span style={styles.logoIcon}>🧠</span>
            <span style={styles.logoText}>OneContext</span>
            <span style={styles.logoBadge}>Hindsight + Groq</span>
          </Link>

          <div style={styles.navLinks}>
            {navLinks.map((link) => {
              const isActive = location.pathname === link.path;
              return (
                <Link
                  key={link.path}
                  to={link.path}
                  style={{
                    ...styles.navLink,
                    color: isActive ? "#ffffff" : "#a1a1aa",
                    backgroundColor: isActive ? "#27272a" : "transparent",
                  }}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>

          <div style={styles.activeProjectBadge}>
            {activeProject ? (
              <span>Bank: <strong>{activeProject.id}</strong></span>
            ) : (
              <span style={{ color: "#71717a" }}>No active project</span>
            )}
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main style={styles.mainContent}>
        <Routes>
          <Route
            path="/"
            element={<ContextPack activeProject={activeProject} setActiveProject={setActiveProject} />}
          />
          <Route
            path="/dashboard"
            element={<Dashboard activeProject={activeProject} setActiveProject={setActiveProject} />}
          />
          <Route
            path="/projects/new"
            element={<ProjectCreate setActiveProject={setActiveProject} />}
          />
          <Route
            path="/agents"
            element={<Agents activeProject={activeProject} />}
          />
          <Route
            path="/memory"
            element={<MemoryExplorer activeProject={activeProject} />}
          />
          <Route
            path="/history"
            element={<SearchHistory activeProject={activeProject} />}
          />
          <Route
            path="/team"
            element={
              <Team
                activeProject={activeProject}
                setActiveProject={setActiveProject}
                currentTeam={currentTeam}
                setCurrentTeam={setCurrentTeam}
              />
            }
          />
        </Routes>
      </main>
    </div>
  );
}

const styles = {
  appWrapper: {
    minHeight: "100vh",
    backgroundColor: "#09090b",
    color: "#f4f4f5",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  },
  navbar: {
    backgroundColor: "#121215",
    borderBottom: "1px solid #27272a",
    position: "sticky",
    top: 0,
    zIndex: 50,
  },
  navInner: {
    maxWidth: "1280px",
    margin: "0 auto",
    padding: "0 24px",
    height: "64px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  logo: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    textDecoration: "none",
  },
  logoIcon: {
    fontSize: "24px",
  },
  logoText: {
    color: "#f4f4f5",
    fontSize: "20px",
    fontWeight: "800",
    letterSpacing: "-0.5px",
  },
  logoBadge: {
    backgroundColor: "#27272a",
    color: "#60a5fa",
    fontSize: "11px",
    fontWeight: "700",
    padding: "3px 8px",
    borderRadius: "12px",
    marginLeft: "4px",
  },
  navLinks: {
    display: "flex",
    gap: "6px",
  },
  navLink: {
    textDecoration: "none",
    fontSize: "14px",
    fontWeight: "600",
    padding: "8px 14px",
    borderRadius: "8px",
    transition: "all 0.15s ease",
  },
  activeProjectBadge: {
    fontSize: "12px",
    color: "#a1a1aa",
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    padding: "6px 12px",
    borderRadius: "6px",
  },
  mainContent: {
    maxWidth: "1280px",
    margin: "0 auto",
    padding: "32px 24px",
  },
};
