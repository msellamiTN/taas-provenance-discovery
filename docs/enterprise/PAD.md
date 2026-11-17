# PAD — Physical / Deployment Architecture Design

Deployment topologies and industrialized provisioning for the TaaS control
plane. Everything here is a **design target** unless marked *delivered* —
see `REQUIREMENTS_GAP.md`.

## 1. Deployment topologies

| Topology | Audience | Shape | Status |
|---|---|---|---|
| **T-A · Colab / single process** | Reviewers, dev | One uvicorn process, 7 SQLite stores under a data dir, token via env, proxy URL | delivered — verified on Colab |
| **T-B · Single VM** | Small pilot | Container (root `Dockerfile`), same 7 SQLite stores on a volume, reverse proxy terminates TLS | container written; build unverified; proxy policy = Phase B |
| **T-C · K8s (incl. GPU)** | Production | N stateless API replicas behind ingress/gateway; externalized stores (Postgres); optional GPU node pool for model-runtime workloads | design — Phase B |
| **T-D · Air-gapped on-prem** | Regulated | Offline install bundle (wheels + image tarball + seed registries); Vault/KMS for secrets; no outbound calls | design — Phase D |

T-C detail: the control-plane pod is stateless (NFR-SCL-1). Model-runtime
workloads (HF/Ollama/vLLM) schedule onto GPU nodes via node selectors; the API
itself is CPU-only. The seven stores map to one Postgres database (adapter)
or, in small installs, a hostPath/PVC-backed SQLite layout (single replica only).

## 2. Industrialized provisioning

### Terraform module layout (Phase B)

```
infra/
├── modules/
│   ├── control-plane/    # compute + env wiring + health checks
│   ├── k8s-gpu/          # cluster or node-pool, GPU device plugins, taints
│   ├── gateway/          # API gateway / ingress, TLS, policies (§3)
│   ├── network-egress/   # egress proxy + allow-list rules (§4)
│   ├── secrets/          # KMS/Vault/Secret Manager + CSI wiring
│   └── observability/    # log sink, trace/metrics export, SIEM hook
├── envs/
│   ├── aws/  gcp/  azure/  private/
│   └── colab-dev/        # nothing — notebooks self-provision
```

Everything configurable is an env var today (`docs/deployment/STUDIO_OPERATIONS.md`
§1) — modules map 1:1 to the same variables; no code changes required.

### API gateway policy (Phase B)

| Policy | Rule | Rationale |
|---|---|---|
| TLS | Terminate at gateway; service listens HTTP on loopback/mesh | cert rotation central |
| Auth | Bearer passthrough; gateway may add OIDC session auth (Phase B) | control-plane auth stays fail-closed |
| Rate limit | per-key quotas; 429 with `Retry-After` | protects inspection/discovery cost paths |
| Body cap | **2 MiB** — mirrors in-app cap (413) | parity so error semantics don't change |
| Request-id | honor/propagate `X-Request-ID` | audit correlation must survive the hop |
| WAF | OWASP baseline ruleset where available (APIM/WAF/Cloud Armor) | defense in depth |

### Egress proxy rules (Phase B)

| Destination | Policy |
|---|---|
| MCP servers (stdio) | N/A — local processes; command allow-list in registry config only |
| MCP servers (HTTP) | Egress allow-list by host; timeouts; responses stay `unverified` |
| AI platforms (HF/Mistral/Foundry/Vertex/Bedrock) | Per-provider endpoint allow-list; credentials via secret store only |
| Package/index fetches | Deny in prod; air-gap installs use seeded bundle (T-D) |

## 3. Secrets & key management

| Secret | Today (delivered) | Target |
|---|---|---|
| `TAAS_STUDIO_API_TOKEN` (bootstrap) | env var | gateway/secret-store; retire bootstrap per ops decision |
| Named API keys | hashed SHA-256 in `api_keys.sqlite3` | same + optional KMS envelope for store volume |
| `TAAS_EVIDENCE_ATTESTATION_KEY` | env/file; **persist across restarts** or prior signatures invalidate | KMS/Vault key; rotation = re-attest procedure (runbook §) |
| Provider credentials (Phase D) | — | per-provider secret entries; least-privilege scopes |
| TLS/material | dev: none (loopback) | gateway cert manager; mTLS optional in mesh (Phase C) |

## 4. Multi-cloud / private matrix

| Layer | AWS | GCP | Azure | Private / on-prem |
|---|---|---|---|---|
| Compute | EKS (Karpenter GPU nodes) | GKE (GPU pools) | AKS (GPU pools) | K3s / kubeadm (+NVIDIA operator) |
| Gateway | ALB + WAF / API GW | Cloud LB + Cloud Armor | APIM / AppGW | NGINX Ingress + ModSecurity |
| Secrets | Secrets Manager + CSI | Secret Manager + CSI | Key Vault + CSI | HashiCorp Vault |
| AI platform | Bedrock adapter (Phase D) | Vertex adapter (Phase D) | AI Foundry adapter (Phase D) | Ollama / vLLM / Mistral self-hosted |
| Logs/metrics | CloudWatch/OTel → SIEM | Cloud Logging/OTel | Monitor/OTel → Sentinel | Loki/Prom + OTel → SIEM |
| Registry data | image: ECR | Artifact Registry | ACR | private registry / tarball |

All provider adapters return the same contract surface; model metadata remains
`unverified` regardless of provider (boundary rule).

## 5. Observability stack

- **Logs**: one JSON line/request (`event, request_id, method, path, status,
  duration_ms`) — ship via fluent-bit/sidecar to the platform sink; headers
  and bodies are never logged (delivered invariant).
- **Audit correlation**: `payload.request_id` on every audit event links
  ledger `seq` ↔ API call ↔ upstream trace once OTel lands (Phase B).
- **Probes**: `/health` (liveness) + `/ready` (readiness incl. calibration
  state) — gateway/k8s probes wire to both (delivered).
- **Metrics** (Phase B): request rates, 4xx/5xx ratio, inspection latency,
  store sizes; alert on 5xx, health flaps, audit-verify failures.
