This document breaks down the implementation plan into granular, testable steps intended for code generation.

*Owner assignments are placeholders and should be updated by the project lead.*

---

## Step 1: Repository Bootstrap
- **Phase Task:** A1
- **Owner:** `@developer_A`
- **Estimated Time:** 2 hours
### Context
New project. Need a reproducible Python environment, linting, and a CI scaffold.
### Requirements
1.  Initialize a Git repo with `uv` for Python 3.12+ project and dependency management.
2.  Add a basic package structure (`reddit_watcher/__init__.py`).
3.  Configure `pre-commit` with `ruff` (for linting and formatting).
4.  Add standard `.editorconfig` & `.gitignore`.
5.  Provide a GitHub Actions workflow that installs `uv`, syncs dependencies, and runs `pytest`.
### Prompt for Code Generation:
```
Create a minimal Python 3.11 project named "reddit-watcher" managed by `uv`. The project should be configured with `pre-commit` using `ruff`. Include a GitHub Actions workflow that installs dependencies with `uv pip sync` and runs `pytest`. Add one empty test file `tests/test_smoke.py` that asserts `True is True`.
```

---

## Step 2: Docker-Compose Baseline
- **Phase Task:** A2
- **Owner:** `@developer_A`
- **Estimated Time:** 3 hours
### Context
Repo exists. Need local stack for Postgres, Redis, Mailhog, and app worker.
### Requirements
1.  `docker-compose.yml` with services: db (postgres:15), redis (redis:7), mailhog, and watcher_app.
2.  `Dockerfile` (slim, multi-stage) that installs Python dependencies using `uv`.
3.  `Makefile` target `make dev` to spin up the stack.
### Prompt for Code Generation:
```
Add a multi-stage Dockerfile and a docker-compose.yml as specified. The watcher_app service should build from the local Dockerfile. Add a GNU Makefile with a `dev` target executing `docker compose up --build -d`. The watcher_app image must copy the project source and run `uv pip sync requirements.txt`.
```

---

## Step 3: Configuration Module
- **Phase Task:** A3
- **Owner:** `@developer_A`
- **Estimated Time:** 2 hours
### Context
Running stack; need unified settings and secrets loader.
### Requirements
1.  Create `reddit_watcher/config.py` using Pydantic `BaseSettings`.
2.  Expose all necessary parameters with `.env` overrides (DB URI, Redis URL, etc.).
3.  Implement as a `settings = Settings()` singleton.
### Prompt for Code Generation:
```
Implement the Pydantic settings module described. Provide a unit test `tests/test_config.py` that temporarily writes an `.env.test` file, sets `os.environ["ENV_FILE"]`, and verifies that defaults are correctly overridden.
```

---

## Step 4: Celery Core & Scheduler
- **Phase Task:** A4
- **Owner:** `@developer_A`
- **Estimated Time:** 3 hours
### Context
Settings available, infra running.
### Requirements
1.  Add `reddit_watcher/celery_app.py` factory.
2.  Configure with Redis broker/backend and autodiscover tasks.
3.  Add `celeryconfig.py` with sane defaults.
4.  Provide a beat schedule to trigger the main workflow every 4 hours.
### Prompt for Code Generation:
```
Add Celery support as outlined, including a beat schedule in `celeryconfig.py`. Provide a smoke test `tests/test_celery.py` that starts an in-memory Celery worker and asserts the scheduled task is registered.
```

---

## Step 5: SQLAlchemy Models
- **Phase Task:** B1
- **Owner:** `@developer_B`
- **Estimated Time:** 4 hours
### Context
Database container live. Need data models.
### Requirements
1.  Create `reddit_watcher/db/models.py` with SQLAlchemy 2.0 DeclarativeBase.
2.  Define all tables: `subreddits`, `posts`, `comments`, `summaries`, `alerts`, `cursors`.
3.  Add unit tests for model creation and foreign key integrity.
### Prompt for Code Generation:
```
Implement SQLAlchemy models and a unit test that uses a temporary postgres instance (via `pytest-postgresql`) to verify that tables are created and basic insert/select operations work as expected.
```

---

## Step 6: Alembic Migration Pipeline
- **Phase Task:** B2
- **Owner:** `@developer_B`
- **Estimated Time:** 2 hours
### Context
Models done; need repeatable migrations.
### Requirements
1.  Configure `alembic.ini` and `alembic/env.py` to target the models.
2.  Autogenerate the initial revision `0001_initial`.
3.  Add `make migrate` helper to `Makefile`.
### Prompt for Code Generation:
```
Bootstrap Alembic as described. Provide a GitHub Actions step calling `make migrate` to ensure migrations can be applied cleanly against the service database.
```

---

## Step 7: Retrieval Agent – Posts
- **Phase Task:** C1
- **Owner:** `@developer_B`
- **Estimated Time:** 5 hours
### Context
DB & Celery up. Start with posts retrieval.
### Requirements
1.  Implement `RedditRetrievalAgent` in `reddit_watcher/agents/retrieval.py`.
2.  Method `fetch_new_posts(topic: str)` using PRAW.
3.  Honor and update a cursor from the DB to prevent re-fetching.
4.  Wrap as Celery task `tasks.retrieve_posts`.
### Prompt for Code Generation:
```
Code the RedditRetrievalAgent and its Celery task as specified, with thorough unit tests mocking the PRAW library. Use environment variables for Reddit credentials.
```

---

## Step 8: Retrieval Agent – Comments & Subreddits
- **Phase Task:** C2 & C3
- **Owner:** `@developer_B`
- **Estimated Time:** 4 hours
### Context
Posts retrieval handled; expand coverage.
### Requirements
1.  Extend agent with `fetch_new_comments` for stored posts.
2.  Implement `discover_new_subreddits(topic)` via subreddit search.
3.  Wrap both as Celery tasks, sharing cursor/idempotency logic.
### Prompt for Code Generation:
```
Add the two additional retrieval functions and Celery tasks. Refactor the agent to ensure deduplication and cursor logic is common and not repeated (DRY).
```

---

## Step 9: Filter Agent – Keyword v1
- **Phase Task:** C4
- **Owner:** `@developer_C`
- **Estimated Time:** 3 hours
### Context
Have raw data. Need initial relevance filter.
### Requirements
1.  `FilterAgent.keyword_relevance(text: str, topic_keywords: list[str]) -> bool`.
2.  Celery task `tasks.filter_items` to process items and return a list of relevant IDs.
### Prompt for Code Generation:
```
Create the keyword-based FilterAgent and unit tests. Use parametrized fixtures to test various edge cases (case insensitivity, substring noise, etc.).
```

---

## Step 10: Filter Agent – Semantic v2
- **Phase Task:** C5
- **Owner:** `@developer_C`
- **Estimated Time:** 5 hours
### Context
Need higher precision filtering.
### Requirements
1.  Integrate `sentence-transformers` (e.g., `all-MiniLM-L6-v2`).
2.  `semantic_score(text, topic_description) -> float` method.
3.  Filter items based on a configurable similarity score threshold.
### Prompt for Code Generation:
```
Augment the FilterAgent with semantic scoring capability. Use dependency injection so the embedding model can be easily mocked in tests. Provide tests that assert the scoring threshold behavior.
```

---

## Step 11: Summarisation Agent
- **Phase Task:** C6
- **Owner:** `@developer_B`
- **Estimated Time:** 8 hours
### Context
Relevant content IDs are available. Need to generate concise summaries.
### Requirements
1.  Implement `SummariseAgent.generate_summary(text: str)`.
2.  The agent must be pluggable to support multiple LLM providers (OpenAI, Anthropic, Google Gemini).
3.  Use a client wrapper (e.g., `litellm`) to abstract API calls to models like `gpt-4-turbo`, `claude-3-opus`, and `gemini-1.5-pro`.
4.  Handle context windows >8k tokens via recursive chunking logic.
5.  Wrap as a Celery task `tasks.summarise_items` that reads relevant content IDs and saves `Summary` rows to the database.
### Prompt for Code Generation:
```
Implement a `SummariseAgent` with a Celery task. The agent should use a library like `litellm` to support multiple LLM providers (OpenAI, Anthropic, Gemini) via a single interface. Implement recursive summarisation for texts exceeding the model's context window. Provide dependency-injected clients so tests can stub the LLM calls. Include unit tests for the chunk-splitting and aggregation logic.
```

---

## Step 12: AlertAgent – Slack
- **Phase Task:** C7
- **Owner:** `@developer_C`
- **Estimated Time:** 3 hours
### Context
Summaries are saved. Need to send alerts.
### Requirements
1.  `AlertAgent.send_slack(summary_id)` using an Incoming Webhook URL.
2.  Format a clear, concise message with summary and link.
3.  Mark an `Alert` row in DB to prevent re-sending.
### Prompt for Code Generation:
```
Write the Slack AlertAgent. Provide a PyTest using the `responses` library to fake the webhook endpoint and assert the correct payload is sent.
```

---

## Step 13: Idempotency Guard
- **Phase Task:** C9
- **Owner:** `@developer_B`
- **Estimated Time:** 3 hours
### Context
Prevent duplicate processing and alerts.
### Requirements
1.  Add a unique constraint to `summaries.source_id`.
2.  Implement upsert logic in the summariser agent.
3.  Add a unique constraint on `(summary_id, channel)` in the alerts table.
### Prompt for Code Generation:
```
Add a new Alembic migration to implement the database uniqueness constraints. Update agents with idempotent upsert helpers and add regression tests that simulate duplicate processing.
```

---

## Step 14: Celery Pipeline Integration
- **Phase Task:** D1
- **Owner:** `@developer_A`
- **Estimated Time:** 4 hours
### Context
All atomic tasks exist. Need to wire them together.
### Requirements
1.  Define the complete workflow in `tasks.schedule_cycle` using a Celery chain or chord.
   a) `retrieve_posts.s() | group(retrieve_comments.s(), discover_subreddits.s()) | filter_items.s() | summarise_items.s() | alert.s()`
### Prompt for Code Generation:
```
Compose the Celery chain as outlined. Provide an integration test using an in-memory Celery worker and a temporary database to validate the end-to-end flow completes successfully.
```

---

## Step 15: Structured Logging
- **Phase Task:** E1
- **Owner:** `@developer_A`
- **Estimated Time:** 3 hours
### Context
Need production-grade, observable logs.
### Requirements
1.  Configure `structlog` with a JSON renderer.
2.  Include `task_id`, `agent`, and other relevant context in all logs.
3.  Add a decorator to auto-inject Celery task context into logs.
### Prompt for Code Generation:
```
Set up a `structlog` configuration. Provide a decorator for Celery tasks and write tests using `caplog` to assert that the extra context fields are present in the log output.
```

---

## Step 16: Final Release & Documentation
- **Phase Task:** F1
- **Owner:** `@developer_A`
- **Estimated Time:** 6 hours
### Context
Project is functional. Need to prepare for hand-off.
### Requirements
1.  Harden the `Dockerfile` for production (non-root user, etc.).
2.  Create a comprehensive `README.md` with setup, configuration, and deployment instructions.
3.  Ensure all code is documented with comments and docstrings.
### Prompt for Code Generation:
```
Refactor the Dockerfile to be multi-stage and add a non-root user. Generate a template for the README.md file that includes sections for Installation, Configuration, Running Locally, and Deployment.
