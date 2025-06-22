# Agent Cards - A2A Service Discovery

Agent Cards are JSON documents that describe each agent's capabilities, endpoints, and authentication requirements. They enable automatic service discovery and dynamic integration within the A2A ecosystem.

## Agent Card Endpoint

Every agent exposes its Agent Card at:
```
GET /.well-known/agent.json
```

## Standard Agent Card Structure

```json
{
  "name": "Agent Name",
  "description": "Agent description and purpose",
  "version": "1.0.0",
  "provider": {
    "organization": "Reddit Technical Watcher",
    "url": "https://github.com/reddit-technical-watcher"
  },
  "url": "http://localhost:8000/a2a",
  "defaultInputModes": ["text/plain", "application/json"],
  "defaultOutputModes": ["application/json"],
  "capabilities": {
    "inputModes": ["text/plain", "application/json"],
    "outputModes": ["text/plain", "application/json"],
    "streaming": true,
    "authenticationRequired": true
  },
  "skills": [
    {
      "name": "skill_name",
      "description": "Skill description",
      "parameters": [
        {
          "name": "param_name",
          "type": "string",
          "description": "Parameter description",
          "required": true
        }
      ]
    }
  ],
  "securitySchemes": [
    {
      "name": "X-API-Key",
      "description": "API key authentication",
      "type": "apiKey",
      "in": "header"
    }
  ]
}
```

## Agent-Specific Cards

### Coordinator Agent Card
```json
{
  "name": "Reddit Technical Watcher Coordinator",
  "description": "Orchestrates workflow between Reddit monitoring agents using A2A protocol",
  "skills": [
    {
      "name": "orchestrate_workflow",
      "description": "Execute complete Reddit monitoring workflow",
      "parameters": [
        {"name": "topics", "type": "array", "description": "Topics to monitor", "required": false}
      ]
    },
    {
      "name": "get_workflow_status",
      "description": "Get current workflow execution status",
      "parameters": [
        {"name": "workflow_id", "type": "string", "description": "Workflow ID", "required": true}
      ]
    },
    {
      "name": "health_check",
      "description": "Check agent health and dependencies",
      "parameters": []
    }
  ]
}
```

### Retrieval Agent Card
```json
{
  "name": "Reddit Retrieval Agent",
  "description": "Retrieves Reddit posts, comments, and discovers subreddits",
  "skills": [
    {
      "name": "retrieve_posts",
      "description": "Retrieve Reddit posts for specified topics",
      "parameters": [
        {"name": "topics", "type": "array", "description": "Topics to search", "required": true},
        {"name": "subreddits", "type": "array", "description": "Specific subreddits", "required": false},
        {"name": "limit", "type": "integer", "description": "Maximum posts to retrieve", "required": false},
        {"name": "time_range", "type": "string", "description": "Time range filter", "required": false}
      ]
    },
    {
      "name": "retrieve_comments",
      "description": "Retrieve comments for specified posts",
      "parameters": [
        {"name": "post_ids", "type": "array", "description": "Post IDs to get comments", "required": true},
        {"name": "depth", "type": "integer", "description": "Comment thread depth", "required": false}
      ]
    },
    {
      "name": "discover_subreddits",
      "description": "Discover relevant subreddits for topics",
      "parameters": [
        {"name": "topics", "type": "array", "description": "Topics for subreddit discovery", "required": true}
      ]
    }
  ]
}
```

### Filter Agent Card
```json
{
  "name": "Reddit Filter Agent",
  "description": "Filters Reddit content for relevance using keyword matching and semantic analysis",
  "skills": [
    {
      "name": "filter_posts",
      "description": "Filter posts for relevance to monitoring topics",
      "parameters": [
        {"name": "posts", "type": "array", "description": "Posts to filter", "required": true},
        {"name": "topics", "type": "array", "description": "Relevance topics", "required": true},
        {"name": "threshold", "type": "number", "description": "Relevance threshold", "required": false}
      ]
    },
    {
      "name": "filter_comments",
      "description": "Filter comments for relevance",
      "parameters": [
        {"name": "comments", "type": "array", "description": "Comments to filter", "required": true},
        {"name": "topics", "type": "array", "description": "Relevance topics", "required": true},
        {"name": "threshold", "type": "number", "description": "Relevance threshold", "required": false}
      ]
    },
    {
      "name": "calculate_relevance_score",
      "description": "Calculate relevance score for content",
      "parameters": [
        {"name": "content", "type": "string", "description": "Content to score", "required": true},
        {"name": "topics", "type": "array", "description": "Reference topics", "required": true}
      ]
    }
  ]
}
```

### Summarise Agent Card
```json
{
  "name": "Reddit Summarise Agent",
  "description": "Generates concise summaries of Reddit content using Gemini AI",
  "skills": [
    {
      "name": "summarise_posts",
      "description": "Generate summaries for Reddit posts",
      "parameters": [
        {"name": "posts", "type": "array", "description": "Posts to summarize", "required": true},
        {"name": "max_length", "type": "integer", "description": "Maximum summary length", "required": false}
      ]
    },
    {
      "name": "summarise_discussion",
      "description": "Summarize discussion threads",
      "parameters": [
        {"name": "posts", "type": "array", "description": "Posts with comments", "required": true},
        {"name": "focus_topics", "type": "array", "description": "Topics to focus on", "required": false}
      ]
    },
    {
      "name": "generate_insights",
      "description": "Extract key insights from content",
      "parameters": [
        {"name": "content", "type": "array", "description": "Content for insight extraction", "required": true}
      ]
    }
  ]
}
```

### Alert Agent Card
```json
{
  "name": "Reddit Alert Agent",
  "description": "Sends notifications via Slack, email, and other channels",
  "skills": [
    {
      "name": "send_alert",
      "description": "Send alert notification",
      "parameters": [
        {"name": "content", "type": "object", "description": "Alert content", "required": true},
        {"name": "channels", "type": "array", "description": "Notification channels", "required": false},
        {"name": "priority", "type": "string", "description": "Alert priority level", "required": false}
      ]
    },
    {
      "name": "send_digest",
      "description": "Send periodic digest notification",
      "parameters": [
        {"name": "summaries", "type": "array", "description": "Content summaries", "required": true},
        {"name": "period", "type": "string", "description": "Digest period", "required": false}
      ]
    },
    {
      "name": "test_notifications",
      "description": "Test notification channels",
      "parameters": [
        {"name": "channels", "type": "array", "description": "Channels to test", "required": false}
      ]
    }
  ]
}
```

## Using Agent Cards

### Service Discovery
```bash
# Discover all agents
curl http://localhost:8000/discover

# Get specific agent card
curl http://localhost:8001/.well-known/agent.json
```

### Validation
All Agent Cards should be validated against the A2A specification:

- Required fields: `name`, `description`, `version`, `url`, `skills`
- Valid skill parameters with proper types
- Correct security scheme definitions
- Valid capability declarations

### Dynamic Integration
Agent Cards enable:

1. **Automatic skill discovery** - Find available capabilities
2. **Parameter validation** - Ensure correct skill invocation
3. **Authentication setup** - Configure security schemes
4. **Load balancing** - Discover multiple agent instances
5. **Health monitoring** - Track agent availability

## Best Practices

1. **Version Control** - Update version when skills change
2. **Clear Descriptions** - Make skills self-documenting
3. **Parameter Types** - Use precise type definitions
4. **Security** - Always define required authentication
5. **Testing** - Validate cards after changes

---

*See also: [Authentication](./authentication.md), [Endpoints Reference](./endpoints/)*
