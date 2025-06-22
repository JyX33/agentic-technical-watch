# ABOUTME: Agent coordination and state synchronization for A2A workflows
# ABOUTME: Provides coordination mechanisms, health monitoring, and state synchronization

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .idempotency import get_agent_states, update_agent_state
from .models import A2ATask, AgentState, TaskStatus

logger = logging.getLogger(__name__)


class AgentCoordinator:
    """Coordinates agent state and workflow execution."""

    def __init__(self, session: Session, agent_id: str, agent_type: str):
        self.session = session
        self.agent_id = agent_id
        self.agent_type = agent_type
        self._state_data: dict[str, Any] = {}
        self._heartbeat_interval = 30  # seconds
        self._heartbeat_task: asyncio.Task | None = None

    async def register_agent(
        self, capabilities: list[str], initial_state: dict[str, Any] | None = None
    ) -> None:
        """Register agent with coordination system.

        Args:
            capabilities: List of agent capabilities/skills
            initial_state: Optional initial state data
        """
        agent_state = update_agent_state(
            self.session,
            self.agent_id,
            self.agent_type,
            "idle",
            initial_state or {},
            None,
        )

        agent_state.capabilities = capabilities
        self.session.commit()

        logger.info(
            f"Agent {self.agent_id} registered with capabilities: {capabilities}"
        )

        # Start heartbeat
        await self.start_heartbeat()

    async def start_heartbeat(self) -> None:
        """Start periodic heartbeat to maintain agent liveness."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_heartbeat(self) -> None:
        """Stop heartbeat and mark agent as offline."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        # Mark as offline
        update_agent_state(self.session, self.agent_id, self.agent_type, "offline")
        self.session.commit()

    async def _heartbeat_loop(self) -> None:
        """Internal heartbeat loop."""
        while True:
            try:
                # Update heartbeat
                update_agent_state(
                    self.session,
                    self.agent_id,
                    self.agent_type,
                    self.get_current_status(),
                    self._state_data,
                )
                self.session.commit()

                await asyncio.sleep(self._heartbeat_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error for agent {self.agent_id}: {e}")
                await asyncio.sleep(self._heartbeat_interval)

    def get_current_status(self) -> str:
        """Get current agent status."""
        # This would be overridden by specific agent implementations
        return "idle"

    def update_state(self, state_data: dict[str, Any]) -> None:
        """Update agent state data.

        Args:
            state_data: State data to update
        """
        self._state_data.update(state_data)

        update_agent_state(
            self.session,
            self.agent_id,
            self.agent_type,
            self.get_current_status(),
            self._state_data,
        )
        self.session.commit()

    def start_task(self, task_id: str) -> None:
        """Mark task as started and update agent state.

        Args:
            task_id: Task ID being started
        """
        update_agent_state(
            self.session,
            self.agent_id,
            self.agent_type,
            "busy",
            self._state_data,
            task_id,
        )
        self.session.commit()

        logger.info(f"Agent {self.agent_id} started task {task_id}")

    def complete_task(self, task_id: str, success: bool = True) -> None:
        """Mark task as completed and update agent state.

        Args:
            task_id: Task ID being completed
            success: Whether task completed successfully
        """
        # Update agent state
        agent_state = update_agent_state(
            self.session, self.agent_id, self.agent_type, "idle", self._state_data, None
        )

        # Update performance metrics
        if success:
            agent_state.tasks_completed += 1
        else:
            agent_state.tasks_failed += 1
            agent_state.error_count += 1

        self.session.commit()

        status = "completed" if success else "failed"
        logger.info(f"Agent {self.agent_id} {status} task {task_id}")

    def report_error(self, error_message: str) -> None:
        """Report error and update agent state.

        Args:
            error_message: Error message to report
        """
        agent_state = update_agent_state(
            self.session, self.agent_id, self.agent_type, "error", self._state_data
        )

        agent_state.error_count += 1
        agent_state.last_error = error_message

        self.session.commit()

        logger.error(f"Agent {self.agent_id} reported error: {error_message}")


class WorkflowCoordinator:
    """Coordinates workflow execution across multiple agents."""

    def __init__(self, session: Session):
        self.session = session

    def get_available_agents(
        self,
        agent_type: str | None = None,
        required_capabilities: list[str] | None = None,
    ) -> list[AgentState]:
        """Get available agents for task assignment.

        Args:
            agent_type: Optional filter by agent type
            required_capabilities: Optional required capabilities

        Returns:
            List of available agent states
        """
        agents = get_agent_states(self.session, agent_type, "idle")

        if required_capabilities:
            # Filter by capabilities
            filtered_agents = []
            for agent in agents:
                agent_capabilities = set(agent.capabilities or [])
                required_set = set(required_capabilities)
                if required_set.issubset(agent_capabilities):
                    filtered_agents.append(agent)
            agents = filtered_agents

        # Filter out agents with recent heartbeat (within last 2 minutes)
        cutoff_time = datetime.utcnow() - timedelta(minutes=2)
        active_agents = [
            agent
            for agent in agents
            if agent.heartbeat_at and agent.heartbeat_at > cutoff_time
        ]

        return active_agents

    def assign_task_to_agent(
        self, task: A2ATask, preferred_agent_id: str | None = None
    ) -> str | None:
        """Assign task to an available agent.

        Args:
            task: Task to assign
            preferred_agent_id: Optional preferred agent ID

        Returns:
            Assigned agent ID if successful, None otherwise
        """
        # Try preferred agent first
        if preferred_agent_id:
            agents = get_agent_states(self.session)
            preferred_agent = next(
                (
                    a
                    for a in agents
                    if a.agent_id == preferred_agent_id and a.status == "idle"
                ),
                None,
            )
            if preferred_agent:
                return preferred_agent_id

        # Find available agents of the right type
        available_agents = self.get_available_agents(agent_type=task.agent_type)

        if not available_agents:
            logger.warning(
                f"No available agents for task {task.task_id} of type {task.agent_type}"
            )
            return None

        # Select agent with best performance (lowest error rate)
        best_agent = min(
            available_agents,
            key=lambda a: (
                a.error_count / max(a.tasks_completed + a.tasks_failed, 1),
                a.tasks_completed,  # Prefer more experienced agents
            ),
        )

        return best_agent.agent_id

    def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """Get comprehensive workflow status.

        Args:
            workflow_id: Workflow ID to check

        Returns:
            Workflow status dictionary
        """
        # Get workflow tasks
        query = select(A2ATask).where(A2ATask.workflow_id == workflow_id)
        tasks = list(self.session.execute(query).scalars().all())

        if not tasks:
            return {"status": "not_found", "tasks": []}

        # Calculate status
        status_counts = {}
        for task in tasks:
            status = task.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        # Determine overall status
        if status_counts.get("failed", 0) > 0:
            overall_status = "failed"
        elif status_counts.get("running", 0) > 0:
            overall_status = "running"
        elif status_counts.get("pending", 0) > 0:
            overall_status = "pending"
        elif status_counts.get("completed", 0) == len(tasks):
            overall_status = "completed"
        else:
            overall_status = "unknown"

        return {
            "status": overall_status,
            "total_tasks": len(tasks),
            "status_counts": status_counts,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "agent_type": task.agent_type,
                    "skill_name": task.skill_name,
                    "status": task.status.value,
                    "created_at": task.created_at.isoformat(),
                    "started_at": task.started_at.isoformat()
                    if task.started_at
                    else None,
                    "completed_at": task.completed_at.isoformat()
                    if task.completed_at
                    else None,
                    "error_message": task.error_message,
                }
                for task in tasks
            ],
        }

    def get_agent_health_summary(self) -> dict[str, Any]:
        """Get health summary of all agents.

        Returns:
            Agent health summary
        """
        agents = get_agent_states(self.session)

        # Calculate health metrics
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)

        healthy_agents = []
        unhealthy_agents = []
        offline_agents = []

        for agent in agents:
            if agent.status == "offline":
                offline_agents.append(agent)
            elif agent.heartbeat_at and agent.heartbeat_at > cutoff_time:
                if agent.error_count < 5:  # Threshold for unhealthy
                    healthy_agents.append(agent)
                else:
                    unhealthy_agents.append(agent)
            else:
                offline_agents.append(agent)

        return {
            "total_agents": len(agents),
            "healthy_agents": len(healthy_agents),
            "unhealthy_agents": len(unhealthy_agents),
            "offline_agents": len(offline_agents),
            "agents": [
                {
                    "agent_id": agent.agent_id,
                    "agent_type": agent.agent_type,
                    "status": agent.status,
                    "heartbeat_at": agent.heartbeat_at.isoformat()
                    if agent.heartbeat_at
                    else None,
                    "tasks_completed": agent.tasks_completed,
                    "tasks_failed": agent.tasks_failed,
                    "error_count": agent.error_count,
                    "capabilities": agent.capabilities,
                }
                for agent in agents
            ],
        }

    def cleanup_stale_agents(self, stale_threshold_minutes: int = 10) -> int:
        """Clean up agents that haven't sent heartbeat recently.

        Args:
            stale_threshold_minutes: Minutes before considering agent stale

        Returns:
            Number of agents cleaned up
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=stale_threshold_minutes)

        query = select(AgentState).where(
            and_(AgentState.heartbeat_at < cutoff_time, AgentState.status != "offline")
        )

        stale_agents = list(self.session.execute(query).scalars().all())

        for agent in stale_agents:
            agent.status = "offline"

        if stale_agents:
            self.session.commit()
            logger.info(f"Marked {len(stale_agents)} stale agents as offline")

        return len(stale_agents)


class TaskDistributor:
    """Distributes tasks across available agents with load balancing."""

    def __init__(self, session: Session):
        self.session = session
        self.workflow_coordinator = WorkflowCoordinator(session)

    def distribute_workflow_tasks(
        self, workflow_id: str, tasks: list[dict[str, Any]]
    ) -> list[str]:
        """Distribute workflow tasks across available agents.

        Args:
            workflow_id: Workflow ID
            tasks: List of task definitions

        Returns:
            List of created task IDs
        """
        from .idempotency import create_idempotent_task

        created_task_ids = []

        for task_def in tasks:
            # Create idempotent task
            task, is_new = create_idempotent_task(
                self.session,
                agent_type=task_def["agent_type"],
                skill_name=task_def["skill_name"],
                parameters=task_def["parameters"],
                workflow_id=workflow_id,
                priority=task_def.get("priority", 5),
            )

            if is_new:
                logger.info(
                    f"Created new task {task.task_id} for workflow {workflow_id}"
                )
            else:
                logger.info(
                    f"Reusing existing task {task.task_id} for workflow {workflow_id}"
                )

            created_task_ids.append(task.task_id)

        self.session.commit()
        return created_task_ids

    def get_next_task_for_agent(
        self, agent_id: str, agent_type: str, capabilities: list[str]
    ) -> A2ATask | None:
        """Get next task for agent to execute.

        Args:
            agent_id: Agent ID requesting task
            agent_type: Agent type
            capabilities: Agent capabilities

        Returns:
            Next task to execute or None if no tasks available
        """
        # Find pending tasks for this agent type
        query = (
            select(A2ATask)
            .where(
                and_(
                    A2ATask.agent_type == agent_type,
                    A2ATask.status == TaskStatus.PENDING,
                    A2ATask.lock_token.is_(None),  # Not locked
                )
            )
            .order_by(A2ATask.priority.asc(), A2ATask.created_at.asc())
        )

        tasks = list(self.session.execute(query).scalars().all())

        # Filter by capabilities if needed
        for task in tasks:
            # Check if agent has required capabilities for this task
            # This could be enhanced with more sophisticated capability matching
            return task

        return None
