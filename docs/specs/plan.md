# Reddit Technical Watcher – Implementation Plan (v2)

## 1. Project Overview (SMART Goal)
Within 9 weeks, this project will develop and deploy an autonomous watcher system. This system will, every 4 hours, identify, filter, summarize, and report on new, relevant English-language content (including subreddits, posts, and comments) on Reddit related to the configurable topic of "Claude Code." Alerts containing summaries will be delivered to a designated Slack channel and/or email address.

**Responsibilities:**
* **Collect → Filter → Summarise → Alert:** Execute the core data pipeline reliably.
* **Operate Unattended:** Run 24/7 with robust, graceful error-handling.
* **Be Extensible & Observable:** Support future growth and provide clear operational insight.

## 2. Success Criteria & Non-Functional Requirements
To ensure the project meets its strategic objectives, the following specific criteria have been defined:

* **Extensibility:** The architecture must be "trivially extensible," defined as: A new data source (e.g., Twitter, Hacker News) can be fully integrated by a single developer in under two weeks of effort.
* **Observability:** The system must achieve "full observability," defined by the following key metrics:
    * **Uptime:** 99.9%
    * **Latency:** End-to-end data processing (from retrieval to alert) in under 15 minutes.
    * **Error Rate:** Core task failure rate below 1%.
* **Analysis Quality:** Summaries must accurately capture the key point or question of the source content, as judged by human review.

## 3. Target Architecture

```
            +-------------------------+
            |  Cloud Scheduler / Beat | 4-hour trigger
            +-----------+-------------+
                        |
                Celery task chain
                        |
 +----------------+  +---------------+  +--------------+  +--------------+
 | RetrievalAgent |→| FilterAgent   |→| SummariseAgent|→| AlertAgent    |
 +--------+-------+  +-------+------+  +------+-------+  +------+-------+
          |                  |                |                 |
      Reddit API         NLP / LLM      LLM APIs (GenAI)   Slack / E-mail
          |
      Postgres ←———————————————— persistent state & idempotency
```

**Supporting Services & Technologies:**
* **Orchestration:** Celery (with Redis as broker/backend)
* **Storage:** PostgreSQL (durable storage), Alembic (migrations)
* **Development:** Docker/Compose, `uv` (for Python environment/dependency management)
* **CI/CD:** GitHub Actions
* **Testing:** PyTest, pytest-asyncio, `responses`
* **Reddit API:** PRAW
* **Generative AI:** Pluggable interface for OpenAI, Anthropic, and Google Gemini models.
* **Observability:** `structlog` (JSON logging), Prometheus/Grafana (metrics)

## 4. High-Level Timeline & Phases (calendar weeks)

| Wk | Phase                                  | Milestone                                      |
|----|----------------------------------------|------------------------------------------------|
| 1  | **A. Infrastructure** | Repo bootstrap, CI, Docker skeleton            |
| 2  | **B. Persistence** | Data model & migration pipeline                |
| 3  | **C. Agents (Part 1)** | Core Retrieval & Filtering Agents + unit tests |
| 4  | **C. Agents (Part 2)** | Advanced Filtering & Summarisation Agents      |
| 5  | **C. Agents (Part 3)** | Alerting & Idempotency                         |
| 6  | **D. Workflow & Integration** | Celery orchestration & end-to-end tests        |
| 7  | **D. Workflow & Integration** | Risk mitigation and failure-mode testing       |
| 8  | **E. Observability & Ops** | Logging, metrics, and dashboarding             |
| 9  | **F. Finalization** | Documentation, final QA & hand-off           |

## 5. Testing Strategy
1.  **Unit Tests:** 100% test coverage for all pure functions (e.g., parsers, data transformations).
2.  **Contract Tests:** Each agent will be tested against input/output contracts using deterministic fixtures.
3.  **Integration Tests:** The full stack (Postgres, Redis, app) will be spun up in CI to test component interactions with external APIs stubbed.
4.  **End-to-End Tests:** A full 4-hour cycle will be simulated to verify the complete workflow.
5.  **Chaos Engineering Tests:** Scenarios will be tested, such as killing a worker mid-task, to ensure resilience and task retries.

## 6. Risk Assessment

| Risk                                    | Mitigation Strategy (Linked to `todo.md` tasks)           |
|-----------------------------------------|-----------------------------------------------------------|
| Reddit API Quota / Auth Revocation      | Implement a central rate-limiter & auto-refreshing tokens (Task D4). |
| LLM Cost Overrun or API Outage          | Build a pluggable provider interface; create a fallback extractive summarizer (Task C6.2). |
| Missing Idempotency → Alert Spam        | Use processed-ID cursors and enforce DB unique constraints (Task C9). |
| Sudden Data Volume Spike                | Configure Celery for autoscaling; implement back-pressure monitoring (Task E5). |
| Specification Change (New Sources)      | Enforce a strict agent interface contract (Adapter Pattern). |
