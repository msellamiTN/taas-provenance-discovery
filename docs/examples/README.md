# MCP / Enterprise Agent Gateway — Architecture document set

Prepared: **17 November 2026**  
Status: **Draft v0.1 — review required**

## Contents

1. `01-SoW-MCP-Agent-Gateway.md` — Statement of Work: scope, work packages, deliverables, roles, acceptance, assumptions and risks.
2. `02-LAD-MCP-Agent-Gateway.md` — Logical Architecture Document: components, protocols, identity, lifecycle, logical flows and architecture decisions.
3. `03-PAD-MCP-Agent-Gateway.md` — Physical Architecture Document: zones, GCP/Apigee/PSC topology, DNS, network flows, security and physical validation checklist.

## Baseline interpretation

The documents use **Apigee Hybrid + a custom Enterprise Agent Registry + Backstage/Camunda integration** as the working architecture baseline. This is a proposal, not an approved final decision. Gemini Enterprise Agent Platform is documented as an alternative for a broader agent-mesh capability.

The supplied screenshots identify:

- a single governed exposure layer for agents, applications, frontends and other agents;
- automatic registration and proxy exposure when R1 provisions an agent;
- internal API/non-API and external SaaS MCP consumption;
- Mistral and Vertex AI / Model Garden backends;
- WSO2 / JDE, Snowflake and Atlassian/Jira integration paths;
- PSC, load balancer, internal DNS, firewall, SD-WAN and Zscaler connectivity.

## Important technical validation

The screenshots refer to Apigee 1.16.x as a prerequisite. Current Google documentation checked on 17 November 2026 lists Apigee Hybrid 1.17.3 and states that native MCP support in Hybrid starts at 1.17.0. Hybrid currently supports the documented stateful MCP versions; the stateless `2026-07-28` protocol is not supported on Hybrid. Confirm product entitlements and the client-specific upgrade path before implementation.

## Status and limitations

- All documents are drafts, not signed contractual baselines.
- The physical network diagram was low-resolution; ambiguous project names, arrows, IPs, CIDRs, ports, DNS records and PSC producer/consumer roles are marked for validation.
- The exact first-wave endpoints, A2A level, identity delegation, scale, service objectives, schedule and commercial values remain open.
- No secrets, credentials, production IPs or unverified network values are included.
