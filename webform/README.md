# Travel Agent Webform

Next.js web client migrated from the Abacus prototype. The browser never calls Abacus AI or travel search providers directly. `/api/submit` is a server-side proxy to `POST /v1/web/draft` on the FastAPI Contract v1 runtime.

Required server-only environment variables:
- `TRAVEL_AGENT_API_URL`
- `TRAVEL_AGENT_WEB_TOKEN`

The returned result is always presented as an **AI Draft** until a travel agent approves the exact proposal version. Live provider search and model planning remain controlled by FastAPI feature flags and are not enabled by this web client.

The map/KML export routes retain the existing optional SerpApi geocoding integration as a transitional map-only capability; they do not search flights or hotels.
