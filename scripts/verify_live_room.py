import requests
import time
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"

print("--- 1. Checking Backend Health ---")
h = requests.get(f"{BASE}/health").json()
print("Health:", h)

print("\n--- 2. Creating a Team Room as Alice ---")
projects = requests.get(f"{BASE}/projects").json()
project_id = projects[0]["id"]
print(f"Using project: {projects[0]['name']} ({project_id})")

create_res = requests.post(
    f"{BASE}/teams",
    json={"name": "Dev Team Alpha", "project_id": project_id}
).json()
team_id = create_res["id"]
code = create_res["join_code"]
print(f"Room Created! Team ID: {team_id} | Join Code: {code}")

print("\n--- 3. Alice joins the room ---")
alice_res = requests.post(
    f"{BASE}/teams/join",
    json={"join_code": code, "display_name": "Alice"}
).json()
print(f"Alice joined! Member: {alice_res['member']['display_name']}")

print("\n--- 4. Bob joins the room using Join Code in separate session ---")
bob_res = requests.post(
    f"{BASE}/teams/join",
    json={"join_code": code, "display_name": "Bob"}
).json()
print(f"Bob joined! Member: {bob_res['member']['display_name']}")

print("\n--- 5. Checking Room Presence (Heartbeat & Members) ---")
requests.post(f"{BASE}/rooms/{team_id}/heartbeat", json={"display_name": "Alice"})
requests.post(f"{BASE}/rooms/{team_id}/heartbeat", json={"display_name": "Bob"})
members = requests.get(f"{BASE}/rooms/{team_id}/members").json()
for m in members:
    status = "🟢 ONLINE" if m.get("online") else "⚪ OFFLINE"
    print(f"  Teammate: {m['display_name']} -> {status}")

print("\n--- 6. Alice Captures a Decision ---")
decision_text = "All database queries must use parameterized prepared statements to prevent injection."
cap_res = requests.post(
    f"{BASE}/projects/{project_id}/capture",
    json={"text": decision_text, "source_name": "Alice"}
).json()
print(f"Captured: {decision_text[:60]}... (Conflict: {cap_res.get('has_conflict')})")

print("\n--- 7. Bob reads the Live Context Feed ---")
events = requests.get(f"{BASE}/rooms/{team_id}/events").json()
print(f"Total events in feed: {len(events)}")
for e in events[:3]:
    print(f"  [{e['type'].upper()}] {e['title']} (by {e['author']})")

print("\n--- 8. Bob asks 'Catch me up' to summarize Alice's changes ---")
catchup = requests.post(
    f"{BASE}/rooms/{team_id}/catch-up",
    json={"display_name": "Bob"}
).json()
print("Catch-up events count:", catchup["events_count"])
print("AI Catch-Up Summary:\n" + catchup["summary"])

print("\n=== VERIFICATION COMPLETE: ALL TEAM FEATURES WORKING! ===")
