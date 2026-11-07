# OneContext Live Demonstration Script (3 Minutes)

> **One project. One memory. Every agent.**

This script provides an exact, step-by-step walkthrough to demonstrate OneContext in under 3 minutes, showcasing how Vectorize Hindsight Cloud grounds multi-agent workflows and prevents architectural drift.

---

## Pre-Demo Checklist (30 seconds before recording)
1. Double-click [`start_app.bat`](file:///C:/Users/Suresh/Desktop/one_mem/start_app.bat) to launch both FastAPI (`:8000`) and Vite (`:5173`).
2. Open your browser to `http://localhost:5173`.
3. Ensure the active project is set to **`apexpay-core`** in the top navigation bar.

---

## Step 1: The Before/After Panel (0:00 – 0:40)
**Goal:** Show the direct difference between an ungrounded LLM and OneContext's memory-grounded reasoning.

1. Navigate to the **Before / After** tab.
2. Under "Preset Questions", click:
   > *"What is our policy for transactions above $10,000?"*
3. Click **"Compare Responses"**.
4. **Talking Point**:
   > *"Notice the left column: without memory, the model provides generic fintech advice with zero source citations. On the right, OneContext queries our Hindsight memory bank, immediately citing our specific compliance policy: transactions over $10,000 require dual-officer sign-off from the compliance officer and finance director. It shows the author badge (`security-lead`), the source category, and the authentic Hindsight semantic vector score."*

---

## Step 2: Cross-Agent Memory Collaboration (0:40 – 1:20)
**Goal:** Prove that agents share a single brain without manual context passing.

1. Navigate to the **Agents** tab.
2. In the **Lead Architect (Planner)** card, click **Run Agent**.
   - Input task: *"Review our transactional database standard."*
   - Click **Execute Task**. The Planner reviews and confirms PostgreSQL 16 with UUIDv4 primary keys.
3. Scroll to the **Core Developer (Builder)** card and click **Run Agent**.
   - Input task: *"Generate implementation steps for the new ledger service."*
   - Click **Execute Task**.
4. **Talking Point**:
   > *"Notice that Builder was never given Planner's prompt. It autonomously recalled Planner's decision from Hindsight and generated an async SQLAlchemy implementation with UUIDv4 keys, perfectly aligned with the team's standard."*

---

## Step 3: Validator Catches a Contradictory PR (1:20 – 1:55)
**Goal:** Demonstrate automated QA preventing bad code from entering production.

1. Scroll to the **Compliance Auditor (Validator)** card.
2. In the draft field, paste:
   > *"PR #142: Implemented accounts persistence layer using MongoDB document store."*
3. Set the topic to *"database engine"* and click **Validate Proposed Draft**.
4. The system flags the draft with `valid: false` and displays:
   > *"Contradiction: Project policy strictly standardizes transactional persistence on PostgreSQL 16. MongoDB is prohibited."*
5. **Talking Point**:
   > *"Agent 3 caught the violation immediately by querying Hindsight. No human had to review the PR to enforce institutional memory."*

---

## Step 4: Conflict Detection on Retain (1:55 – 2:30)
**Goal:** Show real-time collision prevention when contradictory policies are submitted.

1. Navigate to **Memory Explorer**.
2. Click **"+ Retain New Memory"**.
3. In the text area, enter:
   > *"PROPOSAL: We are migrating all our public endpoints from REST to GraphQL."*
4. Click **Retain Memory**.
5. An **amber Warning Card** immediately appears above the grid:
   - **Established Decision**: REST with OpenAPI 3.1 conventions.
   - **New Proposed Memory**: REST to GraphQL proposal.
   - **Explanation**: Explicit contradiction detected between REST standard and GraphQL proposal.
6. **Talking Point**:
   > *"OneContext doesn't just store memories; it checks incoming decisions against existing policies at retain time using an LLM at temperature 0, alerting the team before conflicting rules spread."*

---

## Step 5: Memory Correction & Supersession (2:30 – 3:00)
**Goal:** Show how policies evolve cleanly without retaining zombie facts.

1. On the conflicting card in the warning banner, click:
   > **"✏️ Correct / Supersede Established Memory"**
2. In the modal, enter:
   - **Updated Policy**: *"DECISION: Public API remains on REST with OpenAPI 3.1. GraphQL is strictly rejected due to CDN edge caching limitations."*
   - **Reason**: *"Reverted proposal after edge caching audit."*
3. Click **"Save & Supersede Memory"**.
4. Return to the **Chat** or **Before/After** panel and ask:
   > *"Are we using REST or GraphQL?"*
5. The answer confirms REST and explicitly notes that GraphQL was evaluated and rejected. The old proposal is marked `⛔ Superseded` and excluded from active context.
6. **Closing Line**:
   > *"OneContext: One project. One memory. Every agent. Production-ready long-term memory for engineering teams."*
