# ABOUTME: CoordinatorAgent for orchestrating the complete Reddit monitoring workflow
# ABOUTME: Implements A2A task delegation to other agents with error handling, retries, and audit logging

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp
from sqlalchemy import and_, desc

from reddit_watcher.a2a_protocol import AgentSkill
from reddit_watcher.agents.base import BaseA2AAgent
from reddit_watcher.database.utils import get_db_session
from reddit_watcher.models import (
    AgentTask,
    ContentFilter,
    RedditPost,
    WorkflowExecution,
)

logger = logging.getLogger(__name__)


class CoordinatorAgent(BaseA2AAgent):
    """
    CoordinatorAgent for orchestrating the complete Reddit monitoring workflow.

    Implements A2A skills for:
    - Coordinating the complete monitoring cycle
    - Delegating tasks to specialized agents
    - Managing workflow state and recovery
    - Comprehensive audit logging
    - Error handling and retry logic
    """

    def __init__(self):
        super().__init__(
            agent_type="coordinator",
            name="Workflow Coordinator Agent",
            description="Orchestrates the complete Reddit monitoring workflow via A2A task delegation",
            version="1.0.0",
        )

        # Agent endpoints for delegation
        self._agent_endpoints = {
            "retrieval": f"http://localhost:{self.settings.a2a_port + 1}",
            "filter": f"http://localhost:{self.settings.a2a_port + 2}",
            "summarise": f"http://localhost:{self.settings.a2a_port + 3}",
            "alert": f"http://localhost:{self.settings.a2a_port + 4}",
        }

        # HTTP session for A2A communication
        self._http_session: aiohttp.ClientSession | None = None

        # Retry configuration
        self._max_retries = 3
        self._retry_delay = 30  # seconds
        self._timeout = 300  # 5 minutes

    async def _ensure_http_session(self) -> aiohttp.ClientSession:
        """Ensure HTTP session is initialized for A2A communication."""
        if not self._http_session or self._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._http_session = aiohttp.ClientSession(timeout=timeout)
        return self._http_session

    async def _cleanup_http_session(self) -> None:
        """Cleanup HTTP session resources."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

    def get_skills(self) -> list[AgentSkill]:
        """Return list of skills this agent can perform."""
        return [
            AgentSkill(
                id="health_check",
                name="health_check",
                description="Check coordinator health and agent connectivity",
                tags=["health", "status", "coordination"],
                inputModes=["text/plain", "application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="run_monitoring_cycle",
                name="run_monitoring_cycle",
                description="Execute complete monitoring cycle: retrieve -> filter -> summarise -> alert",
                tags=["workflow", "monitoring", "orchestration"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="check_agent_status",
                name="check_agent_status",
                description="Check health status of all managed agents",
                tags=["health", "agents", "status"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="recover_failed_workflow",
                name="recover_failed_workflow",
                description="Recover from a failed workflow execution",
                tags=["recovery", "workflow", "error"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="get_workflow_status",
                name="get_workflow_status",
                description="Get status of current or recent workflow executions",
                tags=["workflow", "status", "monitoring"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
        ]

    async def execute_skill(
        self, skill_name: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a specific skill with given parameters."""
        if skill_name == "health_check":
            return await self._health_check(parameters)
        elif skill_name == "run_monitoring_cycle":
            return await self._run_monitoring_cycle(parameters)
        elif skill_name == "check_agent_status":
            return await self._check_agent_status(parameters)
        elif skill_name == "recover_failed_workflow":
            return await self._recover_failed_workflow(parameters)
        elif skill_name == "get_workflow_status":
            return await self._get_workflow_status(parameters)
        else:
            raise ValueError(f"Unknown skill: {skill_name}")

    async def _health_check(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Check coordinator health and agent connectivity."""
        health_status = self.get_common_health_status()

        # Check agent connectivity
        agent_status = {}
        for agent_name, endpoint in self._agent_endpoints.items():
            try:
                status = await self._check_single_agent_health(agent_name, endpoint)
                agent_status[agent_name] = status
            except Exception as e:
                agent_status[agent_name] = {
                    "status": "error",
                    "error": str(e),
                    "endpoint": endpoint,
                }

        # Check recent workflow executions
        workflow_status = await self._get_recent_workflow_status()

        health_status["coordinator_specific"] = {
            "managed_agents": list(self._agent_endpoints.keys()),
            "agent_status": agent_status,
            "recent_workflows": workflow_status,
            "http_session_active": self._http_session is not None
            and not self._http_session.closed,
        }

        return {
            "skill": "health_check",
            "status": "success",
            "result": health_status,
        }

    async def _check_single_agent_health(
        self, agent_name: str, endpoint: str
    ) -> dict[str, Any]:
        """Check health of a single agent."""
        session = await self._ensure_http_session()

        try:
            async with session.get(f"{endpoint}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    return {
                        "status": "healthy",
                        "endpoint": endpoint,
                        "response_time": "< 1s",
                        "details": health_data,
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "endpoint": endpoint,
                        "http_status": response.status,
                        "error": f"HTTP {response.status}",
                    }
        except TimeoutError:
            return {
                "status": "timeout",
                "endpoint": endpoint,
                "error": "Health check timed out",
            }
        except Exception as e:
            return {
                "status": "error",
                "endpoint": endpoint,
                "error": str(e),
            }

    async def _get_recent_workflow_status(self) -> dict[str, Any]:
        """Get recent workflow execution status."""
        try:
            with get_db_session() as session:
                recent_workflows = (
                    session.query(WorkflowExecution)
                    .order_by(desc(WorkflowExecution.started_at))
                    .limit(5)
                    .all()
                )

                workflow_summaries = []
                for workflow in recent_workflows:
                    workflow_summaries.append(
                        {
                            "id": workflow.id,
                            "status": workflow.status,
                            "started_at": workflow.started_at.isoformat(),
                            "completed_at": workflow.completed_at.isoformat()
                            if workflow.completed_at
                            else None,
                            "duration_seconds": (
                                workflow.completed_at - workflow.started_at
                            ).total_seconds()
                            if workflow.completed_at
                            else None,
                            "posts_processed": workflow.posts_processed,
                            "comments_processed": workflow.comments_processed,
                        }
                    )

                return {
                    "recent_count": len(workflow_summaries),
                    "workflows": workflow_summaries,
                }

        except Exception as e:
            logger.error(f"Error getting recent workflow status: {e}")
            return {"error": str(e)}

    async def _run_monitoring_cycle(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute complete monitoring cycle."""
        topics = parameters.get("topics", self.settings.reddit_topics)
        subreddits = parameters.get("subreddits", ["all"])
        # force_run = parameters.get("force_run", False)  # TODO: Implement forced execution

        if not topics:
            return {
                "skill": "run_monitoring_cycle",
                "status": "error",
                "error": "No topics configured for monitoring",
            }

        # Create workflow execution record
        workflow_id = await self._create_workflow_execution(topics, subreddits)

        try:
            logger.info(f"Starting monitoring cycle workflow {workflow_id}")
            await self._log_workflow_event(
                workflow_id,
                "workflow_started",
                {"topics": topics, "subreddits": subreddits},
            )

            # Step 1: Retrieve Reddit content
            retrieval_result = await self._execute_retrieval_tasks(
                workflow_id, topics, subreddits
            )

            if retrieval_result["status"] != "success":
                await self._mark_workflow_failed(
                    workflow_id,
                    "retrieval_failed",
                    retrieval_result.get("error", "Unknown error"),
                )
                return {
                    "skill": "run_monitoring_cycle",
                    "status": "error",
                    "error": f"Retrieval failed: {retrieval_result.get('error')}",
                    "workflow_id": workflow_id,
                }

            # Step 2: Filter content for relevance
            filter_result = await self._execute_filter_tasks(
                workflow_id, retrieval_result["result"]
            )

            if filter_result["status"] != "success":
                await self._mark_workflow_failed(
                    workflow_id,
                    "filter_failed",
                    filter_result.get("error", "Unknown error"),
                )
                return {
                    "skill": "run_monitoring_cycle",
                    "status": "error",
                    "error": f"Filtering failed: {filter_result.get('error')}",
                    "workflow_id": workflow_id,
                }

            # Step 3: Summarise relevant content
            summarise_result = await self._execute_summarise_tasks(
                workflow_id, filter_result["result"]
            )

            if summarise_result["status"] != "success":
                # Don't fail workflow for summarisation errors, just log
                await self._log_workflow_event(
                    workflow_id, "summarise_partial_failure", summarise_result
                )

            # Step 4: Send alerts for important content
            alert_result = await self._execute_alert_tasks(
                workflow_id, filter_result["result"], summarise_result.get("result")
            )

            if alert_result["status"] != "success":
                # Don't fail workflow for alert errors, just log
                await self._log_workflow_event(
                    workflow_id, "alert_partial_failure", alert_result
                )

            # Mark workflow as completed
            await self._mark_workflow_completed(
                workflow_id,
                retrieval_result["result"],
                filter_result["result"],
                summarise_result.get("result"),
                alert_result.get("result"),
            )

            logger.info(
                f"Monitoring cycle workflow {workflow_id} completed successfully"
            )

            return {
                "skill": "run_monitoring_cycle",
                "status": "success",
                "result": {
                    "workflow_id": workflow_id,
                    "topics": topics,
                    "subreddits": subreddits,
                    "retrieval_result": retrieval_result["result"],
                    "filter_result": filter_result["result"],
                    "summarise_result": summarise_result.get("result"),
                    "alert_result": alert_result.get("result"),
                    "completed_at": datetime.now(UTC).isoformat(),
                },
            }

        except Exception as e:
            logger.error(
                f"Monitoring cycle workflow {workflow_id} failed: {e}", exc_info=True
            )
            await self._mark_workflow_failed(workflow_id, "unexpected_error", str(e))
            return {
                "skill": "run_monitoring_cycle",
                "status": "error",
                "error": str(e),
                "workflow_id": workflow_id,
            }

    async def _create_workflow_execution(
        self, topics: list[str], subreddits: list[str]
    ) -> int:
        """Create a new workflow execution record."""
        try:
            with get_db_session() as session:
                workflow = WorkflowExecution(
                    topics=topics,
                    subreddits=subreddits,
                    status="running",
                    started_at=datetime.now(UTC),
                )
                session.add(workflow)
                session.commit()
                return workflow.id
        except Exception as e:
            logger.error(f"Error creating workflow execution: {e}")
            raise

    async def _log_workflow_event(
        self, workflow_id: int, event_type: str, event_data: dict[str, Any]
    ) -> None:
        """Log a workflow event for audit purposes."""
        try:
            with get_db_session() as session:
                task = AgentTask(
                    workflow_id=workflow_id,
                    agent_type="coordinator",
                    task_type=event_type,
                    task_data=event_data,
                    status="completed",
                    created_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                )
                session.add(task)
                session.commit()
        except Exception as e:
            logger.error(f"Error logging workflow event: {e}")

    async def _execute_retrieval_tasks(
        self, workflow_id: int, topics: list[str], subreddits: list[str]
    ) -> dict[str, Any]:
        """Execute retrieval tasks via A2A delegation."""
        await self._log_workflow_event(
            workflow_id,
            "retrieval_started",
            {"topics": topics, "subreddits": subreddits},
        )

        all_posts = []
        total_posts = 0
        successful_retrievals = 0
        failed_retrievals = 0

        try:
            for topic in topics:
                for subreddit in subreddits:
                    # Delegate to RetrievalAgent
                    task_params = {
                        "skill": "fetch_posts_by_topic",
                        "parameters": {
                            "topic": topic,
                            "subreddit": subreddit,
                            "limit": 50,
                            "time_range": "day",
                        },
                    }

                    result = await self._delegate_to_agent(
                        "retrieval", task_params, workflow_id
                    )

                    if result["status"] == "success":
                        topic_posts = result["result"]["posts_stored"]
                        total_posts += topic_posts
                        all_posts.extend(result["result"].get("posts", []))
                        successful_retrievals += 1

                        await self._log_workflow_event(
                            workflow_id,
                            "retrieval_topic_completed",
                            {
                                "topic": topic,
                                "subreddit": subreddit,
                                "posts_found": topic_posts,
                            },
                        )
                    else:
                        failed_retrievals += 1
                        await self._log_workflow_event(
                            workflow_id,
                            "retrieval_topic_failed",
                            {
                                "topic": topic,
                                "subreddit": subreddit,
                                "error": result.get("error"),
                            },
                        )

            await self._log_workflow_event(
                workflow_id, "retrieval_completed", {"total_posts": total_posts}
            )

            # If all retrievals failed, consider it a failure
            if successful_retrievals == 0 and failed_retrievals > 0:
                return {"status": "error", "error": "All retrieval attempts failed"}

            return {
                "status": "success",
                "result": {"total_posts": total_posts, "posts": all_posts},
            }

        except Exception as e:
            await self._log_workflow_event(
                workflow_id, "retrieval_failed", {"error": str(e)}
            )
            return {"status": "error", "error": str(e)}

    async def _execute_filter_tasks(
        self, workflow_id: int, retrieval_result: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute filtering tasks via A2A delegation."""
        total_posts = retrieval_result.get("total_posts", 0)

        if total_posts == 0:
            return {
                "status": "success",
                "result": {"relevant_posts": 0, "relevant_comments": 0},
            }

        await self._log_workflow_event(
            workflow_id, "filter_started", {"posts_to_filter": total_posts}
        )

        try:
            # Get recent posts from database for filtering
            with get_db_session() as session:
                recent_posts = (
                    session.query(RedditPost)
                    .filter(
                        RedditPost.created_at >= datetime.now(UTC) - timedelta(hours=24)
                    )
                    .all()
                )

                post_ids = [post.id for post in recent_posts]

            # Batch filter posts
            if post_ids:
                filter_params = {
                    "skill": "batch_filter_posts",
                    "parameters": {
                        "post_ids": post_ids,
                        "use_semantic": True,
                    },
                }

                filter_result = await self._delegate_to_agent(
                    "filter", filter_params, workflow_id
                )

                if filter_result["status"] == "success":
                    relevant_posts = filter_result["result"]["relevant"]

                    await self._log_workflow_event(
                        workflow_id,
                        "filter_completed",
                        {
                            "posts_processed": filter_result["result"]["processed"],
                            "relevant_posts": relevant_posts,
                        },
                    )

                    return {
                        "status": "success",
                        "result": {
                            "relevant_posts": relevant_posts,
                            "relevant_comments": 0,  # Will be implemented later
                            "filter_details": filter_result["result"],
                        },
                    }
                else:
                    return {"status": "error", "error": filter_result.get("error")}
            else:
                return {
                    "status": "success",
                    "result": {"relevant_posts": 0, "relevant_comments": 0},
                }

        except Exception as e:
            await self._log_workflow_event(
                workflow_id, "filter_failed", {"error": str(e)}
            )
            return {"status": "error", "error": str(e)}

    async def _execute_summarise_tasks(
        self, workflow_id: int, filter_result: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute summarisation tasks via A2A delegation."""
        relevant_posts = filter_result.get("relevant_posts", 0)

        if relevant_posts == 0:
            return {"status": "success", "result": {"summaries_created": 0}}

        await self._log_workflow_event(
            workflow_id, "summarise_started", {"relevant_posts": relevant_posts}
        )

        try:
            # Get relevant posts for summarisation
            with get_db_session() as session:
                relevant_filters = (
                    session.query(ContentFilter)
                    .filter(
                        and_(
                            ContentFilter.is_relevant,
                            ContentFilter.created_at
                            >= datetime.now(UTC) - timedelta(hours=24),
                        )
                    )
                    .limit(10)  # Limit to top 10 most relevant
                    .all()
                )

                if relevant_filters:
                    # Get the posts to summarise
                    post_ids = [f.post_id for f in relevant_filters if f.post_id]
                    posts = (
                        session.query(RedditPost)
                        .filter(RedditPost.id.in_(post_ids))
                        .all()
                    )

                    summaries_created = 0
                    for post in posts:
                        summarise_params = {
                            "skill": "summarize_content",
                            "parameters": {
                                "title": post.title,
                                "content": post.content,
                                "url": post.url,
                                "metadata": {
                                    "subreddit": post.subreddit,
                                    "author": post.author,
                                    "score": post.score,
                                },
                            },
                        }

                        result = await self._delegate_to_agent(
                            "summarise", summarise_params, workflow_id
                        )

                        if result["status"] == "success":
                            summaries_created += 1

                    await self._log_workflow_event(
                        workflow_id,
                        "summarise_completed",
                        {"summaries_created": summaries_created},
                    )

                    return {
                        "status": "success",
                        "result": {"summaries_created": summaries_created},
                    }

            return {"status": "success", "result": {"summaries_created": 0}}

        except Exception as e:
            await self._log_workflow_event(
                workflow_id, "summarise_failed", {"error": str(e)}
            )
            return {"status": "error", "error": str(e)}

    async def _execute_alert_tasks(
        self,
        workflow_id: int,
        filter_result: dict[str, Any],
        summarise_result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Execute alert tasks via A2A delegation."""
        relevant_posts = filter_result.get("relevant_posts", 0)

        if relevant_posts == 0:
            return {"status": "success", "result": {"alerts_sent": 0}}

        await self._log_workflow_event(
            workflow_id, "alert_started", {"relevant_posts": relevant_posts}
        )

        try:
            # Send summary alert if there are relevant posts
            alert_params = {
                "skill": "send_summary_alert",
                "parameters": {
                    "relevant_posts": relevant_posts,
                    "summaries_created": summarise_result.get("summaries_created", 0)
                    if summarise_result
                    else 0,
                    "monitoring_topics": self.settings.reddit_topics,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }

            result = await self._delegate_to_agent("alert", alert_params, workflow_id)

            if result["status"] == "success":
                await self._log_workflow_event(
                    workflow_id, "alert_completed", {"alerts_sent": 1}
                )
                return {"status": "success", "result": {"alerts_sent": 1}}
            else:
                return {"status": "error", "error": result.get("error")}

        except Exception as e:
            await self._log_workflow_event(
                workflow_id, "alert_failed", {"error": str(e)}
            )
            return {"status": "error", "error": str(e)}

    async def _delegate_to_agent(
        self, agent_name: str, task_params: dict[str, Any], workflow_id: int
    ) -> dict[str, Any]:
        """Delegate a task to a specific agent via A2A protocol."""
        endpoint = self._agent_endpoints.get(agent_name)
        if not endpoint:
            raise ValueError(f"Unknown agent: {agent_name}")

        session = await self._ensure_http_session()
        retries = 0

        while retries <= self._max_retries:
            try:
                # Create agent task record
                task_id = await self._create_agent_task(
                    workflow_id, agent_name, task_params
                )

                # Make A2A request
                async with session.post(
                    f"{endpoint}/execute", json=task_params
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        await self._complete_agent_task(task_id, "completed", result)
                        return result
                    else:
                        error_text = await response.text()
                        error_msg = f"HTTP {response.status}: {error_text}"

                        if retries < self._max_retries:
                            logger.warning(
                                f"Agent {agent_name} request failed (attempt {retries + 1}): {error_msg}"
                            )
                            await self._update_agent_task(
                                task_id,
                                "retrying",
                                {"error": error_msg, "attempt": retries + 1},
                            )
                            await asyncio.sleep(self._retry_delay)
                            retries += 1
                            continue
                        else:
                            await self._complete_agent_task(
                                task_id, "failed", {"error": error_msg}
                            )
                            return {"status": "error", "error": error_msg}

            except TimeoutError:
                error_msg = f"Timeout communicating with {agent_name} agent"
                if retries < self._max_retries:
                    logger.warning(f"{error_msg} (attempt {retries + 1})")
                    await self._update_agent_task(
                        task_id,
                        "retrying",
                        {"error": error_msg, "attempt": retries + 1},
                    )
                    await asyncio.sleep(self._retry_delay)
                    retries += 1
                    continue
                else:
                    await self._complete_agent_task(
                        task_id, "failed", {"error": error_msg}
                    )
                    return {"status": "error", "error": error_msg}

            except Exception as e:
                error_msg = f"Error communicating with {agent_name} agent: {str(e)}"
                if retries < self._max_retries:
                    logger.warning(f"{error_msg} (attempt {retries + 1})")
                    await self._update_agent_task(
                        task_id,
                        "retrying",
                        {"error": error_msg, "attempt": retries + 1},
                    )
                    await asyncio.sleep(self._retry_delay)
                    retries += 1
                    continue
                else:
                    await self._complete_agent_task(
                        task_id, "failed", {"error": error_msg}
                    )
                    return {"status": "error", "error": error_msg}

    async def _create_agent_task(
        self, workflow_id: int, agent_name: str, task_params: dict[str, Any]
    ) -> int:
        """Create an agent task record."""
        try:
            with get_db_session() as session:
                task = AgentTask(
                    workflow_id=workflow_id,
                    agent_type=agent_name,
                    task_type=task_params.get("skill", "unknown"),
                    task_data=task_params,
                    status="pending",
                    created_at=datetime.now(UTC),
                )
                session.add(task)
                session.commit()
                return task.id
        except Exception as e:
            logger.error(f"Error creating agent task: {e}")
            raise

    async def _update_agent_task(
        self, task_id: int, status: str, result_data: dict[str, Any]
    ) -> None:
        """Update an agent task record."""
        try:
            with get_db_session() as session:
                task = session.query(AgentTask).filter_by(id=task_id).first()
                if task:
                    task.status = status
                    task.result_data = result_data
                    task.updated_at = datetime.now(UTC)
                    session.commit()
        except Exception as e:
            logger.error(f"Error updating agent task: {e}")

    async def _complete_agent_task(
        self, task_id: int, status: str, result_data: dict[str, Any]
    ) -> None:
        """Complete an agent task record."""
        try:
            with get_db_session() as session:
                task = session.query(AgentTask).filter_by(id=task_id).first()
                if task:
                    task.status = status
                    task.result_data = result_data
                    task.completed_at = datetime.now(UTC)
                    session.commit()
        except Exception as e:
            logger.error(f"Error completing agent task: {e}")

    async def _mark_workflow_completed(
        self,
        workflow_id: int,
        retrieval_result: dict[str, Any],
        filter_result: dict[str, Any],
        summarise_result: dict[str, Any] | None,
        alert_result: dict[str, Any] | None,
    ) -> None:
        """Mark workflow as completed."""
        try:
            with get_db_session() as session:
                workflow = (
                    session.query(WorkflowExecution).filter_by(id=workflow_id).first()
                )
                if workflow:
                    workflow.status = "completed"
                    workflow.completed_at = datetime.now(UTC)
                    workflow.posts_processed = retrieval_result.get("total_posts", 0)
                    workflow.comments_processed = (
                        0  # TODO: Implement comment processing
                    )
                    workflow.relevant_items = filter_result.get("relevant_posts", 0)
                    workflow.summaries_created = (
                        summarise_result.get("summaries_created", 0)
                        if summarise_result
                        else 0
                    )
                    workflow.alerts_sent = (
                        alert_result.get("alerts_sent", 0) if alert_result else 0
                    )
                    session.commit()
        except Exception as e:
            logger.error(f"Error marking workflow completed: {e}")

    async def _mark_workflow_failed(
        self, workflow_id: int, failure_reason: str, error_message: str
    ) -> None:
        """Mark workflow as failed."""
        try:
            with get_db_session() as session:
                workflow = (
                    session.query(WorkflowExecution).filter_by(id=workflow_id).first()
                )
                if workflow:
                    workflow.status = "failed"
                    workflow.completed_at = datetime.now(UTC)
                    workflow.error_message = f"{failure_reason}: {error_message}"
                    session.commit()
        except Exception as e:
            logger.error(f"Error marking workflow failed: {e}")

    async def _check_agent_status(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Check health status of all managed agents."""
        agent_status = {}

        for agent_name, endpoint in self._agent_endpoints.items():
            try:
                status = await self._check_single_agent_health(agent_name, endpoint)
                agent_status[agent_name] = status
            except Exception as e:
                agent_status[agent_name] = {
                    "status": "error",
                    "error": str(e),
                    "endpoint": endpoint,
                }

        # Calculate overall health
        healthy_agents = sum(
            1 for status in agent_status.values() if status.get("status") == "healthy"
        )
        total_agents = len(agent_status)

        return {
            "skill": "check_agent_status",
            "status": "success",
            "result": {
                "total_agents": total_agents,
                "healthy_agents": healthy_agents,
                "health_percentage": (healthy_agents / total_agents) * 100
                if total_agents > 0
                else 0,
                "agent_details": agent_status,
            },
        }

    async def _recover_failed_workflow(
        self, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Recover from a failed workflow execution."""
        workflow_id = parameters.get("workflow_id")

        if not workflow_id:
            return {
                "skill": "recover_failed_workflow",
                "status": "error",
                "error": "workflow_id parameter is required",
            }

        try:
            with get_db_session() as session:
                workflow = (
                    session.query(WorkflowExecution).filter_by(id=workflow_id).first()
                )

                if not workflow:
                    return {
                        "skill": "recover_failed_workflow",
                        "status": "error",
                        "error": f"Workflow {workflow_id} not found",
                    }

                if workflow.status != "failed":
                    return {
                        "skill": "recover_failed_workflow",
                        "status": "error",
                        "error": f"Workflow {workflow_id} is not in failed state",
                    }

                # Restart the workflow with the same parameters
                recovery_params = {
                    "topics": workflow.topics,
                    "subreddits": workflow.subreddits,
                    "force_run": True,
                }

                # Mark old workflow as recovered
                workflow.status = "recovered"
                session.commit()

                # Start new workflow
                result = await self._run_monitoring_cycle(recovery_params)

                return {
                    "skill": "recover_failed_workflow",
                    "status": "success",
                    "result": {
                        "recovered_workflow_id": workflow_id,
                        "new_workflow_result": result,
                    },
                }

        except Exception as e:
            logger.error(f"Error recovering workflow {workflow_id}: {e}")
            return {
                "skill": "recover_failed_workflow",
                "status": "error",
                "error": str(e),
            }

    async def _get_workflow_status(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Get status of current or recent workflow executions."""
        limit = min(parameters.get("limit", 10), 50)
        status_filter = parameters.get("status")  # Optional status filter

        try:
            with get_db_session() as session:
                query = session.query(WorkflowExecution).order_by(
                    desc(WorkflowExecution.started_at)
                )

                if status_filter:
                    query = query.filter(WorkflowExecution.status == status_filter)

                workflows = query.limit(limit).all()

                workflow_status = []
                for workflow in workflows:
                    status_info = {
                        "id": workflow.id,
                        "status": workflow.status,
                        "topics": workflow.topics,
                        "subreddits": workflow.subreddits,
                        "started_at": workflow.started_at.isoformat(),
                        "completed_at": workflow.completed_at.isoformat()
                        if workflow.completed_at
                        else None,
                        "duration_seconds": (
                            workflow.completed_at - workflow.started_at
                        ).total_seconds()
                        if workflow.completed_at
                        else (datetime.now(UTC) - workflow.started_at).total_seconds(),
                        "posts_processed": workflow.posts_processed,
                        "comments_processed": workflow.comments_processed,
                        "relevant_items": workflow.relevant_items,
                        "summaries_created": workflow.summaries_created,
                        "alerts_sent": workflow.alerts_sent,
                        "error_message": workflow.error_message,
                    }
                    workflow_status.append(status_info)

                return {
                    "skill": "get_workflow_status",
                    "status": "success",
                    "result": {
                        "workflows": workflow_status,
                        "total_count": len(workflow_status),
                    },
                }

        except Exception as e:
            logger.error(f"Error getting workflow status: {e}")
            return {
                "skill": "get_workflow_status",
                "status": "error",
                "error": str(e),
            }

    def get_health_status(self) -> dict[str, Any]:
        """Get detailed health status for this agent."""
        base_health = self.get_common_health_status()

        coordinator_health = {
            "managed_agents": list(self._agent_endpoints.keys()),
            "http_session_active": self._http_session is not None
            and not self._http_session.closed,
            "retry_configuration": {
                "max_retries": self._max_retries,
                "retry_delay": self._retry_delay,
                "timeout": self._timeout,
            },
        }

        base_health["coordinator_specific"] = coordinator_health
        return base_health

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_http_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._cleanup_http_session()


if __name__ == "__main__":
    import asyncio

    from .server import A2AAgentServer

    async def main():
        agent = CoordinatorAgent()
        server = A2AAgentServer(agent)
        await server.start_server()

    asyncio.run(main())
