# ABOUTME: Test data fixtures for A2A integration testing
# ABOUTME: Provides mock data for Reddit posts, comments, and A2A communication testing

from typing import Any

# Mock Reddit Posts for Testing
MOCK_REDDIT_POSTS = [
    {
        "id": "test_post_1",
        "title": "Claude Code revolutionizes AI agent development",
        "selftext": "I've been using Claude Code for building A2A protocol-based agents and it's incredible. The multi-agent communication is seamless and the development experience is outstanding.",
        "author": "ai_developer_123",
        "subreddit": "MachineLearning",
        "score": 89,
        "num_comments": 23,
        "created_utc": 1703808000,
        "url": "https://reddit.com/r/MachineLearning/comments/test_post_1",
        "permalink": "/r/MachineLearning/comments/test_post_1/claude_code_revolutionizes/",
        "upvote_ratio": 0.94,
        "flair_text": "Discussion",
        "is_self": True,
    },
    {
        "id": "test_post_2",
        "title": "Comparing AI development frameworks: Claude Code vs alternatives",
        "selftext": "Looking for experiences with different AI development frameworks. How does Claude Code compare to LangChain, AutoGen, and others for agent-based systems?",
        "author": "tech_researcher",
        "subreddit": "artificial",
        "score": 67,
        "num_comments": 34,
        "created_utc": 1703794600,
        "url": "https://reddit.com/r/artificial/comments/test_post_2",
        "permalink": "/r/artificial/comments/test_post_2/comparing_ai_frameworks/",
        "upvote_ratio": 0.87,
        "flair_text": "Question",
        "is_self": True,
    },
    {
        "id": "test_post_3",
        "title": "Claude Code A2A protocol implementation guide",
        "selftext": "Just published a guide on implementing A2A protocol with Claude Code. Covers service discovery, agent cards, and workflow orchestration.",
        "author": "code_mentor",
        "subreddit": "programming",
        "score": 156,
        "num_comments": 42,
        "created_utc": 1703781200,
        "url": "https://reddit.com/r/programming/comments/test_post_3",
        "permalink": "/r/programming/comments/test_post_3/claude_code_a2a_guide/",
        "upvote_ratio": 0.96,
        "flair_text": "Tutorial",
        "is_self": True,
    },
    {
        "id": "irrelevant_post",
        "title": "Best pizza places in San Francisco",
        "selftext": "Looking for recommendations for pizza places in SF. Any hidden gems?",
        "author": "foodie_sf",
        "subreddit": "sanfrancisco",
        "score": 23,
        "num_comments": 15,
        "created_utc": 1703767800,
        "url": "https://reddit.com/r/sanfrancisco/comments/irrelevant_post",
        "permalink": "/r/sanfrancisco/comments/irrelevant_post/best_pizza_places/",
        "upvote_ratio": 0.82,
        "flair_text": "Food",
        "is_self": True,
    },
]

# Mock Reddit Comments for Testing
MOCK_REDDIT_COMMENTS = [
    {
        "id": "comment_1",
        "post_id": "test_post_1",
        "body": "Completely agree! Claude Code's A2A protocol makes building multi-agent systems so much easier. The service discovery through Redis is brilliant.",
        "author": "agent_builder",
        "score": 34,
        "created_utc": 1703808300,
        "permalink": "/r/MachineLearning/comments/test_post_1/claude_code_revolutionizes/comment_1/",
        "parent_id": "test_post_1",
    },
    {
        "id": "comment_2",
        "post_id": "test_post_1",
        "body": "Has anyone tried using it for Reddit monitoring? I'm building a similar system and wondering about the performance characteristics.",
        "author": "monitoring_dev",
        "score": 28,
        "created_utc": 1703808600,
        "permalink": "/r/MachineLearning/comments/test_post_1/claude_code_revolutionizes/comment_2/",
        "parent_id": "test_post_1",
    },
    {
        "id": "comment_3",
        "post_id": "test_post_2",
        "body": "I've used both Claude Code and LangChain. Claude Code wins for agent orchestration, but LangChain has more integrations. Depends on your use case.",
        "author": "framework_expert",
        "score": 19,
        "created_utc": 1703795200,
        "permalink": "/r/artificial/comments/test_post_2/comparing_ai_frameworks/comment_3/",
        "parent_id": "test_post_2",
    },
]

# Mock Subreddit Data
MOCK_SUBREDDITS = [
    {
        "display_name": "MachineLearning",
        "public_description": "Machine Learning research discussions, implementations, and news",
        "subscribers": 2100000,
        "created_utc": 1232227200,
        "over18": False,
        "lang": "en",
        "subreddit_type": "public",
    },
    {
        "display_name": "artificial",
        "public_description": "Artificial Intelligence community for discussions and research",
        "subscribers": 950000,
        "created_utc": 1264982400,
        "over18": False,
        "lang": "en",
        "subreddit_type": "public",
    },
    {
        "display_name": "programming",
        "public_description": "Computer programming discussions and tutorials",
        "subscribers": 4200000,
        "created_utc": 1134104400,
        "over18": False,
        "lang": "en",
        "subreddit_type": "public",
    },
    {
        "display_name": "ClaudeAI",
        "public_description": "Discussion about Claude AI and its applications",
        "subscribers": 45000,
        "created_utc": 1640995200,
        "over18": False,
        "lang": "en",
        "subreddit_type": "public",
    },
]

# Expected Summaries for Testing
EXPECTED_SUMMARIES = {
    "claude_code_discussion": {
        "title": "Claude Code AI Development Discussion Summary",
        "content": "**Key Discussion Points:**\n- Claude Code's A2A protocol praised for multi-agent development\n- Excellent development experience and seamless communication\n- Strong community interest in Reddit monitoring applications\n- Comparison with other AI frameworks shows competitive advantages\n\n**Community Sentiment:** Very positive (94% upvote ratio)\n**Engagement Level:** High (89 upvotes, 23 comments)\n**Technical Focus:** A2A protocol, agent orchestration, service discovery",
        "metadata": {
            "posts_summarized": 1,
            "total_score": 89,
            "average_engagement": "high",
            "primary_topics": ["claude_code", "a2a_protocol", "agent_development"],
        },
    },
    "framework_comparison": {
        "title": "AI Framework Comparison Discussion Summary",
        "content": "**Discussion Overview:**\n- Comparative analysis of AI development frameworks\n- Claude Code vs LangChain, AutoGen, and others\n- Community seeking practical implementation guidance\n- Focus on agent-based system capabilities\n\n**Community Sentiment:** Informative and constructive\n**Engagement Level:** Moderate to high (67 upvotes, 34 comments)\n**Technical Focus:** Framework evaluation, practical comparisons",
        "metadata": {
            "posts_summarized": 1,
            "total_score": 67,
            "average_engagement": "moderate",
            "primary_topics": [
                "framework_comparison",
                "agent_systems",
                "development_tools",
            ],
        },
    },
}

# A2A Agent Card Templates for Testing
AGENT_CARD_TEMPLATES = {
    "retrieval": {
        "name": "RetrievalAgent",
        "description": "A2A agent for fetching Reddit posts, comments, and discovering subreddits",
        "version": "1.0.0",
        "skills": [
            {
                "name": "fetch_posts",
                "description": "Fetch Reddit posts based on search query",
                "parameters": {
                    "query": {"type": "string", "required": True},
                    "limit": {"type": "integer", "default": 25},
                    "sort": {"type": "string", "default": "relevance"},
                },
                "returns": {"type": "array", "items": "post"},
            },
            {
                "name": "fetch_comments",
                "description": "Fetch comments for a specific Reddit post",
                "parameters": {
                    "post_id": {"type": "string", "required": True},
                    "limit": {"type": "integer", "default": 100},
                },
                "returns": {"type": "array", "items": "comment"},
            },
            {
                "name": "discover_subreddits",
                "description": "Discover relevant subreddits based on search query",
                "parameters": {
                    "query": {"type": "string", "required": True},
                    "limit": {"type": "integer", "default": 25},
                },
                "returns": {"type": "array", "items": "subreddit"},
            },
        ],
        "endpoints": {
            "health": "/health",
            "agent_card": "/.well-known/agent.json",
            "skills": "/skills/{skill_name}",
        },
        "authentication": {"required": False, "methods": ["api_key", "bearer_token"]},
    },
    "filter": {
        "name": "FilterAgent",
        "description": "A2A agent for content relevance assessment and filtering",
        "version": "1.0.0",
        "skills": [
            {
                "name": "keyword_filter",
                "description": "Filter content based on keyword matching",
                "parameters": {
                    "content": {"type": "array", "required": True},
                    "keywords": {"type": "array", "required": True},
                    "threshold": {"type": "float", "default": 0.5},
                },
                "returns": {"type": "array", "items": "filtered_content"},
            },
            {
                "name": "semantic_filter",
                "description": "Filter content using semantic similarity",
                "parameters": {
                    "content": {"type": "array", "required": True},
                    "target_topics": {"type": "array", "required": True},
                    "similarity_threshold": {"type": "float", "default": 0.7},
                },
                "returns": {"type": "array", "items": "filtered_content"},
            },
        ],
    },
}

# Test Workflow Scenarios
WORKFLOW_SCENARIOS = [
    {
        "name": "reddit_monitoring_basic",
        "description": "Basic Reddit monitoring workflow",
        "steps": [
            {
                "agent": "retrieval",
                "skill": "fetch_posts",
                "parameters": {"query": "Claude Code", "limit": 5},
            },
            {
                "agent": "filter",
                "skill": "keyword_filter",
                "parameters": {
                    "content": "{{previous_result}}",
                    "keywords": ["claude", "code", "ai", "agent"],
                },
            },
            {
                "agent": "summarise",
                "skill": "summarize_content",
                "parameters": {"content": "{{previous_result}}", "max_length": 200},
            },
            {
                "agent": "alert",
                "skill": "send_slack",
                "parameters": {
                    "message": "{{previous_result}}",
                    "channel": "#ai-alerts",
                },
            },
        ],
        "expected_outcome": {
            "posts_retrieved": {"min": 1, "max": 5},
            "posts_filtered": {"min": 1, "max": 5},
            "summary_generated": True,
            "alert_sent": True,
        },
    },
    {
        "name": "subreddit_discovery",
        "description": "Discover and analyze new subreddits",
        "steps": [
            {
                "agent": "retrieval",
                "skill": "discover_subreddits",
                "parameters": {"query": "artificial intelligence", "limit": 10},
            },
            {
                "agent": "filter",
                "skill": "semantic_filter",
                "parameters": {
                    "content": "{{previous_result}}",
                    "target_topics": ["ai", "machine learning", "development"],
                    "similarity_threshold": 0.6,
                },
            },
        ],
        "expected_outcome": {
            "subreddits_discovered": {"min": 1, "max": 10},
            "subreddits_filtered": {"min": 1, "max": 10},
        },
    },
]

# Error Scenarios for Testing
ERROR_SCENARIOS = [
    {
        "name": "invalid_skill",
        "agent": "retrieval",
        "skill": "nonexistent_skill",
        "parameters": {},
        "expected_error": "skill_not_found",
    },
    {
        "name": "missing_parameters",
        "agent": "retrieval",
        "skill": "fetch_posts",
        "parameters": {},  # Missing required 'query' parameter
        "expected_error": "missing_required_parameter",
    },
    {
        "name": "invalid_parameter_type",
        "agent": "filter",
        "skill": "keyword_filter",
        "parameters": {
            "content": "not_an_array",  # Should be array
            "keywords": ["test"],
        },
        "expected_error": "invalid_parameter_type",
    },
]


def get_mock_posts_by_query(query: str, limit: int = 25) -> list[dict[str, Any]]:
    """Filter mock posts by query string"""
    query_lower = query.lower()
    matching_posts = []

    for post in MOCK_REDDIT_POSTS:
        if (
            query_lower in post["title"].lower()
            or query_lower in post["selftext"].lower()
            or query_lower in post.get("flair_text", "").lower()
        ):
            matching_posts.append(post)

    return matching_posts[:limit]


def get_mock_comments_by_post_id(
    post_id: str, limit: int = 100
) -> list[dict[str, Any]]:
    """Filter mock comments by post ID"""
    matching_comments = [c for c in MOCK_REDDIT_COMMENTS if c["post_id"] == post_id]
    return matching_comments[:limit]


def get_mock_subreddits_by_query(query: str, limit: int = 25) -> list[dict[str, Any]]:
    """Filter mock subreddits by query string"""
    query_lower = query.lower()
    matching_subreddits = []

    for subreddit in MOCK_SUBREDDITS:
        if (
            query_lower in subreddit["display_name"].lower()
            or query_lower in subreddit["public_description"].lower()
        ):
            matching_subreddits.append(subreddit)

    return matching_subreddits[:limit]
