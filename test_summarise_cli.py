#!/usr/bin/env python3
"""
Manual CLI testing for SummariseAgent.

This script provides interactive testing of the SummariseAgent's A2A capabilities
including content summarization, rate limiting, and extractive fallback functionality.
"""

import asyncio

from reddit_watcher.agents.summarise_agent import SummariseAgent


async def test_agent_initialization():
    """Test SummariseAgent initialization and basic properties."""
    print("=" * 60)
    print("Testing SummariseAgent Initialization")
    print("=" * 60)

    agent = SummariseAgent()

    print(f"Agent Type: {agent.agent_type}")
    print(f"Agent Name: {agent.name}")
    print(f"Agent Version: {agent.version}")
    print(f"Gemini Initialized: {agent._gemini_initialized}")
    print(f"spaCy Model Available: {agent._nlp_model is not None}")
    print()


async def test_get_skills():
    """Test agent skills enumeration."""
    print("=" * 60)
    print("Testing Agent Skills")
    print("=" * 60)

    agent = SummariseAgent()
    skills = agent.get_skills()

    print(f"Number of skills: {len(skills)}")
    for i, skill in enumerate(skills, 1):
        print(f"\n{i}. Skill: {skill.name}")
        print(f"   ID: {skill.id}")
        print(f"   Description: {skill.description}")
        print(f"   Tags: {', '.join(skill.tags)}")
        print(f"   Input Modes: {', '.join(skill.inputModes)}")
        print(f"   Output Modes: {', '.join(skill.outputModes)}")
    print()


async def test_health_status():
    """Test agent health status reporting."""
    print("=" * 60)
    print("Testing Health Status")
    print("=" * 60)

    agent = SummariseAgent()
    health = agent.get_health_status()

    print("Health Status:")
    for key, value in health.items():
        print(f"  {key}: {value}")
    print()


async def test_content_summarization():
    """Test content summarization with different content types."""
    print("=" * 60)
    print("Testing Content Summarization")
    print("=" * 60)

    agent = SummariseAgent()

    # Test cases with different content lengths and types
    test_cases = [
        {
            "name": "Short Reddit Post",
            "content": "Just discovered Claude Code and it's amazing! The AI-powered development workflow is incredibly smooth. Has anyone else tried using it for complex projects? Would love to hear your experiences.",
            "content_type": "post",
        },
        {
            "name": "Long Technical Comment",
            "content": """The Agent-to-Agent (A2A) protocol represents a significant advancement in distributed AI systems. Unlike traditional monolithic AI applications, A2A enables multiple specialized agents to collaborate on complex tasks. Each agent maintains its own expertise domain while communicating through standardized interfaces.

The key benefits include improved scalability, fault tolerance, and modularity. When one agent fails, others can continue operating. The protocol supports both synchronous and asynchronous communication patterns, making it suitable for real-time applications as well as batch processing scenarios.

Implementation typically involves defining agent capabilities through Agent Cards, which describe the skills each agent can perform. Service discovery mechanisms allow agents to find and communicate with relevant peers. Security is handled through various authentication schemes including API keys and bearer tokens.

For developers getting started with A2A, I recommend beginning with simple use cases like content processing pipelines. The Reddit Technical Watcher project is an excellent example, demonstrating how retrieval, filtering, summarization, and alerting agents can work together to monitor social media content.""",
            "content_type": "comment",
        },
        {
            "name": "Very Long Content (Chunking Test)",
            "content": "This is a test of content chunking. "
            * 300,  # Creates very long content
            "content_type": "mixed",
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test_case['name']} ---")
        print(f"Content Length: {len(test_case['content'])} characters")
        print(f"Content Type: {test_case['content_type']}")

        try:
            result = await agent.execute_skill(
                "summarizeContent",
                {
                    "content": test_case["content"],
                    "content_type": test_case["content_type"],
                    "post_ids": [f"test_post_{i}"],
                },
            )

            if result["success"]:
                print("✅ Success!")
                print(f"Summary: {result['summary']}")
                print(f"Original Length: {result['original_length']} chars")
                print(f"Summary Length: {result['summary_length']} chars")
                print(f"Chunks Processed: {result['chunks_processed']}")
                print(f"Method: {result['summarization_method']}")

                # Calculate compression ratio
                compression_ratio = result["summary_length"] / result["original_length"]
                print(f"Compression Ratio: {compression_ratio:.2%}")
            else:
                print(f"❌ Failed: {result['error']}")

        except Exception as e:
            print(f"❌ Exception: {e}")

        print()


async def test_error_handling():
    """Test error handling scenarios."""
    print("=" * 60)
    print("Testing Error Handling")
    print("=" * 60)

    agent = SummariseAgent()

    error_test_cases = [
        {
            "name": "Unknown Skill",
            "skill": "unknownSkill",
            "params": {"content": "test"},
        },
        {"name": "Missing Content", "skill": "summarizeContent", "params": {}},
        {
            "name": "Empty Content",
            "skill": "summarizeContent",
            "params": {"content": ""},
        },
    ]

    for test_case in error_test_cases:
        print(f"\n--- {test_case['name']} ---")
        try:
            result = await agent.execute_skill(test_case["skill"], test_case["params"])
            if result["success"]:
                print(f"⚠️  Unexpected success: {result}")
            else:
                print(f"✅ Expected failure: {result['error']}")
        except Exception as e:
            print(f"❌ Exception: {e}")


async def test_content_chunking():
    """Test content chunking functionality."""
    print("=" * 60)
    print("Testing Content Chunking")
    print("=" * 60)

    agent = SummariseAgent()

    # Test with different chunk sizes
    test_content = "This is a test sentence. " * 100  # Creates ~2500 character content

    print(f"Original content length: {len(test_content)} characters")

    # Test different chunk sizes
    chunk_sizes = [500, 1000, 2000, 5000]

    for chunk_size in chunk_sizes:
        chunks = agent._split_content_recursively(
            test_content, max_chunk_size=chunk_size
        )
        print(f"Chunk size {chunk_size}: Generated {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i + 1}: {len(chunk)} characters")
    print()


async def test_extractive_summarization():
    """Test extractive summarization fallback."""
    print("=" * 60)
    print("Testing Extractive Summarization")
    print("=" * 60)

    agent = SummariseAgent()

    test_content = "First sentence about AI. Second sentence discusses machine learning. Third sentence covers neural networks. Fourth sentence explains deep learning. Fifth sentence mentions transformers."

    print(f"Original content: {test_content}")
    print(f"Original length: {len(test_content)} characters")

    # Test different max_sentences values
    for max_sentences in [1, 2, 3, 5]:
        summary = agent._extractive_summarization(
            test_content, max_sentences=max_sentences
        )
        print(f"\nMax sentences {max_sentences}: {summary}")
        print(f"Summary length: {len(summary)} characters")
    print()


async def main():
    """Run all tests."""
    print("🤖 SummariseAgent CLI Testing Suite")
    print("=" * 60)

    try:
        await test_agent_initialization()
        await test_get_skills()
        await test_health_status()
        await test_content_summarization()
        await test_error_handling()
        await test_content_chunking()
        await test_extractive_summarization()

        print("✅ All tests completed!")

    except KeyboardInterrupt:
        print("\n🛑 Testing interrupted by user")
    except Exception as e:
        print(f"\n❌ Testing failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
