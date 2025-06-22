# ABOUTME: FilterAgent for content relevance assessment using keyword matching and semantic similarity
# ABOUTME: Implements A2A skills for filtering Reddit posts and comments based on configured topics

import asyncio
import logging
import re
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from reddit_watcher.a2a_protocol import AgentSkill
from reddit_watcher.agents.base import BaseA2AAgent
from reddit_watcher.config import Settings
from reddit_watcher.database.utils import get_db_session
from reddit_watcher.models import ContentFilter, RedditComment, RedditPost
from reddit_watcher.performance.decorators import agent_skill_monitor, ml_model_monitor
from reddit_watcher.performance.ml_model_cache import get_model_cache

logger = logging.getLogger(__name__)


class FilterAgent(BaseA2AAgent):
    """
    FilterAgent for assessing content relevance using keyword matching and semantic similarity.

    Implements A2A skills for:
    - Filtering content by keyword matching
    - Computing semantic similarity scores
    - Batch processing of posts and comments
    - Relevance assessment with configurable thresholds
    """

    def __init__(self, config: Settings):
        super().__init__(
            config=config,
            agent_type="filter",
            name="Content Filter Agent",
            description="Assesses content relevance using keyword matching and semantic similarity",
            version="1.0.0",
        )

        # Use optimized ML model cache
        self._model_cache = get_model_cache()
        self._semantic_model: SentenceTransformer | None = None

        # Cache for topic embeddings to avoid recomputation
        self._topic_embeddings: dict[str, np.ndarray] = {}

    async def _ensure_semantic_model(self) -> SentenceTransformer:
        """Ensure semantic similarity model is loaded with optimization."""
        if self._semantic_model is None:
            self._semantic_model = await self._model_cache.get_sentence_transformer(
                model_name="all-MiniLM-L6-v2", use_gpu=True
            )
        return self._semantic_model

    def get_skills(self) -> list[AgentSkill]:
        """Return list of skills this agent can perform."""
        return [
            AgentSkill(
                id="health_check",
                name="health_check",
                description="Check agent health and semantic model status",
                tags=["health", "status", "semantic"],
                inputModes=["text/plain", "application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="filter_content_by_keywords",
                name="filter_content_by_keywords",
                description="Filter content using keyword matching against configured topics",
                tags=["filter", "keywords", "relevance"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="filter_content_by_semantic_similarity",
                name="filter_content_by_semantic_similarity",
                description="Filter content using semantic similarity scoring",
                tags=["filter", "semantic", "similarity", "ai"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="batch_filter_posts",
                name="batch_filter_posts",
                description="Batch filter multiple Reddit posts with combined scoring",
                tags=["filter", "batch", "posts", "reddit"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="batch_filter_comments",
                name="batch_filter_comments",
                description="Batch filter multiple Reddit comments with combined scoring",
                tags=["filter", "batch", "comments", "reddit"],
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
        elif skill_name == "filter_content_by_keywords":
            return await self._filter_content_by_keywords(parameters)
        elif skill_name == "filter_content_by_semantic_similarity":
            return await self._filter_content_by_semantic_similarity(parameters)
        elif skill_name == "batch_filter_posts":
            return await self._batch_filter_posts(parameters)
        elif skill_name == "batch_filter_comments":
            return await self._batch_filter_comments(parameters)
        else:
            raise ValueError(f"Unknown skill: {skill_name}")

    async def _health_check(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Check agent health and semantic model status."""
        health_status = self.get_common_health_status()

        # Check semantic model status
        semantic_status = {
            "model_initialized": self._semantic_model is not None,
            "cached_embeddings": len(self._topic_embeddings),
            "configured_topics": self.config.reddit_topics,
            "relevance_threshold": self.config.relevance_threshold,
        }

        if self._semantic_model:
            try:
                # Test model with a simple sentence
                test_embedding = await asyncio.to_thread(
                    self._semantic_model.encode, ["test sentence"]
                )
                semantic_status["model_status"] = "operational"
                semantic_status["embedding_dimension"] = len(test_embedding[0])
            except Exception as e:
                semantic_status["model_status"] = "error"
                semantic_status["model_error"] = str(e)
        else:
            semantic_status["model_status"] = "not_initialized"

        health_status["filter_specific"] = semantic_status
        return {
            "skill": "health_check",
            "status": "success",
            "result": health_status,
        }

    async def _filter_content_by_keywords(
        self, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Filter content using keyword matching."""
        content = parameters.get("content", "")
        title = parameters.get("title", "")
        topics = parameters.get("topics", self.config.reddit_topics)

        if not content and not title:
            return {
                "skill": "filter_content_by_keywords",
                "status": "error",
                "error": "Either content or title parameter is required",
            }

        try:
            # Combine title and content for matching
            combined_text = f"{title} {content}".strip()

            # Perform keyword matching
            match_results = await asyncio.to_thread(
                self._match_keywords, combined_text, topics
            )

            return {
                "skill": "filter_content_by_keywords",
                "status": "success",
                "result": {
                    "content_length": len(combined_text),
                    "topics_checked": topics,
                    "keywords_matched": match_results["matched_keywords"],
                    "match_score": match_results["match_score"],
                    "is_relevant": match_results["match_score"] > 0,
                    "match_details": match_results["match_details"],
                },
            }

        except Exception as e:
            logger.error(f"Error in keyword filtering: {e}")
            return {
                "skill": "filter_content_by_keywords",
                "status": "error",
                "error": str(e),
            }

    def _match_keywords(self, text: str, topics: list[str]) -> dict[str, Any]:
        """Perform keyword matching against topics."""
        text_lower = text.lower()
        matched_keywords = []
        match_details = {}
        total_matches = 0

        for topic in topics:
            topic_lower = topic.lower()
            topic_matches = []

            # Direct substring match
            if topic_lower in text_lower:
                topic_matches.append(
                    {
                        "type": "exact",
                        "term": topic,
                        "positions": self._find_positions(text_lower, topic_lower),
                    }
                )
                total_matches += len(self._find_positions(text_lower, topic_lower))

            # Word boundary match (more precise)
            word_pattern = r"\b" + re.escape(topic_lower) + r"\b"
            word_matches = list(re.finditer(word_pattern, text_lower))
            if word_matches:
                topic_matches.append(
                    {"type": "word_boundary", "term": topic, "count": len(word_matches)}
                )
                total_matches += len(word_matches)

            # Individual word matching for multi-word topics
            if " " in topic:
                words = topic_lower.split()
                word_match_count = 0
                for word in words:
                    if len(word) > 2:  # Skip short words
                        word_pattern = r"\b" + re.escape(word) + r"\b"
                        if re.search(word_pattern, text_lower):
                            word_match_count += 1

                if word_match_count > 0:
                    topic_matches.append(
                        {
                            "type": "partial_words",
                            "term": topic,
                            "words_matched": word_match_count,
                            "total_words": len(words),
                            "match_ratio": word_match_count / len(words),
                        }
                    )
                    total_matches += word_match_count

            if topic_matches:
                matched_keywords.append(topic)
                match_details[topic] = topic_matches

        # Calculate match score (0.0 to 1.0)
        match_score = min(total_matches / 10.0, 1.0)  # Normalize to max 1.0

        return {
            "matched_keywords": matched_keywords,
            "match_score": match_score,
            "total_matches": total_matches,
            "match_details": match_details,
        }

    def _find_positions(self, text: str, pattern: str) -> list[int]:
        """Find all positions of pattern in text."""
        positions = []
        start = 0
        while True:
            pos = text.find(pattern, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1
        return positions

    @agent_skill_monitor()
    @ml_model_monitor("sentence_transformer")
    async def _filter_content_by_semantic_similarity(
        self, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Filter content using semantic similarity with optimized model cache."""
        content = parameters.get("content", "")
        title = parameters.get("title", "")
        topics = parameters.get("topics", self.config.reddit_topics)

        if not content and not title:
            return {
                "skill": "filter_content_by_semantic_similarity",
                "status": "error",
                "error": "Either content or title parameter is required",
            }

        try:
            # Ensure model is loaded
            model = await self._ensure_semantic_model()

            # Combine title and content
            combined_text = f"{title} {content}".strip()

            # Compute semantic similarity with optimization
            similarity_results = await self._compute_semantic_similarity_optimized(
                combined_text, topics, model
            )

            return {
                "skill": "filter_content_by_semantic_similarity",
                "status": "success",
                "result": {
                    "content_length": len(combined_text),
                    "topics_checked": topics,
                    "max_similarity": similarity_results["max_similarity"],
                    "best_topic": similarity_results["best_topic"],
                    "topic_similarities": similarity_results["topic_similarities"],
                    "is_relevant": similarity_results["max_similarity"]
                    >= self.config.relevance_threshold,
                    "threshold_used": self.config.relevance_threshold,
                },
            }

        except Exception as e:
            logger.error(f"Error in semantic similarity filtering: {e}")
            return {
                "skill": "filter_content_by_semantic_similarity",
                "status": "error",
                "error": str(e),
            }

    async def _compute_semantic_similarity_optimized(
        self, text: str, topics: list[str], model: SentenceTransformer
    ) -> dict[str, Any]:
        """Compute semantic similarity between text and topics with optimization."""
        # Use optimized encoding from model cache
        text_embeddings = await self._model_cache.encode_texts_optimized(
            model, [text], batch_size=1
        )
        text_embedding = text_embeddings[0].reshape(1, -1)

        # Get or compute topic embeddings using optimized encoding
        topic_similarities = {}
        max_similarity = 0.0
        best_topic = None

        # Get all missing topic embeddings in batch for efficiency
        missing_topics = [
            topic for topic in topics if topic not in self._topic_embeddings
        ]
        if missing_topics:
            topic_embeddings = await self._model_cache.encode_texts_optimized(
                model, missing_topics, batch_size=32
            )
            for i, topic in enumerate(missing_topics):
                self._topic_embeddings[topic] = topic_embeddings[i]

        # Compute similarities
        for topic in topics:
            topic_embedding = self._topic_embeddings[topic].reshape(1, -1)

            # Compute cosine similarity
            similarity = cosine_similarity(text_embedding, topic_embedding)[0][0]
            topic_similarities[topic] = float(similarity)

            if similarity > max_similarity:
                max_similarity = similarity
                best_topic = topic

        return {
            "max_similarity": float(max_similarity),
            "best_topic": best_topic,
            "topic_similarities": topic_similarities,
        }

    def _compute_semantic_similarity(
        self, text: str, topics: list[str]
    ) -> dict[str, Any]:
        """Legacy method - kept for backward compatibility."""
        # Fallback to synchronous computation if needed
        if not self._semantic_model:
            raise RuntimeError("Semantic model not initialized")

        # Encode the input text
        text_embedding = self._semantic_model.encode([text])

        # Get or compute topic embeddings
        topic_similarities = {}
        max_similarity = 0.0
        best_topic = None

        for topic in topics:
            if topic not in self._topic_embeddings:
                # Cache topic embedding (keep as 1D array)
                self._topic_embeddings[topic] = self._semantic_model.encode([topic])[0]

            # Reshape both to 2D for cosine_similarity
            topic_embedding = self._topic_embeddings[topic].reshape(1, -1)

            # Compute cosine similarity
            similarity = cosine_similarity(text_embedding, topic_embedding)[0][0]
            topic_similarities[topic] = float(similarity)

            if similarity > max_similarity:
                max_similarity = similarity
                best_topic = topic

        return {
            "max_similarity": float(max_similarity),
            "best_topic": best_topic,
            "topic_similarities": topic_similarities,
        }

    async def _batch_filter_posts(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Batch filter multiple Reddit posts."""
        post_ids = parameters.get("post_ids", [])
        topics = parameters.get("topics", self.config.reddit_topics)
        use_semantic = parameters.get("use_semantic", True)

        if not post_ids:
            return {
                "skill": "batch_filter_posts",
                "status": "error",
                "error": "post_ids parameter is required",
            }

        try:
            results = {
                "total_posts": len(post_ids),
                "processed": 0,
                "relevant": 0,
                "stored": 0,
                "details": [],
            }

            with get_db_session() as session:
                for post_id in post_ids:
                    # Get post from database
                    if isinstance(post_id, int):
                        post = session.query(RedditPost).filter_by(id=post_id).first()
                    else:
                        post = (
                            session.query(RedditPost).filter_by(post_id=post_id).first()
                        )

                    if not post:
                        logger.warning(f"Post not found: {post_id}")
                        continue

                    # Check if already filtered
                    existing_filter = (
                        session.query(ContentFilter).filter_by(post_id=post.id).first()
                    )
                    if existing_filter:
                        logger.debug(f"Post {post_id} already filtered, skipping")
                        continue

                    # Process the post
                    filter_result = await self._process_single_post(
                        post, topics, use_semantic
                    )

                    # Store result in database
                    content_filter = ContentFilter(
                        post_id=post.id,
                        relevance_score=filter_result["relevance_score"],
                        is_relevant=filter_result["is_relevant"],
                        keywords_matched=filter_result["keywords_matched"],
                        semantic_similarity=filter_result.get("semantic_similarity"),
                        filter_reason=filter_result["filter_reason"],
                    )
                    session.add(content_filter)
                    session.commit()

                    results["processed"] += 1
                    results["stored"] += 1
                    if filter_result["is_relevant"]:
                        results["relevant"] += 1

                    # Add to details (limit to first 10)
                    if len(results["details"]) < 10:
                        results["details"].append(
                            {
                                "post_id": post.post_id,
                                "title": post.title[:60] + "..."
                                if len(post.title) > 60
                                else post.title,
                                "relevance_score": filter_result["relevance_score"],
                                "is_relevant": filter_result["is_relevant"],
                                "keywords_matched": filter_result["keywords_matched"],
                            }
                        )

            return {
                "skill": "batch_filter_posts",
                "status": "success",
                "result": results,
            }

        except Exception as e:
            logger.error(f"Error in batch post filtering: {e}")
            return {
                "skill": "batch_filter_posts",
                "status": "error",
                "error": str(e),
            }

    async def _process_single_post(
        self, post: RedditPost, topics: list[str], use_semantic: bool
    ) -> dict[str, Any]:
        """Process a single post for filtering."""
        combined_text = f"{post.title} {post.content}".strip()

        # Keyword matching
        keyword_results = await asyncio.to_thread(
            self._match_keywords, combined_text, topics
        )

        semantic_similarity = 0.0
        if use_semantic and self._semantic_model:
            try:
                semantic_results = await asyncio.to_thread(
                    self._compute_semantic_similarity, combined_text, topics
                )
                semantic_similarity = semantic_results["max_similarity"]
            except Exception as e:
                logger.warning(
                    f"Semantic similarity failed for post {post.post_id}: {e}"
                )

        # Combine scores (70% keyword, 30% semantic)
        keyword_weight = 0.7
        semantic_weight = 0.3
        relevance_score = (keyword_results["match_score"] * keyword_weight) + (
            semantic_similarity * semantic_weight
        )

        is_relevant = relevance_score >= self.config.relevance_threshold

        # Determine filter reason
        if is_relevant:
            reasons = []
            if keyword_results["matched_keywords"]:
                reasons.append(
                    f"Keywords: {', '.join(keyword_results['matched_keywords'])}"
                )
            if semantic_similarity > 0.5:
                reasons.append(f"Semantic similarity: {semantic_similarity:.3f}")
            filter_reason = "Relevant - " + "; ".join(reasons)
        else:
            filter_reason = f"Not relevant - Score: {relevance_score:.3f} < {self.config.relevance_threshold}"

        return {
            "relevance_score": relevance_score,
            "is_relevant": is_relevant,
            "keywords_matched": keyword_results["matched_keywords"],
            "semantic_similarity": semantic_similarity if use_semantic else None,
            "filter_reason": filter_reason,
        }

    async def _batch_filter_comments(
        self, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Batch filter multiple Reddit comments."""
        comment_ids = parameters.get("comment_ids", [])
        topics = parameters.get("topics", self.config.reddit_topics)
        use_semantic = parameters.get("use_semantic", True)

        if not comment_ids:
            return {
                "skill": "batch_filter_comments",
                "status": "error",
                "error": "comment_ids parameter is required",
            }

        try:
            results = {
                "total_comments": len(comment_ids),
                "processed": 0,
                "relevant": 0,
                "stored": 0,
                "details": [],
            }

            with get_db_session() as session:
                for comment_id in comment_ids:
                    # Get comment from database
                    if isinstance(comment_id, int):
                        comment = (
                            session.query(RedditComment)
                            .filter_by(id=comment_id)
                            .first()
                        )
                    else:
                        comment = (
                            session.query(RedditComment)
                            .filter_by(comment_id=comment_id)
                            .first()
                        )

                    if not comment:
                        logger.warning(f"Comment not found: {comment_id}")
                        continue

                    # Check if already filtered
                    existing_filter = (
                        session.query(ContentFilter)
                        .filter_by(comment_id=comment.id)
                        .first()
                    )
                    if existing_filter:
                        logger.debug(f"Comment {comment_id} already filtered, skipping")
                        continue

                    # Process the comment
                    filter_result = await self._process_single_comment(
                        comment, topics, use_semantic
                    )

                    # Store result in database
                    content_filter = ContentFilter(
                        comment_id=comment.id,
                        relevance_score=filter_result["relevance_score"],
                        is_relevant=filter_result["is_relevant"],
                        keywords_matched=filter_result["keywords_matched"],
                        semantic_similarity=filter_result.get("semantic_similarity"),
                        filter_reason=filter_result["filter_reason"],
                    )
                    session.add(content_filter)
                    session.commit()

                    results["processed"] += 1
                    results["stored"] += 1
                    if filter_result["is_relevant"]:
                        results["relevant"] += 1

                    # Add to details (limit to first 10)
                    if len(results["details"]) < 10:
                        results["details"].append(
                            {
                                "comment_id": comment.comment_id,
                                "body": comment.body[:60] + "..."
                                if len(comment.body) > 60
                                else comment.body,
                                "relevance_score": filter_result["relevance_score"],
                                "is_relevant": filter_result["is_relevant"],
                                "keywords_matched": filter_result["keywords_matched"],
                            }
                        )

            return {
                "skill": "batch_filter_comments",
                "status": "success",
                "result": results,
            }

        except Exception as e:
            logger.error(f"Error in batch comment filtering: {e}")
            return {
                "skill": "batch_filter_comments",
                "status": "error",
                "error": str(e),
            }

    async def _process_single_comment(
        self, comment: RedditComment, topics: list[str], use_semantic: bool
    ) -> dict[str, Any]:
        """Process a single comment for filtering."""
        text = comment.body.strip()

        # Keyword matching
        keyword_results = await asyncio.to_thread(self._match_keywords, text, topics)

        semantic_similarity = 0.0
        if use_semantic and self._semantic_model:
            try:
                semantic_results = await asyncio.to_thread(
                    self._compute_semantic_similarity, text, topics
                )
                semantic_similarity = semantic_results["max_similarity"]
            except Exception as e:
                logger.warning(
                    f"Semantic similarity failed for comment {comment.comment_id}: {e}"
                )

        # Combine scores (70% keyword, 30% semantic)
        keyword_weight = 0.7
        semantic_weight = 0.3
        relevance_score = (keyword_results["match_score"] * keyword_weight) + (
            semantic_similarity * semantic_weight
        )

        is_relevant = relevance_score >= self.config.relevance_threshold

        # Determine filter reason
        if is_relevant:
            reasons = []
            if keyword_results["matched_keywords"]:
                reasons.append(
                    f"Keywords: {', '.join(keyword_results['matched_keywords'])}"
                )
            if semantic_similarity > 0.5:
                reasons.append(f"Semantic similarity: {semantic_similarity:.3f}")
            filter_reason = "Relevant - " + "; ".join(reasons)
        else:
            filter_reason = f"Not relevant - Score: {relevance_score:.3f} < {self.config.relevance_threshold}"

        return {
            "relevance_score": relevance_score,
            "is_relevant": is_relevant,
            "keywords_matched": keyword_results["matched_keywords"],
            "semantic_similarity": semantic_similarity if use_semantic else None,
            "filter_reason": filter_reason,
        }

    def get_health_status(self) -> dict[str, Any]:
        """Get detailed health status for this agent."""
        base_health = self.get_common_health_status()

        filter_health = {
            "semantic_model_initialized": self._semantic_model is not None,
            "cached_topic_embeddings": len(self._topic_embeddings),
            "configured_topics": len(self.config.reddit_topics),
            "relevance_threshold": self.config.relevance_threshold,
        }

        if self._semantic_model:
            try:
                # Quick model test
                test_result = self._semantic_model.encode(["test"])
                filter_health["model_status"] = "operational"
                filter_health["embedding_dimension"] = len(test_result[0])
            except Exception as e:
                filter_health["model_status"] = "error"
                filter_health["model_error"] = str(e)
        else:
            filter_health["model_status"] = "not_initialized"

        base_health["filter_specific"] = filter_health
        return base_health


if __name__ == "__main__":
    import asyncio

    from .server import A2AAgentServer

    async def main():
        agent = FilterAgent()
        server = A2AAgentServer(agent)
        await server.start_server()

    asyncio.run(main())
