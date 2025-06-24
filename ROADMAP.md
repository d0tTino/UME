Below is a **phase-by-phase technical road map** that turns Universal Memory + Guardian-Angel into a production-grade, 24 × 7 platform.  Tasks are grouped by the P0–P3 priorities you already approved; “exit criteria” show when to advance.  Hardware guidance and DevOps notes ensure a smooth hand-off from your powerful desktop to a persistent server.

---
## Exocortic Eudaemon pillars

| Pillar | Description |
| ------ | ----------- |
| **Memory** | Durable event capture and recall. |
| **Ethical Safeguards** | Privacy, policy enforcement and security boundaries. |
| **Productive Collaboration** | Features that help users act on knowledge and share updates. |
| **Self-Improvement** | Automated tuning and continual learning loops. |
| **Operational Resilience** | CI/CD, observability and power efficiency for 24×7 use. |

---


## 0 · Dev-foundations (local, Week 0)

| Goal | Pillar | Stakeholders | Acceptance Criteria | Effort |
| ---- | ------ | ------------ | ------------------- | ------ |
| **Containerised stack** | Operational Resilience | DevOps team | `docker compose up` shows all services healthy | M |
| **Python workspace** | Operational Resilience | Dev team | CI badge green on `main` | S |
| **Access to repos** | Memory | Dev team | Universal-memory shows first GitHub event | S |

## P0 · Bootstrapping Autonomy & Memory (Sprint 1–3)

| ID | Feature | Pillar | Stakeholders | Acceptance Criteria | Effort |
| --- | ------- | ------ | ------------ | ------------------- | ------ |
| **0-A** | Event Bus | Memory | Data engineers | `kcat -C` shows replay; seek works | L |
| **0-B** | Privacy Filter | Ethical Safeguards | Privacy officer | Porn tab blocked; false-positive restored | M |
| **0-C** | Dev-log Watchers | Memory | Developers | Code edit appears within < 50 ms | S |
| **0-D** | Task DAG Manager | Memory | Data scientists | Dag visualises, waits for human | M |
| **0-E** | Resource Scheduler | Operational Resilience | Ops team | Gaming session shows zero dropped FPS | S |
| **0-F** | Angel Bridge | Productive Collaboration | Product owner | Angel digest summarises daily log | M |
## Hardware pivot planning (parallel with P0)

### Why EPYC

* 4th-gen AMD EPYC (Zen 4c “Bergamo”) offers **best perf/W** and ECC RAM; 1 × 64-core 9254P idles ≈ 55 W, well within home-lab budgets. ([Level1Techs Forums][1])
* Dell **PowerEdge R7625** ships with dual 10 GbE, PCIe 5.0 lanes for future GPUs, and tested idle draw ≈ 85 W with one CPU and four NVMe drives—solid 24/7 box. ([Dell][2])

| Recommended starter config                     |
| ---------------------------------------------- |
| 1 × EPYC 9254P (64C 128T, 200 W TDP)           |
| 256 GB ECC DDR5-4800                           |
| 4 × 4 TB Gen4 NVMe (mirrored Redpanda / Lance) |
| 2 × 10 GbE + iDRAC                             |
| Ubuntu Server 24.04 LTS                        |

Redpanda’s sizing guide shows a single such node easily handles 100 MB/s sustained ingest with < 5 ms p99 latency. ([Redpanda Documentation][3], [Redpanda Documentation][4])  You can cluster later by adding two cheaper 32-core nodes.

---

## P1 · Productivity & Public Face (Sprint 4–8)

| ID | Feature | Pillar | Stakeholders | Acceptance Criteria | Effort |
| --- | ------- | ------ | ------------ | ------------------- | ------ |
| **1-A** | LLM Ferry bot | Productive Collaboration | Developers | Chats mirrored and logged | M |
| **1-B** | Tweet-bot + UI | Productive Collaboration | Community manager | Posts appear in digest | M |
| | _Implemented via_ `ume.TweetBot` | | | | |
| **1-C** | Document Guru | Productive Collaboration | Docs team | Reformatted files awaiting approval | M |
| **1-D** | Dashboard | Productive Collaboration | All users | Web UI shows digests | M |
| **1-E** | OPA “work-mode” toggle | Ethical Safeguards | Ops team | Rego rule blocks distractions during meetings | S |
| **1-F** | Mobile capture | Memory | Users | Notes sync via events | M |

Exit: weekly digest contains tweets, doc reforms, and mobile notes without manual intervention.
## P2 · Self-Improvement & Collective IQ (Q2 – Q3)

| Feature | Pillar | Stakeholders | Acceptance Criteria | Effort |
| ------- | ------ | ------------ | ------------------- | ------ |
| Auto-LoRA Tuner | Self-Improvement | ML engineers | Adapter swapped nightly | L |
| Micro-agent Swarm Writer | Productive Collaboration | Knowledge team | Wiki drafts generated | L |
| Model Autotuner | Self-Improvement | ML engineers | Faster model selected per task | M |
| Provenance Explorer | Self-Improvement | All users | UI explains belief changes | M |
Exit: Angel suggests faster model when task slows; provenance UI shows why a belief changed.|

| Feature | Pillar | Stakeholders | Acceptance Criteria | Effort |
| ------- | ------ | ------------ | ------------------- | ------ |
| Dreaming mode | Self-Improvement | Users | Prompts captured during sleep | L |
| Phone LLM-lite | Productive Collaboration | Mobile users | Offline responses within 1s | L |
| Peer mesh | Productive Collaboration | Community | Peers share events securely | L |
| Gamified focus | Self-Improvement | Users | Focus sessions logged | M |
| E-ink tile | Operational Resilience | Hardware team | Display updates from dashboard | M |
---

## DevOps & lifecycle pillars

| Pillar            | Implementation                                                                      |
| ----------------- | ----------------------------------------------------------------------------------- |
| **CI/CD**         | GitHub Actions builds; `docker buildx` → GHCR; Ansible deploys containers on R7625. |
| **Observability** | OpenTelemetry → Prometheus → Grafana dash; Redpanda metrics exporter.               |
| **Back-ups**      | Nightly MirrorMaker to Minio (S3 + Zstd); Parquet monthly archives.                 |
| **Security**      | WireGuard VPN for remote; Fail2Ban; Rego policy gateway in front of write API.      |
| **Energy**        | Redpanda `power_save_mode`, CPU governor “schedutil”; nightly cron parks GPU.       |

---

## Milestone checklist

1. **P0 complete, local** – single-node stack stable, privacy filter proven.
2. **Server procured & imaged** – R7625 (or similar) online, Docker swarm bootstrapped.
3. **State migration** – Redpanda topic mirror replicates events; cut agents over.
4. **P1 features live** – LLM Ferry + dashboard in daily use.
5. **Cluster scale-out** – add 2 × 32-core nodes; enable Redpanda tiered storage.
6. **P2 intelligence** – LoRA tuner producing weekly adapters; Angel auto-selects fastest.

With that scaffold you can start coding tomorrow, migrate seamlessly when the server arrives, and layer on intelligence without ever rewriting the foundations.

[1]: https://forum.level1techs.com/t/eypc-homelab-2025/221576?utm_source=chatgpt.com "Eypc homelab 2025 - Build a PC - Level1Techs Forums"
[2]: https://www.dell.com/en-sg/shop/ipovw/poweredge-r7625?utm_source=chatgpt.com "PowerEdge R7625 Rack Server | Dell Singapore"
[3]: https://docs.redpanda.com/current/deploy/deployment-option/self-hosted/manual/production/requirements/?utm_source=chatgpt.com "Requirements and Recommendations | Redpanda Self-Managed"
[4]: https://docs.redpanda.com/current/deploy/deployment-option/self-hosted/manual/sizing/?utm_source=chatgpt.com "Sizing Guidelines | Redpanda Self-Managed"
