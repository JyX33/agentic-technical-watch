# ABOUTME: RetrievalAgent for Reddit data fetching using PRAW
# ABOUTME: Implements A2A skills for posts, comments, and subreddit discovery with rate limiting

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import praw
from praw.exceptions import APIException, ClientException, RedditAPIException
from praw.models import Comment, Submission, Subreddit

from reddit_watcher.a2a_protocol import AgentSkill
from reddit_watcher.agents.base import BaseA2AAgent
from reddit_watcher.config import Settings
from reddit_watcher.database.utils import get_db_session
from reddit_watcher.models import RedditComment, RedditPost
from reddit_watcher.models import Subreddit as SubredditModel

logger = logging.getLogger(__name__)


class RetrievalAgent(BaseA2AAgent):
    """
    RetrievalAgent for fetching Reddit data using PRAW.

    Implements A2A skills for:
    - Fetching Reddit posts by topic
    - Fetching comments from posts
    - Discovering new subreddits
    - Managing rate limits and error handling
    """

    def __init__(self, config: Settings):
        super().__init__(
            config=config,
            agent_type="retrieval",
            name="Reddit Retrieval Agent",
            description="Fetches Reddit posts, comments, and discovers subreddits using PRAW",
            version="1.0.0",
        )

        # Initialize Reddit client
        self._reddit_client = None
        self._initialize_reddit_client()

        # Rate limiting
        self._last_request_time = datetime.now(UTC)
        self._min_request_interval = (
            60 / self.config.reddit_rate_limit
        )  # seconds between requests

    def _initialize_reddit_client(self) -> None:
        """Initialize PRAW Reddit client with authentication."""
        try:
            if not self.config.has_reddit_credentials():
                logger.warning("Reddit credentials not configured")
                return

            self._reddit_client = praw.Reddit(
                client_id=self.config.reddit_client_id,
                client_secret=self.config.reddit_client_secret,
                user_agent=self.config.reddit_user_agent,
                ratelimit_seconds=300,  # Wait up to 5 minutes for rate limits
                timeout=30,
            )

            # Test authentication
            try:
                # This should not fail for read-only access
                self._reddit_client.read_only = True
                logger.info("Reddit client initialized successfully (read-only)")
            except Exception as e:
                logger.error(f"Reddit client authentication failed: {e}")
                self._reddit_client = None

        except Exception as e:
            logger.error(f"Failed to initialize Reddit client: {e}")
            self._reddit_client = None

    async def _ensure_rate_limit(self) -> None:
        """Ensure we don't exceed Reddit API rate limits."""
        current_time = datetime.now(UTC)
        time_since_last = (current_time - self._last_request_time).total_seconds()

        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            await asyncio.sleep(sleep_time)

        self._last_request_time = datetime.now(UTC)

    def get_skills(self) -> list[AgentSkill]:
        """Return list of skills this agent can perform."""
        return [
            AgentSkill(
                id="health_check",
                name="health_check",
                description="Check agent health and Reddit API connectivity",
                tags=["health", "status", "reddit"],
                inputModes=["text/plain", "application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="fetch_posts_by_topic",
                name="fetch_posts_by_topic",
                description="Fetch Reddit posts related to a specific topic",
                tags=["reddit", "posts", "search"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="fetch_comments_from_post",
                name="fetch_comments_from_post",
                description="Fetch comments from a specific Reddit post",
                tags=["reddit", "comments"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="discover_subreddits",
                name="discover_subreddits",
                description="Discover subreddits related to monitored topics",
                tags=["reddit", "subreddits", "discovery"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="fetch_subreddit_info",
                name="fetch_subreddit_info",
                description="Get information about a specific subreddit",
                tags=["reddit", "subreddits", "info"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
        ]

    async def execute_skill(self, skill_name: str, parameters: dict) -> dict[str, Any]:
        """Execute a specific skill with given parameters."""
        if skill_name == "health_check":
            return await self._health_check(parameters)
        elif skill_name == "fetch_posts_by_topic":
            return await self._fetch_posts_by_topic(parameters)
        elif skill_name == "fetch_comments_from_post":
            return await self._fetch_comments_from_post(parameters)
        elif skill_name == "discover_subreddits":
            return await self._discover_subreddits(parameters)
        elif skill_name == "fetch_subreddit_info":
            return await self._fetch_subreddit_info(parameters)
        else:
            raise ValueError(f"Unknown skill: {skill_name}")

    async def _health_check(self, parameters: dict) -> dict[str, Any]:
        """Check agent health and Reddit API connectivity."""
        health_status = self.get_common_health_status()

        # Check Reddit client status
        reddit_status = {
            "initialized": self._reddit_client is not None,
            "credentials_configured": self.config.has_reddit_credentials(),
            "rate_limit": self.config.reddit_rate_limit,
        }

        if self._reddit_client:
            try:
                # Test API connectivity with a simple request
                await asyncio.to_thread(self._test_reddit_connectivity)
                reddit_status["connectivity"] = "ok"
                reddit_status["read_only"] = self._reddit_client.read_only
            except Exception as e:
                reddit_status["connectivity"] = "failed"
                reddit_status["error"] = str(e)
        else:
            reddit_status["connectivity"] = "not_initialized"

        health_status["reddit"] = reddit_status
        return {
            "skill": "health_check",
            "status": "success",
            "result": health_status,
        }

    def _test_reddit_connectivity(self) -> None:
        """Test Reddit API connectivity (sync method for thread execution)."""
        if not self._reddit_client:
            raise RuntimeError("Reddit client not initialized")

        # Simple test request
        subreddit = self._reddit_client.subreddit("test")
        _ = subreddit.display_name  # This should trigger an API call

    async def _fetch_posts_by_topic(self, parameters: dict) -> dict[str, Any]:
        """Fetch Reddit posts related to a specific topic."""
        if not self._reddit_client:
            return {
                "skill": "fetch_posts_by_topic",
                "status": "error",
                "error": "Reddit client not initialized",
            }

        topic = parameters.get("topic", "")
        subreddit_name = parameters.get("subreddit", "all")
        limit = min(parameters.get("limit", 25), 100)  # Cap at 100
        time_range = parameters.get("time_range", "day")

        if not topic:
            return {
                "skill": "fetch_posts_by_topic",
                "status": "error",
                "error": "Topic parameter is required",
            }

        try:
            # Ensure rate limiting before executing Reddit API calls in thread
            await self._ensure_rate_limit()
            posts_data = await asyncio.to_thread(
                self._search_posts_sync, topic, subreddit_name, limit, time_range
            )

            # Store posts in database
            stored_count = await self._store_posts_in_db(posts_data, topic)

            return {
                "skill": "fetch_posts_by_topic",
                "status": "success",
                "result": {
                    "topic": topic,
                    "subreddit": subreddit_name,
                    "posts_found": len(posts_data),
                    "posts_stored": stored_count,
                    "time_range": time_range,
                    "posts": posts_data[:10],  # Return first 10 for preview
                },
            }

        except Exception as e:
            logger.error(f"Error fetching posts for topic '{topic}': {e}")
            return {
                "skill": "fetch_posts_by_topic",
                "status": "error",
                "error": str(e),
            }

    def _search_posts_sync(
        self, topic: str, subreddit_name: str, limit: int, time_range: str
    ) -> list[dict]:
        """Search Reddit posts synchronously (for thread execution)."""

        try:
            subreddit = self._reddit_client.subreddit(subreddit_name)

            # Search for posts containing the topic
            posts_data = []
            search_results = subreddit.search(
                topic, sort="new", time_filter=time_range, limit=limit
            )

            for submission in search_results:
                post_data = self._extract_post_data(submission)
                posts_data.append(post_data)

        except (APIException, ClientException, RedditAPIException) as e:
            logger.error(f"Reddit API error during search: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Reddit search: {e}")
            raise

        return posts_data

    def _extract_post_data(self, submission: Submission) -> dict:
        """Extract relevant data from a Reddit submission."""
        return {
            "post_id": submission.id,
            "title": submission.title,
            "content": submission.selftext if submission.is_self else "",
            "url": submission.url,
            "author": str(submission.author) if submission.author else "[deleted]",
            "subreddit": str(submission.subreddit),
            "created_utc": submission.created_utc,
            "score": submission.score,
            "upvote_ratio": submission.upvote_ratio,
            "num_comments": submission.num_comments,
            "is_self": submission.is_self,
            "is_video": submission.is_video,
            "over_18": submission.over_18,
            "permalink": submission.permalink,
        }

    async def _store_posts_in_db(self, posts_data: list[dict], topic: str) -> int:
        """Store Reddit posts in database."""
        stored_count = 0

        try:
            with get_db_session() as session:
                for post_data in posts_data:
                    # Check if post already exists
                    existing_post = (
                        session.query(RedditPost)
                        .filter_by(post_id=post_data["post_id"])
                        .first()
                    )

                    if not existing_post:
                        # Create new post record
                        reddit_post = RedditPost(
                            post_id=post_data["post_id"],
                            title=post_data["title"],
                            content=post_data["content"],
                            url=post_data["url"],
                            author=post_data["author"],
                            subreddit=post_data["subreddit"],
                            created_utc=datetime.fromtimestamp(
                                post_data["created_utc"], UTC
                            ),
                            score=post_data["score"],
                            upvote_ratio=post_data["upvote_ratio"],
                            num_comments=post_data["num_comments"],
                            is_self=post_data["is_self"],
                            is_video=post_data["is_video"],
                            over_18=post_data["over_18"],
                            permalink=post_data["permalink"],
                            topic=topic,
                        )
                        session.add(reddit_post)
                        stored_count += 1

                session.commit()

        except Exception as e:
            logger.error(f"Error storing posts in database: {e}")

        return stored_count

    async def _fetch_comments_from_post(self, parameters: dict) -> dict[str, Any]:
        """Fetch comments from a specific Reddit post."""
        if not self._reddit_client:
            return {
                "skill": "fetch_comments_from_post",
                "status": "error",
                "error": "Reddit client not initialized",
            }

        post_id = parameters.get("post_id", "")
        limit = min(parameters.get("limit", 50), 200)  # Cap at 200

        if not post_id:
            return {
                "skill": "fetch_comments_from_post",
                "status": "error",
                "error": "post_id parameter is required",
            }

        try:
            await self._ensure_rate_limit()
            comments_data = await asyncio.to_thread(
                self._fetch_comments_sync, post_id, limit
            )

            stored_count = await self._store_comments_in_db(comments_data, post_id)

            return {
                "skill": "fetch_comments_from_post",
                "status": "success",
                "result": {
                    "post_id": post_id,
                    "comments_found": len(comments_data),
                    "comments_stored": stored_count,
                    "comments": comments_data[:20],  # Return first 20 for preview
                },
            }

        except Exception as e:
            logger.error(f"Error fetching comments for post '{post_id}': {e}")
            return {
                "skill": "fetch_comments_from_post",
                "status": "error",
                "error": str(e),
            }

    def _fetch_comments_sync(self, post_id: str, limit: int) -> list[dict]:
        """Fetch comments from a post synchronously."""

        try:
            submission = self._reddit_client.submission(id=post_id)
            submission.comments.replace_more(limit=0)  # Remove MoreComments objects

            comments_data = []
            for comment in submission.comments.list()[:limit]:
                if isinstance(comment, Comment):
                    comment_data = self._extract_comment_data(comment, post_id)
                    comments_data.append(comment_data)

        except (APIException, ClientException, RedditAPIException) as e:
            logger.error(f"Reddit API error during comment fetch: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during comment fetch: {e}")
            raise

        return comments_data

    def _extract_comment_data(self, comment: Comment, post_id: str) -> dict:
        """Extract relevant data from a Reddit comment."""
        return {
            "comment_id": comment.id,
            "post_id": post_id,
            "body": comment.body,
            "author": str(comment.author) if comment.author else "[deleted]",
            "created_utc": comment.created_utc,
            "score": comment.score,
            "parent_id": comment.parent_id,
            "permalink": comment.permalink,
            "is_submitter": comment.is_submitter,
        }

    async def _store_comments_in_db(
        self, comments_data: list[dict], post_id: str
    ) -> int:
        """Store Reddit comments in database."""
        stored_count = 0

        try:
            with get_db_session() as session:
                for comment_data in comments_data:
                    # Check if comment already exists
                    existing_comment = (
                        session.query(RedditComment)
                        .filter_by(comment_id=comment_data["comment_id"])
                        .first()
                    )

                    if not existing_comment:
                        reddit_comment = RedditComment(
                            comment_id=comment_data["comment_id"],
                            post_id=comment_data["post_id"],
                            body=comment_data["body"],
                            author=comment_data["author"],
                            created_utc=datetime.fromtimestamp(
                                comment_data["created_utc"], UTC
                            ),
                            score=comment_data["score"],
                            parent_id=comment_data["parent_id"],
                            permalink=comment_data["permalink"],
                            is_submitter=comment_data["is_submitter"],
                        )
                        session.add(reddit_comment)
                        stored_count += 1

                session.commit()

        except Exception as e:
            logger.error(f"Error storing comments in database: {e}")

        return stored_count

    async def _discover_subreddits(self, parameters: dict) -> dict[str, Any]:
        """Discover subreddits related to monitored topics."""
        if not self._reddit_client:
            return {
                "skill": "discover_subreddits",
                "status": "error",
                "error": "Reddit client not initialized",
            }

        topic = parameters.get("topic", "")
        limit = min(parameters.get("limit", 10), 25)  # Cap at 25

        if not topic:
            return {
                "skill": "discover_subreddits",
                "status": "error",
                "error": "Topic parameter is required",
            }

        try:
            await self._ensure_rate_limit()
            subreddits_data = await asyncio.to_thread(
                self._search_subreddits_sync, topic, limit
            )

            stored_count = await self._store_subreddits_in_db(subreddits_data, topic)

            return {
                "skill": "discover_subreddits",
                "status": "success",
                "result": {
                    "topic": topic,
                    "subreddits_found": len(subreddits_data),
                    "subreddits_stored": stored_count,
                    "subreddits": subreddits_data,
                },
            }

        except Exception as e:
            logger.error(f"Error discovering subreddits for topic '{topic}': {e}")
            return {
                "skill": "discover_subreddits",
                "status": "error",
                "error": str(e),
            }

    def _search_subreddits_sync(self, topic: str, limit: int) -> list[dict]:
        """Search for subreddits synchronously."""

        try:
            subreddits_data = []
            search_results = self._reddit_client.subreddits.search(topic, limit=limit)

            for subreddit in search_results:
                subreddit_data = self._extract_subreddit_data(subreddit)
                subreddits_data.append(subreddit_data)

        except (APIException, ClientException, RedditAPIException) as e:
            logger.error(f"Reddit API error during subreddit search: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during subreddit search: {e}")
            raise

        return subreddits_data

    def _extract_subreddit_data(self, subreddit: Subreddit) -> dict:
        """Extract relevant data from a Reddit subreddit."""
        return {
            "name": subreddit.display_name,
            "title": subreddit.title or "",
            "description": subreddit.public_description or "",
            "subscribers": subreddit.subscribers or 0,
            "created_utc": subreddit.created_utc,
            "over_18": subreddit.over18,
            "lang": getattr(subreddit, "lang", "en"),
        }

    async def _store_subreddits_in_db(
        self, subreddits_data: list[dict], topic: str
    ) -> int:
        """Store discovered subreddits in database."""
        stored_count = 0

        try:
            with get_db_session() as session:
                for subreddit_data in subreddits_data:
                    # Check if subreddit already exists
                    existing_subreddit = (
                        session.query(SubredditModel)
                        .filter_by(name=subreddit_data["name"])
                        .first()
                    )

                    if not existing_subreddit:
                        subreddit_model = SubredditModel(
                            name=subreddit_data["name"],
                            display_name=subreddit_data["title"],
                            description=subreddit_data["description"],
                            subscribers=subreddit_data["subscribers"],
                        )
                        session.add(subreddit_model)
                        stored_count += 1

                session.commit()

        except Exception as e:
            logger.error(f"Error storing subreddits in database: {e}")

        return stored_count

    async def _fetch_subreddit_info(self, parameters: dict) -> dict[str, Any]:
        """Get information about a specific subreddit."""
        if not self._reddit_client:
            return {
                "skill": "fetch_subreddit_info",
                "status": "error",
                "error": "Reddit client not initialized",
            }

        subreddit_name = parameters.get("subreddit_name", "")

        if not subreddit_name:
            return {
                "skill": "fetch_subreddit_info",
                "status": "error",
                "error": "subreddit_name parameter is required",
            }

        try:
            await self._ensure_rate_limit()
            subreddit_data = await asyncio.to_thread(
                self._get_subreddit_info_sync, subreddit_name
            )

            return {
                "skill": "fetch_subreddit_info",
                "status": "success",
                "result": {
                    "subreddit_name": subreddit_name,
                    "info": subreddit_data,
                },
            }

        except Exception as e:
            logger.error(f"Error fetching subreddit info for '{subreddit_name}': {e}")
            return {
                "skill": "fetch_subreddit_info",
                "status": "error",
                "error": str(e),
            }

    def _get_subreddit_info_sync(self, subreddit_name: str) -> dict:
        """Get subreddit information synchronously."""

        try:
            subreddit = self._reddit_client.subreddit(subreddit_name)
            return self._extract_subreddit_data(subreddit)

        except (APIException, ClientException, RedditAPIException) as e:
            logger.error(f"Reddit API error during subreddit info fetch: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during subreddit info fetch: {e}")
            raise

    def get_health_status(self) -> dict[str, Any]:
        """Get detailed health status for this agent."""
        base_health = self.get_common_health_status()

        retrieval_health = {
            "reddit_client_initialized": self._reddit_client is not None,
            "reddit_credentials": self.config.has_reddit_credentials(),
            "rate_limit_rpm": self.config.reddit_rate_limit,
            "min_request_interval": self._min_request_interval,
        }

        if self._reddit_client:
            retrieval_health["reddit_read_only"] = self._reddit_client.read_only

        base_health["retrieval_specific"] = retrieval_health
        return base_health


if __name__ == "__main__":
    import asyncio

    from .server import A2AAgentServer

    async def main():
        agent = RetrievalAgent()
        server = A2AAgentServer(agent)
        await server.start_server()

    asyncio.run(main())
