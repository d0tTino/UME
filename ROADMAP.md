Below is a **phase-by-phase technical road map** that turns Universal Memory + Guardian-Angel into a production-grade, 24 × 7 platform.  Tasks are grouped by the P0–P3 priorities you already approved; “exit criteria” show when to advance.  Hardware guidance and DevOps notes ensure a smooth hand-off from your powerful desktop to a persistent server.

---

## 0 · Dev-foundations (local, Week 0)

| Goal                    | Tasks                                                                                                                   | Exit criteria                                  |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| **Containerised stack** | \* Docker Desktop + WSL2 (Ubuntu 24.04)<br>\* `docker-compose.yml` with Redpanda, LanceDB, TerminusDB, Minio (back-ups) | `docker compose up` shows all services healthy |
| **Python workspace**    | \* Python 3.12, `poetry` <br>\* Black, Ruff, MyPy pre-commit hooks<br>\* GH Actions CI (pytest + build/push images)     | CI badge green on `main`                       |
| **Access to repos**     | \* PAT with `repo` scope<br>\* gh-cli helper that emits `Repo.Create`, `Repo.Push` events                               | Universal-memory shows first GitHub event      |

---

## P0 · Bootstrapping Autonomy & Memory (Sprint 1–3)

| Capability                 | Key Implementations                                                                                         | Exit criteria                             |
| -------------------------- | ----------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| **0-A Event Bus**          | \* Redpanda single-node, 1 × NVMe partition<br>\* Avro schema (`branch_id`, `share`, ActivityStreams verbs) | `kcat -C` shows replay; seek works        |
| **0-B Privacy Filter**     | \* Rego policy + `nsfw-detector` + DataFog<br>\* ActivityWatch exclude list<br>\* Tauri toast signer        | Porn tab blocked; false-positive restored |
| **0-C Dev-log Watchers**   | \* ActivityWatch → producer scripts for IDE, clipboard                                                      | Code edit appears within < 50 ms          |
| **0-D Task DAG Manager**   | \* Tiny Dagster project; checkpoints require Angel approval                                                 | Dag visualises, waits for human           |
| **0-E Resource Scheduler** | \* `psutil` + `nvitop`; throttles ETL if CPU > 80 %                                                         | Gaming session shows zero dropped FPS     |
| **0-F Angel Bridge**       | \* Semantic-Kernel agent subscribes, writes `belief.update` events                                          | Angel digest summarises daily log         |

---

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

| ID      | Feature                    | Notes                                                    |
| ------- | -------------------------- | -------------------------------------------------------- |
| **1-A** | LLM Ferry bot (Playwright) | Ferries chats Cursor ⇆ Gemini, logs `llm.chat.*`         |
| **1-B** | Tweet-bot + UI             | Draft on `code.test.pass`; React UI inside Tauri panel   |
| **1-C** | Document Guru              | LangGraph chain to re-format + ask approval              |
| **1-D** | Dashboard                  | Next.js front end ↔ WebSockets (Redpanda “digest” topic) |
| **1-E** | OPA “work-mode” toggle     | Rego rule blocks distracting events during meetings      |
| **1-F** | Mobile capture             | Syncthing Mobile SDK ► `idea.note` events                |

Exit: weekly digest contains tweets, doc reforms, and mobile notes without manual intervention.

---

## P2 · Self-Improvement & Collective IQ (Q2 – Q3)

* **Auto-LoRA Tuner** – nightly job samples approved Q/A, fine-tunes 4-bit Llama, hot-swaps adapters.
* **Micro-agent Swarm Writer** – AutoGen 0.3 pipeline; 1-manager + 20 workers drafting wiki pages.
* **Model Autotuner** – bench llama-cpp, Mixtral-8x22B, GPT-4o; store best pick per task.
* **Provenance Explorer** – TerminusDB React app; diff belief graph across time.

Exit: Angel suggests faster model when task slows; provenance UI shows why a belief changed.

---

## P3 · Delight & Moonshots (back-log)

* Dreaming mode, phone LLM-lite, peer mesh, gamified focus, e-ink tile, etc.

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
