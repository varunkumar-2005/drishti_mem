## Team Rooms
Team rooms use 6-character alphanumeric join codes to group collaborators around a shared project memory bank.
Join codes only work when teammates use the SAME running backend (one person hosts it and shares the backend URL), because team rooms and members are stored in that backend's local SQLite database.

## Live Room
- **Hosting & Connection**: One person hosts the backend and shares the URL. On the same Wi-Fi network, teammates use the host's local IP (e.g., `http://192.168.1.50:8000`). Over the internet, use a secure tunnel such as ngrok (`ngrok http 8000`) or Cloudflare Tunnel. Teammates run only the frontend with `VITE_API_URL` set to the host's backend URL, or open the hosted frontend directly in their browser.
- **Real-Time Sync**: Updates arrive across all connected teammates in a few seconds via Server-Sent Events (SSE) with an automatic 5-second polling fallback. Connected GitHub repositories automatically poll and synchronize commits into Hindsight every 45 seconds.
- **Indexing Delay**: Due to Hindsight's vector indexing pipeline, newly retained memories and ingested document chunks may take a few seconds to appear in generated context packs and catch-up summaries.
