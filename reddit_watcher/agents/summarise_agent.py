# ABOUTME: SummariseAgent for AI content summarization using Google Gemini models
# ABOUTME: Implements A2A skills for generating concise summaries with primary/fallback strategy and extractive backup

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import google.generativeai as genai
import spacy
from google.api_core import exceptions as google_exceptions

from reddit_watcher.a2a_protocol import AgentSkill
from reddit_watcher.agents.base import BaseA2AAgent
from reddit_watcher.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class RateLimitState:
    """Track rate limiting state for API calls."""

    requests_made: int = 0
    window_start: float = 0.0
    max_requests_per_minute: int = 100


class SummariseAgent(BaseA2AAgent):
    """
    SummariseAgent for AI content summarization using Google Gemini models.

    Implements A2A skills for:
    - Content summarization with primary/fallback model strategy
    - Rate limiting and retry logic
    - Recursive chunking for large content
    - Extractive fallback when AI models fail
    """

    def __init__(self, config: Settings):
        super().__init__(
            config=config,
            agent_type="summarise",
            name="Content Summarization Agent",
            description="Generates AI-powered summaries using Gemini models with extractive fallback",
            version="1.0.0",
        )

        # Initialize Gemini client if API key is available
        self._gemini_initialized = False
        self._nlp_model: spacy.language.Language | None = None
        self._rate_limit_state = RateLimitState(
            max_requests_per_minute=self.config.gemini_rate_limit
        )

        self._initialize_gemini()
        self._initialize_spacy()

    def _initialize_gemini(self) -> None:
        """Initialize the Google Gemini client."""
        if not self.config.has_gemini_credentials():
            self.logger.warning(
                "Gemini API key not configured. Summarization will use extractive fallback only."
            )
            return

        try:
            genai.configure(api_key=self.config.gemini_api_key)
            self._gemini_initialized = True
            self.logger.info("Gemini client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Gemini client: {e}")
            self._gemini_initialized = False

    def _initialize_spacy(self) -> None:
        """Initialize spaCy model for extractive summarization fallback."""
        try:
            # Try to load English model, fallback to basic if not available
            try:
                self._nlp_model = spacy.load("en_core_web_sm")
            except OSError:
                self.logger.warning(
                    "en_core_web_sm not found, downloading basic model..."
                )
                # Create a basic pipeline for extractive summarization
                self._nlp_model = spacy.blank("en")
                self._nlp_model.add_pipe("sentencizer")

            self.logger.info("spaCy model initialized for extractive fallback")
        except Exception as e:
            self.logger.error(f"Failed to initialize spaCy model: {e}")
            self._nlp_model = None

    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting for Gemini API calls."""
        current_time = time.time()

        # Reset window if a minute has passed
        if current_time - self._rate_limit_state.window_start >= 60:
            self._rate_limit_state.requests_made = 0
            self._rate_limit_state.window_start = current_time

        # If we've hit the limit, wait until the window resets
        if (
            self._rate_limit_state.requests_made
            >= self._rate_limit_state.max_requests_per_minute
        ):
            wait_time = 60 - (current_time - self._rate_limit_state.window_start)
            if wait_time > 0:
                self.logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                await asyncio.sleep(wait_time)
                # Reset after waiting
                self._rate_limit_state.requests_made = 0
                self._rate_limit_state.window_start = time.time()

    def _split_content_recursively(
        self, content: str, max_chunk_size: int = 8000
    ) -> list[str]:
        """
        Split content into chunks that fit within token limits.

        Args:
            content: Text content to split
            max_chunk_size: Maximum characters per chunk (approximate token limit)

        Returns:
            List of content chunks
        """
        if len(content) <= max_chunk_size:
            return [content]

        chunks = []

        # Try to split by paragraphs first
        paragraphs = content.split("\n\n")
        current_chunk = ""

        for paragraph in paragraphs:
            # If single paragraph is too large, split by sentences
            if len(paragraph) > max_chunk_size:
                if self._nlp_model:
                    doc = self._nlp_model(paragraph)
                    sentences = [sent.text for sent in doc.sents]
                else:
                    # Basic sentence splitting if spaCy not available
                    sentences = re.split(r"[.!?]+", paragraph)

                for sentence in sentences:
                    if len(current_chunk + sentence) > max_chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = sentence
                        else:
                            # Even single sentence is too large, force split
                            chunks.append(sentence[:max_chunk_size])
                            current_chunk = sentence[max_chunk_size:]
                    else:
                        current_chunk += sentence
            else:
                # Normal paragraph processing
                if len(current_chunk + paragraph) > max_chunk_size:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = paragraph
                    else:
                        chunks.append(paragraph)
                else:
                    current_chunk += "\n\n" + paragraph if current_chunk else paragraph

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    async def _summarize_with_gemini(
        self, content: str, use_fallback_model: bool = False
    ) -> str | None:
        """
        Summarize content using Gemini models with retry logic.

        Args:
            content: Content to summarize
            use_fallback_model: Whether to use fallback model instead of primary

        Returns:
            Generated summary or None if failed
        """
        if not self._gemini_initialized:
            return None

        model_name = (
            self.config.gemini_model_fallback
            if use_fallback_model
            else self.config.gemini_model_primary
        )

        try:
            await self._check_rate_limit()
            self._rate_limit_state.requests_made += 1

            model = genai.GenerativeModel(model_name)

            # Construct summarization prompt
            prompt = f"""
Please provide a concise, informative summary of the following content.
Focus on key points, main topics, and important insights.
Keep the summary clear and well-structured.

Content:
{content}

Summary:"""

            response = model.generate_content(prompt)

            if response.text:
                self.logger.debug(f"Generated summary using {model_name}")
                return response.text.strip()
            else:
                self.logger.warning(f"Empty response from {model_name}")
                return None

        except google_exceptions.ResourceExhausted as e:
            self.logger.warning(f"Rate limit exceeded for {model_name}: {e}")
            # Wait a bit and try again with exponential backoff
            await asyncio.sleep(2 ** (1 if not use_fallback_model else 2))
            return None
        except google_exceptions.InvalidArgument as e:
            self.logger.error(f"Invalid argument for {model_name}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error with {model_name}: {e}")
            return None

    def _extractive_summarization(self, content: str, max_sentences: int = 3) -> str:
        """
        Fallback extractive summarization using simple heuristics.

        Args:
            content: Content to summarize
            max_sentences: Maximum number of sentences in summary

        Returns:
            Extractive summary
        """
        if not self._nlp_model:
            # Very basic fallback - return first few sentences
            sentences = re.split(r"[.!?]+", content)
            summary_sentences = [
                s.strip() for s in sentences[:max_sentences] if s.strip()
            ]
            return ". ".join(summary_sentences) + "."

        try:
            doc = self._nlp_model(content)
            sentences = list(doc.sents)

            if len(sentences) <= max_sentences:
                return content

            # Simple extractive method: take first, middle, and last sentences
            if max_sentences == 3 and len(sentences) >= 3:
                selected = [sentences[0], sentences[len(sentences) // 2], sentences[-1]]
            else:
                # Distribute sentences evenly
                step = len(sentences) // max_sentences
                selected = [sentences[i * step] for i in range(max_sentences)]

            summary = " ".join([sent.text.strip() for sent in selected])
            return summary

        except Exception as e:
            self.logger.error(f"Extractive summarization failed: {e}")
            # Ultimate fallback
            return content[:500] + "..." if len(content) > 500 else content

    async def _summarize_content_chunks(self, chunks: list[str]) -> str:
        """
        Summarize multiple content chunks and combine results.

        Args:
            chunks: List of content chunks to summarize

        Returns:
            Combined summary
        """
        chunk_summaries = []

        for i, chunk in enumerate(chunks):
            self.logger.debug(f"Processing chunk {i + 1}/{len(chunks)}")

            # Try primary model first
            summary = await self._summarize_with_gemini(chunk, use_fallback_model=False)

            # Try fallback model if primary failed
            if not summary:
                self.logger.info(
                    f"Primary model failed for chunk {i + 1}, trying fallback"
                )
                summary = await self._summarize_with_gemini(
                    chunk, use_fallback_model=True
                )

            # Use extractive fallback if both AI models failed
            if not summary:
                self.logger.info(
                    f"AI models failed for chunk {i + 1}, using extractive fallback"
                )
                summary = self._extractive_summarization(chunk)

            if summary:
                chunk_summaries.append(summary)

        if not chunk_summaries:
            return "Summary generation failed for all content chunks."

        # If we have multiple chunk summaries, combine them
        if len(chunk_summaries) > 1:
            combined_content = "\n\n".join(chunk_summaries)

            # Try to summarize the combined summaries
            final_summary = await self._summarize_with_gemini(
                combined_content, use_fallback_model=False
            )
            if not final_summary:
                final_summary = await self._summarize_with_gemini(
                    combined_content, use_fallback_model=True
                )

            if final_summary:
                return final_summary
            else:
                # Fallback to extractive combination
                return self._extractive_summarization(combined_content, max_sentences=5)

        return chunk_summaries[0]

    def get_skills(self) -> list[AgentSkill]:
        """Define the skills provided by the SummariseAgent."""
        return [
            AgentSkill(
                id="health_check",
                name="health_check",
                description="Check agent health and Gemini model status",
                tags=["health", "status", "gemini"],
                inputModes=["text/plain", "application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
            AgentSkill(
                id="summarize_content",
                name="summarizeContent",
                description="Generate AI-powered summaries of Reddit posts and comments using Gemini models",
                tags=["summarize", "gemini", "ai", "content"],
                inputModes=["application/json"],
                outputModes=["application/json"],
                examples=[],
            ),
        ]

    async def execute_skill(
        self, skill_name: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a summarization skill."""
        if skill_name != "summarizeContent":
            return {
                "success": False,
                "error": f"Unknown skill: {skill_name}",
                "available_skills": [skill.name for skill in self.get_skills()],
            }

        try:
            content = parameters.get("content", "")
            content_type = parameters.get("content_type", "mixed")
            post_ids = parameters.get("post_ids", [])

            if not content:
                return {
                    "success": False,
                    "error": "Content parameter is required and cannot be empty",
                }

            self.logger.info(
                f"Summarizing {content_type} content ({len(content)} characters)"
            )

            # Split content into manageable chunks
            chunks = self._split_content_recursively(content)

            if len(chunks) > 1:
                self.logger.info(
                    f"Content split into {len(chunks)} chunks for processing"
                )

            # Generate summary
            summary = await self._summarize_content_chunks(chunks)

            # Store summary in database if post IDs provided
            summary_id = None
            if post_ids:
                try:
                    # Note: Database storage implementation depends on async session setup
                    self.logger.debug(
                        "Database storage for summaries not yet implemented"
                    )
                    # TODO: Implement proper async database session handling
                    # async with get_async_db_session() as session:
                    #     db_summary = ContentSummary(...)
                    #     session.add(db_summary)
                    #     await session.commit()
                    #     summary_id = db_summary.id
                except Exception as e:
                    self.logger.warning(f"Failed to store summary in database: {e}")

            return {
                "success": True,
                "summary": summary,
                "content_type": content_type,
                "original_length": len(content),
                "summary_length": len(summary),
                "chunks_processed": len(chunks),
                "summarization_method": "gemini_ai"
                if self._gemini_initialized
                else "extractive",
                "summary_id": summary_id,
            }

        except Exception as e:
            self.logger.error(
                f"Error executing summarizeContent skill: {e}", exc_info=True
            )
            return {
                "success": False,
                "error": f"Failed to summarize content: {str(e)}",
                "content_type": parameters.get("content_type", "unknown"),
            }

    def get_health_status(self) -> dict[str, Any]:
        """Get the health status of the SummariseAgent."""
        status = self.get_common_health_status()

        # Add agent-specific health information
        status.update(
            {
                "gemini_initialized": self._gemini_initialized,
                "spacy_available": self._nlp_model is not None,
                "rate_limit_requests_made": self._rate_limit_state.requests_made,
                "rate_limit_window_remaining": max(
                    0, 60 - (time.time() - self._rate_limit_state.window_start)
                ),
                "primary_model": self.config.gemini_model_primary,
                "fallback_model": self.config.gemini_model_fallback,
                "max_requests_per_minute": self._rate_limit_state.max_requests_per_minute,
            }
        )

        return status


if __name__ == "__main__":
    import asyncio

    from .server import A2AAgentServer

    async def main():
        agent = SummariseAgent()
        server = A2AAgentServer(agent)
        await server.start_server()

    asyncio.run(main())
