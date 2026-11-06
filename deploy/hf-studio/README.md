---
title: TaaS Studio F01
emoji: 🧭
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: TaaS Studio extension staging — API-backed platform overview
---

# TaaS Studio — F01 staging

Private staging deployment of the existing TaaS Studio extended from baseline commit
18e577d46f1c0b5e896a144a817ddef2b06d988a.

This image serves the existing FastAPI Studio application and static workspace UI.
The Platform Overview uses existing authenticated Core inventory endpoints.

## Required Space Secret

Configure TAAS_STUDIO_API_TOKEN in Space Settings → Secrets before using authenticated API routes.
Use a strong random value and keep it out of source files, notebooks, logs and client-side defaults.

## Health checks

- /health — process health (public, no inventory data).
- /ready — readiness; returns HTTP 503 until TAAS_STUDIO_API_TOKEN is configured.
- All /api/v1/* endpoints remain bearer-token protected.

## Security and scope

- This is a separate private staging Space; it does not replace MSellami/TAAS_Studio.
- No MCP tool invocation or governed execution is enabled by F01.
- Inventory counts are not trust, policy, authorization or readiness decisions.
- The Space uses the repository's retained benchmark data and does not fetch upstream registries at runtime.
