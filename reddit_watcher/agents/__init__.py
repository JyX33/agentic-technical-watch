# ABOUTME: Agent implementations for the Reddit Technical Watcher system
# ABOUTME: Contains all A2A agent implementations for retrieval, filtering, summarization, alerting, and coordination

from reddit_watcher.agents.base import (
    BaseA2AAgent,
    BaseA2AAgentExecutor,
    RedditSkillParameters,
)
from reddit_watcher.agents.filter_agent import FilterAgent
from reddit_watcher.agents.retrieval_agent import RetrievalAgent
from reddit_watcher.agents.test_agent import MockA2AAgent

__all__ = [
    "BaseA2AAgent",
    "BaseA2AAgentExecutor",
    "RedditSkillParameters",
    "FilterAgent",
    "RetrievalAgent",
    "MockA2AAgent",
]
