# ABOUTME: Mock Reddit API server for integration testing
# ABOUTME: Provides controlled Reddit API responses without requiring real Reddit API access

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI

app = FastAPI(title="Mock Reddit API", version="1.0.0")

# Mock data store
MOCK_POSTS = [
    {
        "id": "test_post_1",
        "title": "Claude Code is amazing for AI development",
        "selftext": "Just tried Claude Code and it's incredible for building AI agents. The A2A protocol support is fantastic.",
        "author": "test_user_1",
        "subreddit": "MachineLearning",
        "score": 42,
        "num_comments": 15,
        "created_utc": 1703808000,  # 2023-12-28
        "url": "https://reddit.com/r/MachineLearning/comments/test_post_1",
        "permalink": "/r/MachineLearning/comments/test_post_1/claude_code_amazing/",
        "upvote_ratio": 0.95,
    },
    {
        "id": "test_post_2",
        "title": "New AI framework comparison",
        "selftext": "Comparing different AI frameworks for agent development. Claude Code vs others.",
        "author": "test_user_2",
        "subreddit": "artificial",
        "score": 28,
        "num_comments": 8,
        "created_utc": 1703721600,  # 2023-12-27
        "url": "https://reddit.com/r/artificial/comments/test_post_2",
        "permalink": "/r/artificial/comments/test_post_2/ai_framework_comparison/",
        "upvote_ratio": 0.87,
    },
]

MOCK_COMMENTS = [
    {
        "id": "comment_1",
        "post_id": "test_post_1",
        "body": "I agree! Claude Code's A2A protocol makes multi-agent systems so much easier to build.",
        "author": "commenter_1",
        "score": 12,
        "created_utc": 1703808300,
        "permalink": "/r/MachineLearning/comments/test_post_1/claude_code_amazing/comment_1/",
    },
    {
        "id": "comment_2",
        "post_id": "test_post_1",
        "body": "Has anyone tried it for Reddit monitoring? Seems perfect for that use case.",
        "author": "commenter_2",
        "score": 8,
        "created_utc": 1703808600,
        "permalink": "/r/MachineLearning/comments/test_post_1/claude_code_amazing/comment_2/",
    },
]

MOCK_SUBREDDITS = [
    {
        "display_name": "MachineLearning",
        "public_description": "Machine Learning discussions and news",
        "subscribers": 1500000,
        "created_utc": 1232227200,
        "over18": False,
    },
    {
        "display_name": "artificial",
        "public_description": "Artificial Intelligence community",
        "subscribers": 800000,
        "created_utc": 1264982400,
        "over18": False,
    },
    {
        "display_name": "ClaudeAI",
        "public_description": "Discussion about Claude AI and its applications",
        "subscribers": 25000,
        "created_utc": 1640995200,
        "over18": False,
    },
]


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker health checks"""
    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}


@app.get("/api/v1/search/posts")
async def search_posts(q: str, limit: int = 25, sort: str = "relevance"):
    """Mock Reddit post search endpoint"""
    # Filter posts based on query
    matching_posts = []
    query_lower = q.lower()

    for post in MOCK_POSTS:
        if (
            query_lower in post["title"].lower()
            or query_lower in post["selftext"].lower()
            or query_lower in post["subreddit"].lower()
        ):
            matching_posts.append(post)

    # Apply limit
    matching_posts = matching_posts[:limit]

    return {
        "data": {
            "children": [{"data": post} for post in matching_posts],
            "after": None,
            "before": None,
        }
    }


@app.get("/api/v1/posts/{post_id}/comments")
async def get_post_comments(post_id: str, limit: int = 100):
    """Mock Reddit post comments endpoint"""
    # Filter comments for this post
    post_comments = [c for c in MOCK_COMMENTS if c["post_id"] == post_id]
    post_comments = post_comments[:limit]

    return {
        "data": {
            "children": [{"data": comment} for comment in post_comments],
            "after": None,
            "before": None,
        }
    }


@app.get("/api/v1/subreddits/search")
async def search_subreddits(q: str, limit: int = 25):
    """Mock Reddit subreddit search endpoint"""
    query_lower = q.lower()

    matching_subreddits = []
    for sub in MOCK_SUBREDDITS:
        if (
            query_lower in sub["display_name"].lower()
            or query_lower in sub["public_description"].lower()
        ):
            matching_subreddits.append(sub)

    matching_subreddits = matching_subreddits[:limit]

    return {
        "data": {
            "children": [{"data": sub} for sub in matching_subreddits],
            "after": None,
            "before": None,
        }
    }


@app.get("/api/v1/subreddit/{subreddit}/hot")
async def get_subreddit_hot_posts(subreddit: str, limit: int = 25):
    """Mock Reddit subreddit hot posts endpoint"""
    # Filter posts by subreddit
    subreddit_posts = [
        p for p in MOCK_POSTS if p["subreddit"].lower() == subreddit.lower()
    ]
    subreddit_posts = subreddit_posts[:limit]

    return {
        "data": {
            "children": [{"data": post} for post in subreddit_posts],
            "after": None,
            "before": None,
        }
    }


@app.post("/api/v1/posts")
async def create_test_post(post_data: dict[str, Any]):
    """Create test post for integration testing"""
    # Add to mock data store
    post_id = f"test_post_{len(MOCK_POSTS) + 1}"
    new_post = {
        "id": post_id,
        "title": post_data.get("title", "Test Post"),
        "selftext": post_data.get("selftext", "Test content"),
        "author": post_data.get("author", "test_user"),
        "subreddit": post_data.get("subreddit", "test"),
        "score": post_data.get("score", 1),
        "num_comments": 0,
        "created_utc": int(datetime.now(UTC).timestamp()),
        "url": f"https://reddit.com/r/{post_data.get('subreddit', 'test')}/comments/{post_id}",
        "permalink": f"/r/{post_data.get('subreddit', 'test')}/comments/{post_id}/test_post/",
        "upvote_ratio": 1.0,
    }

    MOCK_POSTS.append(new_post)
    return {"data": new_post}


@app.delete("/api/v1/reset")
async def reset_mock_data():
    """Reset mock data to initial state - useful for test isolation"""
    global MOCK_POSTS, MOCK_COMMENTS

    # Reset to initial state
    MOCK_POSTS[:] = [
        {
            "id": "test_post_1",
            "title": "Claude Code is amazing for AI development",
            "selftext": "Just tried Claude Code and it's incredible for building AI agents. The A2A protocol support is fantastic.",
            "author": "test_user_1",
            "subreddit": "MachineLearning",
            "score": 42,
            "num_comments": 15,
            "created_utc": 1703808000,
            "url": "https://reddit.com/r/MachineLearning/comments/test_post_1",
            "permalink": "/r/MachineLearning/comments/test_post_1/claude_code_amazing/",
            "upvote_ratio": 0.95,
        },
        {
            "id": "test_post_2",
            "title": "New AI framework comparison",
            "selftext": "Comparing different AI frameworks for agent development. Claude Code vs others.",
            "author": "test_user_2",
            "subreddit": "artificial",
            "score": 28,
            "num_comments": 8,
            "created_utc": 1703721600,
            "url": "https://reddit.com/r/artificial/comments/test_post_2",
            "permalink": "/r/artificial/comments/test_post_2/ai_framework_comparison/",
            "upvote_ratio": 0.87,
        },
    ]

    MOCK_COMMENTS[:] = [
        {
            "id": "comment_1",
            "post_id": "test_post_1",
            "body": "I agree! Claude Code's A2A protocol makes multi-agent systems so much easier to build.",
            "author": "commenter_1",
            "score": 12,
            "created_utc": 1703808300,
            "permalink": "/r/MachineLearning/comments/test_post_1/claude_code_amazing/comment_1/",
        },
        {
            "id": "comment_2",
            "post_id": "test_post_1",
            "body": "Has anyone tried it for Reddit monitoring? Seems perfect for that use case.",
            "author": "commenter_2",
            "score": 8,
            "created_utc": 1703808600,
            "permalink": "/r/MachineLearning/comments/test_post_1/claude_code_amazing/comment_2/",
        },
    ]

    return {"message": "Mock data reset successfully"}
