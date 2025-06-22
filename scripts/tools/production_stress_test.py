#!/usr/bin/env python3

# ABOUTME: Production-ready stress testing for Reddit Technical Watcher system validation
# ABOUTME: Focused tests for multi-topic processing, agent operations, and production readiness assessment

import asyncio
import json
import logging
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import psutil

from reddit_watcher.agents.alert_agent import AlertAgent
from reddit_watcher.agents.coordinator_agent import CoordinatorAgent
from reddit_watcher.agents.filter_agent import FilterAgent
from reddit_watcher.agents.retrieval_agent import RetrievalAgent
from reddit_watcher.agents.summarise_agent import SummariseAgent
from reddit_watcher.circuit_breaker import CircuitBreaker
from reddit_watcher.config import get_settings


@dataclass
class StressTestResult:
    """Results from stress testing operations."""

    test_name: str
    start_time: float
    end_time: float
    duration: float
    success: bool

    # Performance metrics
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    throughput: float = 0.0

    # Resource metrics
    peak_cpu_percent: float = 0.0
    peak_memory_mb: float = 0.0
    avg_response_time: float = 0.0

    # Error information
    error_messages: list[str] = field(default_factory=list)

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)


class ProductionStressTest:
    """
    Production-focused stress testing for the Reddit Technical Watcher.

    Validates system performance against production requirements:
    - 50+ posts per monitoring cycle throughput
    - < 5 seconds complete workflow response time
    - 99%+ success rate under normal load
    - Proper error handling and recovery
    """

    def __init__(self):
        self.config = get_settings()
        self.results: list[StressTestResult] = []

        # Test data
        self.test_topics = [
            "Claude Code",
            "A2A",
            "Agent-to-Agent",
            "FastAPI",
            "Python AI",
        ]

        # Configure logging
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    async def run_production_stress_tests(self) -> dict[str, Any]:
        """Execute production-focused stress tests."""
        self.logger.info(
            "🚀 Starting Production Stress Testing for Reddit Technical Watcher"
        )
        self.logger.info("=" * 80)

        try:
            # Test 1: Multi-Topic High Volume Processing
            await self._test_multi_topic_high_volume()

            # Test 2: Concurrent Agent Operations
            await self._test_concurrent_agent_operations()

            # Test 3: End-to-End Workflow Performance
            await self._test_end_to_end_workflow_performance()

            # Test 4: Circuit Breaker Resilience
            await self._test_circuit_breaker_resilience()

            # Test 5: Resource Scaling Behavior
            await self._test_resource_scaling_behavior()

            # Generate final report
            report = self._generate_production_report()

            # Export results
            self._export_results(report)

            return report

        except Exception as e:
            self.logger.error(f"Production stress testing failed: {e}")
            raise

    async def _test_multi_topic_high_volume(self):
        """Test processing 50+ posts across multiple topics."""
        self.logger.info(
            "🎯 Test 1: Multi-Topic High Volume Processing (Target: 50+ posts)"
        )

        start_time = time.time()

        # Generate 60 test posts across 5 topics
        test_posts = []
        for i in range(60):
            topic = random.choice(self.test_topics)
            test_posts.append(
                {
                    "id": f"stress_post_{i}",
                    "title": f"{topic} Development Update #{i}",
                    "content": f"""
                This post discusses {topic} implementation details and performance optimizations.
                The system demonstrates advanced capabilities in distributed agent coordination.
                Performance benchmarks show significant improvements in throughput and reliability.
                Key features include enhanced error handling, circuit breaker patterns, and scalability.
                The architecture supports concurrent processing with optimized resource utilization.
                """,
                    "subreddit": f"r/{topic.replace(' ', '').lower()}",
                    "score": random.randint(50, 500),
                    "topics": [topic],
                }
            )

        resource_snapshots = []
        response_times = []
        successful_posts = 0
        failed_posts = 0
        error_messages = []

        try:
            filter_agent = FilterAgent(self.config)

            # Process in optimized batches
            batch_size = 15
            batches = [
                test_posts[i : i + batch_size]
                for i in range(0, len(test_posts), batch_size)
            ]

            for batch_num, batch in enumerate(batches):
                batch_start = time.time()
                resource_snapshots.append(self._capture_resource_snapshot())

                # Process batch concurrently
                tasks = [
                    self._process_post_safely(filter_agent, post) for post in batch
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                batch_duration = time.time() - batch_start
                response_times.append(batch_duration)

                # Count results
                batch_successful = 0
                for result in results:
                    if isinstance(result, Exception):
                        failed_posts += 1
                        error_messages.append(str(result))
                    elif isinstance(result, dict) and result.get("success"):
                        successful_posts += 1
                        batch_successful += 1
                    else:
                        failed_posts += 1

                self.logger.info(
                    f"   Batch {batch_num + 1}/{len(batches)}: {batch_successful}/{len(batch)} posts "
                    f"processed in {batch_duration:.2f}s"
                )

                # Brief pause between batches for resource monitoring
                await asyncio.sleep(0.3)

        except Exception as e:
            error_messages.append(f"Multi-topic test critical failure: {str(e)}")
            self.logger.error(f"Multi-topic test failed: {e}")

        end_time = time.time()
        duration = end_time - start_time

        # Calculate metrics
        total_posts = successful_posts + failed_posts
        throughput = successful_posts / duration if duration > 0 else 0

        result = StressTestResult(
            test_name="multi_topic_high_volume",
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=successful_posts >= 50,  # Target: 50+ posts
            total_operations=total_posts,
            successful_operations=successful_posts,
            failed_operations=failed_posts,
            throughput=throughput,
            peak_cpu_percent=max([s.get("cpu", 0) for s in resource_snapshots] or [0]),
            peak_memory_mb=max(
                [s.get("memory_mb", 0) for s in resource_snapshots] or [0]
            ),
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            error_messages=error_messages[:5],
            metadata={
                "target_posts": 60,
                "topics_tested": len(self.test_topics),
                "batch_size": batch_size,
                "success_rate": successful_posts / total_posts
                if total_posts > 0
                else 0,
            },
        )

        self.results.append(result)

        self.logger.info(
            f"✅ Multi-topic test: {successful_posts}/{total_posts} posts "
            f"({throughput:.1f} posts/sec) - {'PASS' if result.success else 'FAIL'}"
        )

    async def _test_concurrent_agent_operations(self):
        """Test all agents operating concurrently under load."""
        self.logger.info(
            "🤖 Test 2: Concurrent Agent Operations (5 agents simultaneously)"
        )

        start_time = time.time()

        successful_ops = 0
        failed_ops = 0
        error_messages = []
        response_times = []
        resource_snapshots = []

        try:
            # Create agents with error handling
            agents = {}
            agent_creation_success = True

            try:
                agents["coordinator"] = CoordinatorAgent(self.config)
                agents["filter"] = FilterAgent(self.config)
                agents["summarise"] = SummariseAgent(self.config)

                # These might fail if credentials aren't available - handle gracefully
                try:
                    agents["retrieval"] = RetrievalAgent(self.config)
                except Exception as e:
                    self.logger.warning(f"RetrievalAgent creation failed: {e}")
                    agent_creation_success = False

                try:
                    agents["alert"] = AlertAgent(self.config)
                except Exception as e:
                    self.logger.warning(f"AlertAgent creation failed: {e}")
                    agent_creation_success = False

            except Exception as e:
                self.logger.error(f"Critical agent creation failure: {e}")
                agent_creation_success = False

            if not agent_creation_success or len(agents) < 3:
                # Run with available agents
                self.logger.warning(
                    "Running with limited agents due to configuration issues"
                )

            # Execute concurrent operations
            for round_num in range(5):  # 5 rounds of concurrent operations
                round_start = time.time()
                resource_snapshots.append(self._capture_resource_snapshot())

                tasks = []

                # Health checks and basic operations for each agent
                for agent_name, agent in agents.items():
                    try:
                        if hasattr(agent, "get_health_status"):
                            tasks.append(
                                self._safe_agent_operation(
                                    agent.get_health_status, f"{agent_name}_health"
                                )
                            )
                        elif hasattr(agent, "execute_skill"):
                            tasks.append(
                                self._safe_agent_operation(
                                    lambda: agent.execute_skill("health_check", {}),
                                    f"{agent_name}_skill",
                                )
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Agent {agent_name} operation setup failed: {e}"
                        )

                # Execute filter operation
                if "filter" in agents:
                    test_content = {
                        "title": f"Agent Stress Test Round {round_num}",
                        "content": "Testing concurrent agent operations under stress conditions",
                        "topics": ["Claude Code", "A2A"],
                    }
                    tasks.append(
                        self._safe_agent_operation(
                            lambda: agents[
                                "filter"
                            ]._filter_content_by_semantic_similarity(test_content),
                            "filter_operation",
                        )
                    )

                # Execute summarise operation
                if "summarise" in agents:
                    test_text = (
                        "This is test content for summarization under concurrent load conditions. "
                        * 5
                    )
                    tasks.append(
                        self._safe_agent_operation(
                            lambda: agents["summarise"]._extractive_summarization(
                                test_text
                            ),
                            "summarise_operation",
                        )
                    )

                # Execute all tasks concurrently
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    round_duration = time.time() - round_start
                    response_times.append(round_duration)

                    # Count results
                    round_successful = 0
                    for result in results:
                        if isinstance(result, Exception):
                            failed_ops += 1
                            error_messages.append(str(result))
                        else:
                            successful_ops += 1
                            round_successful += 1

                    self.logger.info(
                        f"   Round {round_num + 1}/5: {round_successful}/{len(tasks)} operations "
                        f"successful in {round_duration:.2f}s"
                    )
                else:
                    self.logger.warning(f"Round {round_num + 1}: No tasks to execute")

                # Brief pause between rounds
                await asyncio.sleep(0.5)

        except Exception as e:
            error_messages.append(f"Concurrent agent test critical failure: {str(e)}")
            self.logger.error(f"Concurrent agent test failed: {e}")

        end_time = time.time()
        duration = end_time - start_time

        # Calculate metrics
        total_ops = successful_ops + failed_ops
        throughput = successful_ops / duration if duration > 0 else 0

        result = StressTestResult(
            test_name="concurrent_agent_operations",
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=successful_ops >= 15,  # Target: 75% success rate
            total_operations=total_ops,
            successful_operations=successful_ops,
            failed_operations=failed_ops,
            throughput=throughput,
            peak_cpu_percent=max([s.get("cpu", 0) for s in resource_snapshots] or [0]),
            peak_memory_mb=max(
                [s.get("memory_mb", 0) for s in resource_snapshots] or [0]
            ),
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            error_messages=error_messages[:5],
            metadata={
                "agents_tested": len(agents),
                "rounds": 5,
                "success_rate": successful_ops / total_ops if total_ops > 0 else 0,
            },
        )

        self.results.append(result)

        self.logger.info(
            f"✅ Concurrent agent test: {successful_ops}/{total_ops} operations "
            f"({throughput:.1f} ops/sec) - {'PASS' if result.success else 'FAIL'}"
        )

    async def _test_end_to_end_workflow_performance(self):
        """Test complete workflow under production load."""
        self.logger.info(
            "🔄 Test 3: End-to-End Workflow Performance (Target: < 5s response time)"
        )

        start_time = time.time()

        successful_workflows = 0
        failed_workflows = 0
        error_messages = []
        response_times = []
        resource_snapshots = []

        try:
            filter_agent = FilterAgent(self.config)
            summarise_agent = SummariseAgent(self.config)

            # Test 20 complete workflows
            workflow_items = []
            for i in range(20):
                workflow_items.append(
                    {
                        "id": f"workflow_{i}",
                        "title": f"Production Workflow Test #{i}",
                        "content": f"""
                    This is workflow test item #{i} for production validation.
                    The content covers Claude Code development and A2A protocol implementation.
                    Performance testing validates system behavior under realistic production loads.
                    The workflow includes filtering for relevance and generating concise summaries.
                    Resource utilization and response times are monitored throughout processing.
                    """,
                        "topics": random.choice(
                            [["Claude Code"], ["A2A"], ["Claude Code", "A2A"]]
                        ),
                    }
                )

            # Process workflows in small batches for better performance measurement
            batch_size = 4
            for batch_start in range(0, len(workflow_items), batch_size):
                batch_end = min(batch_start + batch_size, len(workflow_items))
                batch = workflow_items[batch_start:batch_end]

                batch_start_time = time.time()
                resource_snapshots.append(self._capture_resource_snapshot())

                # Process batch through complete workflow
                tasks = [
                    self._process_complete_workflow_safely(
                        filter_agent, summarise_agent, item
                    )
                    for item in batch
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                batch_duration = time.time() - batch_start_time
                response_times.append(batch_duration)

                # Count successful workflows
                batch_successful = 0
                for result in results:
                    if isinstance(result, Exception):
                        failed_workflows += 1
                        error_messages.append(str(result))
                    elif isinstance(result, dict) and result.get("success"):
                        successful_workflows += 1
                        batch_successful += 1
                    else:
                        failed_workflows += 1

                self.logger.info(
                    f"   Workflow batch {batch_start // batch_size + 1}: {batch_successful}/{len(batch)} "
                    f"completed in {batch_duration:.2f}s"
                )

                # Brief pause between batches
                await asyncio.sleep(0.5)

        except Exception as e:
            error_messages.append(f"Workflow test critical failure: {str(e)}")
            self.logger.error(f"Workflow test failed: {e}")

        end_time = time.time()
        duration = end_time - start_time

        # Calculate metrics
        total_workflows = successful_workflows + failed_workflows
        throughput = successful_workflows / duration if duration > 0 else 0
        max_response_time = max(response_times) if response_times else 0

        result = StressTestResult(
            test_name="end_to_end_workflow_performance",
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=(
                successful_workflows >= 16 and max_response_time < 5.0
            ),  # 80% success + < 5s
            total_operations=total_workflows,
            successful_operations=successful_workflows,
            failed_operations=failed_workflows,
            throughput=throughput,
            peak_cpu_percent=max([s.get("cpu", 0) for s in resource_snapshots] or [0]),
            peak_memory_mb=max(
                [s.get("memory_mb", 0) for s in resource_snapshots] or [0]
            ),
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            error_messages=error_messages[:5],
            metadata={
                "workflow_items": 20,
                "batch_size": batch_size,
                "max_response_time": max_response_time,
                "success_rate": successful_workflows / total_workflows
                if total_workflows > 0
                else 0,
            },
        )

        self.results.append(result)

        self.logger.info(
            f"✅ Workflow test: {successful_workflows}/{total_workflows} workflows "
            f"(max: {max_response_time:.2f}s) - {'PASS' if result.success else 'FAIL'}"
        )

    async def _test_circuit_breaker_resilience(self):
        """Test circuit breaker behavior under failure conditions."""
        self.logger.info(
            "⚡ Test 4: Circuit Breaker Resilience (failure detection & recovery)"
        )

        start_time = time.time()

        successful_ops = 0
        failed_ops = 0
        error_messages = []
        response_times = []
        circuit_states = []

        try:
            # Create circuit breaker for testing
            circuit_breaker = CircuitBreaker(
                name="production_stress_test",
                failure_threshold=3,
                recovery_timeout=2,
                success_threshold=2,
                half_open_max_calls=3,
            )

            # Test 1: Cause failures to open circuit
            async def failing_operation():
                await asyncio.sleep(0.1)
                raise Exception("Simulated service failure")

            for i in range(5):
                op_start = time.time()
                circuit_states.append(circuit_breaker.state.name)

                try:
                    await circuit_breaker.call(failing_operation)
                    successful_ops += 1
                except Exception as e:
                    failed_ops += 1
                    if "CircuitBreakerError" not in str(e):
                        error_messages.append(f"Failure {i + 1}: {str(e)}")

                response_times.append(time.time() - op_start)

                self.logger.info(
                    f"   Failure test {i + 1}/5: Circuit state = {circuit_breaker.state.name}"
                )

            # Test 2: Wait for recovery attempt
            self.logger.info("   Waiting for circuit breaker recovery...")
            await asyncio.sleep(3)

            # Test 3: Test recovery with successful operations
            async def succeeding_operation():
                await asyncio.sleep(0.1)
                return "success"

            for i in range(4):
                op_start = time.time()
                circuit_states.append(circuit_breaker.state.name)

                try:
                    result = await circuit_breaker.call(succeeding_operation)
                    if result == "success":
                        successful_ops += 1
                    else:
                        failed_ops += 1
                except Exception as e:
                    failed_ops += 1
                    error_messages.append(f"Recovery test {i + 1}: {str(e)}")

                response_times.append(time.time() - op_start)

                self.logger.info(
                    f"   Recovery test {i + 1}/4: Circuit state = {circuit_breaker.state.name}"
                )

                await asyncio.sleep(0.2)

        except Exception as e:
            error_messages.append(f"Circuit breaker test critical failure: {str(e)}")
            self.logger.error(f"Circuit breaker test failed: {e}")

        end_time = time.time()
        duration = end_time - start_time

        # Analyze state transitions
        unique_states = list(set(circuit_states))
        has_transitions = len(unique_states) >= 2

        result = StressTestResult(
            test_name="circuit_breaker_resilience",
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=has_transitions,  # Success if we see state transitions
            total_operations=successful_ops + failed_ops,
            successful_operations=successful_ops,
            failed_operations=failed_ops,
            throughput=(successful_ops + failed_ops) / duration if duration > 0 else 0,
            peak_cpu_percent=psutil.cpu_percent(),
            peak_memory_mb=psutil.virtual_memory().used / 1024 / 1024,
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            error_messages=error_messages[:3],
            metadata={
                "circuit_states_observed": unique_states,
                "state_transitions": has_transitions,
                "total_operations": len(circuit_states),
            },
        )

        self.results.append(result)

        self.logger.info(
            f"✅ Circuit breaker test: States {unique_states} - "
            f"{'PASS' if result.success else 'FAIL'}"
        )

    async def _test_resource_scaling_behavior(self):
        """Test system behavior under increasing resource load."""
        self.logger.info("📈 Test 5: Resource Scaling Behavior (load progression)")

        start_time = time.time()

        successful_ops = 0
        failed_ops = 0
        error_messages = []
        response_times = []
        resource_snapshots = []

        try:
            filter_agent = FilterAgent(self.config)

            # Progressive load testing: 5, 10, 15, 20 concurrent operations
            load_levels = [5, 10, 15, 20]

            for load_level in load_levels:
                self.logger.info(
                    f"   Testing load level: {load_level} concurrent operations"
                )

                level_start = time.time()
                resource_snapshots.append(self._capture_resource_snapshot())

                # Create concurrent tasks for this load level
                tasks = []
                for i in range(load_level):
                    test_content = {
                        "title": f"Load Test {load_level}-{i}",
                        "content": "Testing system under progressive load conditions",
                        "topics": ["Claude Code"],
                    }
                    tasks.append(self._process_post_safely(filter_agent, test_content))

                # Execute all tasks concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)

                level_duration = time.time() - level_start
                response_times.append(level_duration)

                # Count results for this load level
                level_successful = 0
                for result in results:
                    if isinstance(result, Exception):
                        failed_ops += 1
                        error_messages.append(str(result))
                    elif isinstance(result, dict) and result.get("success"):
                        successful_ops += 1
                        level_successful += 1
                    else:
                        failed_ops += 1

                self.logger.info(
                    f"   Load {load_level}: {level_successful}/{load_level} operations "
                    f"completed in {level_duration:.2f}s"
                )

                # Brief recovery period between load levels
                await asyncio.sleep(1)

        except Exception as e:
            error_messages.append(f"Resource scaling test critical failure: {str(e)}")
            self.logger.error(f"Resource scaling test failed: {e}")

        end_time = time.time()
        duration = end_time - start_time

        # Calculate metrics
        total_ops = successful_ops + failed_ops
        throughput = successful_ops / duration if duration > 0 else 0

        result = StressTestResult(
            test_name="resource_scaling_behavior",
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=successful_ops >= 40,  # Target: Handle progressive load
            total_operations=total_ops,
            successful_operations=successful_ops,
            failed_operations=failed_ops,
            throughput=throughput,
            peak_cpu_percent=max([s.get("cpu", 0) for s in resource_snapshots] or [0]),
            peak_memory_mb=max(
                [s.get("memory_mb", 0) for s in resource_snapshots] or [0]
            ),
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            error_messages=error_messages[:3],
            metadata={
                "load_levels_tested": load_levels,
                "total_expected_operations": sum(load_levels),
                "success_rate": successful_ops / total_ops if total_ops > 0 else 0,
            },
        )

        self.results.append(result)

        self.logger.info(
            f"✅ Resource scaling test: {successful_ops}/{total_ops} operations "
            f"({throughput:.1f} ops/sec) - {'PASS' if result.success else 'FAIL'}"
        )

    # Helper methods

    async def _process_post_safely(self, filter_agent, post):
        """Safely process a post with error handling."""
        try:
            result = await filter_agent._filter_content_by_semantic_similarity(post)
            return {"success": result.get("status") == "success", "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _safe_agent_operation(self, operation, operation_name):
        """Safely execute an agent operation."""
        try:
            if asyncio.iscoroutinefunction(operation):
                result = await operation()
            else:
                result = operation()
            return {"success": True, "operation": operation_name, "result": result}
        except Exception as e:
            return {"success": False, "operation": operation_name, "error": str(e)}

    async def _process_complete_workflow_safely(
        self, filter_agent, summarise_agent, item
    ):
        """Process item through complete workflow safely."""
        try:
            # Step 1: Filter content
            filter_result = await filter_agent._filter_content_by_semantic_similarity(
                item
            )

            if filter_result.get("status") != "success":
                return {"success": False, "error": "Filter stage failed"}

            # Step 2: Summarise if relevant
            if filter_result.get("result", {}).get("is_relevant"):
                summary = summarise_agent._extractive_summarization(
                    item["content"], max_sentences=2
                )
                return {"success": True, "summary": summary}
            else:
                return {"success": True, "summary": "Not relevant"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _capture_resource_snapshot(self) -> dict[str, Any]:
        """Capture current resource usage."""
        try:
            return {
                "timestamp": time.time(),
                "cpu": psutil.cpu_percent(0.1),
                "memory_mb": psutil.virtual_memory().used / 1024 / 1024,
                "memory_percent": psutil.virtual_memory().percent,
            }
        except Exception:
            return {
                "timestamp": time.time(),
                "cpu": 0,
                "memory_mb": 0,
                "memory_percent": 0,
            }

    def _generate_production_report(self) -> dict[str, Any]:
        """Generate production readiness report."""
        if not self.results:
            return {"error": "No test results available"}

        # Overall statistics
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r.success])

        total_operations = sum(r.total_operations for r in self.results)
        total_successful_ops = sum(r.successful_operations for r in self.results)

        # Validation against production targets
        validation_results = {}

        # Target 1: Throughput (50+ posts per cycle)
        multi_topic_result = next(
            (r for r in self.results if "multi_topic" in r.test_name), None
        )
        if multi_topic_result:
            validation_results["throughput"] = {
                "target": 50,
                "achieved": multi_topic_result.successful_operations,
                "passed": multi_topic_result.successful_operations >= 50,
                "metric": "posts per monitoring cycle",
            }

        # Target 2: Response time (< 5 seconds)
        workflow_result = next(
            (r for r in self.results if "workflow" in r.test_name), None
        )
        if workflow_result:
            max_response_time = workflow_result.metadata.get("max_response_time", 0)
            validation_results["response_time"] = {
                "target": 5.0,
                "achieved": max_response_time,
                "passed": max_response_time < 5.0,
                "metric": "seconds for complete workflow",
            }

        # Target 3: Reliability (99%+ success rate)
        overall_success_rate = (
            total_successful_ops / total_operations if total_operations > 0 else 0
        )
        validation_results["reliability"] = {
            "target": 0.99,
            "achieved": overall_success_rate,
            "passed": overall_success_rate >= 0.99,
            "metric": "success rate under normal load",
        }

        # Calculate production readiness score
        passed_validations = sum(1 for v in validation_results.values() if v["passed"])
        test_success_rate = successful_tests / total_tests if total_tests > 0 else 0

        production_readiness_score = (
            (
                (test_success_rate * 0.3)  # Test success rate (30%)
                + (
                    passed_validations / len(validation_results) * 0.7
                )  # Target validation (70%)
            )
            if validation_results
            else test_success_rate
        )

        # Performance metrics
        peak_cpu = max([r.peak_cpu_percent for r in self.results] or [0])
        peak_memory = max([r.peak_memory_mb for r in self.results] or [0])
        avg_throughput = statistics.mean(
            [r.throughput for r in self.results if r.throughput > 0]
        )

        # Generate recommendations
        recommendations = self._generate_production_recommendations(validation_results)

        return {
            "production_stress_test_summary": {
                "timestamp": time.time(),
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "test_success_rate": test_success_rate,
                "total_operations": total_operations,
                "successful_operations": total_successful_ops,
                "overall_success_rate": overall_success_rate,
            },
            "validation_results": validation_results,
            "production_readiness": {
                "score": production_readiness_score,
                "rating": self._get_production_rating(production_readiness_score),
                "ready_for_production": production_readiness_score >= 0.8,
            },
            "performance_metrics": {
                "peak_cpu_percent": peak_cpu,
                "peak_memory_mb": peak_memory,
                "average_throughput": avg_throughput if avg_throughput > 0 else 0,
            },
            "test_details": [
                {
                    "test_name": r.test_name,
                    "success": r.success,
                    "duration": r.duration,
                    "operations": r.total_operations,
                    "success_rate": r.successful_operations / r.total_operations
                    if r.total_operations > 0
                    else 0,
                    "throughput": r.throughput,
                    "avg_response_time": r.avg_response_time,
                    "metadata": r.metadata,
                }
                for r in self.results
            ],
            "recommendations": recommendations,
            "capacity_planning": self._generate_capacity_planning(),
        }

    def _generate_production_recommendations(
        self, validation_results: dict[str, Any]
    ) -> list[str]:
        """Generate production readiness recommendations."""
        recommendations = []

        for target, result in validation_results.items():
            if not result["passed"]:
                if target == "throughput":
                    recommendations.append(
                        f"Improve throughput: Achieved {result['achieved']} posts, target {result['target']}+"
                    )
                elif target == "response_time":
                    recommendations.append(
                        f"Optimize response time: Current {result['achieved']:.2f}s exceeds {result['target']}s target"
                    )
                elif target == "reliability":
                    recommendations.append(
                        f"Enhance reliability: Success rate {result['achieved']:.1%} below {result['target']:.0%} target"
                    )

        # Resource usage recommendations
        peak_cpu = max([r.peak_cpu_percent for r in self.results] or [0])
        peak_memory = max([r.peak_memory_mb for r in self.results] or [0])

        if peak_cpu > 80:
            recommendations.append(
                f"High CPU usage ({peak_cpu:.1f}%) - consider horizontal scaling"
            )

        if peak_memory > 4000:
            recommendations.append(
                f"High memory usage ({peak_memory:.0f}MB) - optimize memory management"
            )

        # Test-specific recommendations
        failed_tests = [r for r in self.results if not r.success]
        if failed_tests:
            recommendations.append(
                f"Address {len(failed_tests)} failed tests to improve system reliability"
            )

        if not recommendations:
            recommendations.append(
                "System meets all production requirements - ready for deployment"
            )

        return recommendations

    def _generate_capacity_planning(self) -> dict[str, Any]:
        """Generate capacity planning guidelines."""
        peak_cpu = max([r.peak_cpu_percent for r in self.results] or [0])
        peak_memory = max([r.peak_memory_mb for r in self.results] or [0])
        best_throughput = max(
            [r.throughput for r in self.results if r.throughput > 0] or [0]
        )

        return {
            "current_performance": {
                "peak_cpu_percent": peak_cpu,
                "peak_memory_mb": peak_memory,
                "best_throughput_per_sec": best_throughput,
            },
            "production_sizing": {
                "recommended_cpu_cores": max(2, int(peak_cpu / 50)),
                "recommended_memory_gb": max(4, int(peak_memory / 1024 * 1.5)),
                "estimated_daily_capacity": best_throughput * 3600 * 6
                if best_throughput > 0
                else 0,
            },
        }

    def _get_production_rating(self, score: float) -> str:
        """Get production readiness rating."""
        if score >= 0.9:
            return "EXCELLENT - Ready for production"
        elif score >= 0.8:
            return "GOOD - Ready for production"
        elif score >= 0.7:
            return "FAIR - Needs optimization"
        elif score >= 0.6:
            return "POOR - Major improvements needed"
        else:
            return "CRITICAL - Not ready for production"

    def _export_results(self, report: dict[str, Any]):
        """Export stress test results."""
        timestamp = int(time.time())

        # JSON report
        json_file = f"production_stress_test_report_{timestamp}.json"
        with open(json_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

        # Text summary
        summary_file = f"production_stress_test_summary_{timestamp}.txt"
        with open(summary_file, "w") as f:
            f.write("REDDIT TECHNICAL WATCHER - PRODUCTION STRESS TEST REPORT\n")
            f.write("=" * 70 + "\n\n")

            readiness = report["production_readiness"]
            f.write(f"Production Readiness: {readiness['rating']}\n")
            f.write(f"Overall Score: {readiness['score']:.1%}\n")
            f.write(
                f"Ready for Production: {'YES' if readiness['ready_for_production'] else 'NO'}\n\n"
            )

            f.write("VALIDATION RESULTS:\n")
            for target, result in report["validation_results"].items():
                status = "PASS" if result["passed"] else "FAIL"
                f.write(
                    f"{status}: {target} - {result['achieved']} (target: {result['target']})\n"
                )

            f.write("\nTEST RESULTS:\n")
            summary = report["production_stress_test_summary"]
            f.write(
                f"Tests: {summary['successful_tests']}/{summary['total_tests']} passed\n"
            )
            f.write(
                f"Operations: {summary['successful_operations']}/{summary['total_operations']} successful\n"
            )

            f.write("\nRECOMMENDATIONS:\n")
            for i, rec in enumerate(report["recommendations"], 1):
                f.write(f"{i}. {rec}\n")

        self.logger.info(f"📊 Results exported: {json_file}, {summary_file}")


async def main():
    """Run production stress testing."""
    print("🚀 Reddit Technical Watcher - Production Stress Test")
    print("=" * 70)
    print("Validating system readiness for production deployment...")
    print()

    stress_test = ProductionStressTest()

    try:
        report = await stress_test.run_production_stress_tests()

        # Display results
        print("\n" + "=" * 70)
        print("📊 PRODUCTION STRESS TEST RESULTS")
        print("=" * 70)

        readiness = report["production_readiness"]
        print(f"\n🎯 PRODUCTION READINESS: {readiness['rating']}")
        print(f"Overall Score: {readiness['score']:.1%}")
        print(
            f"Ready for Production: {'✅ YES' if readiness['ready_for_production'] else '❌ NO'}"
        )

        print("\n📋 VALIDATION AGAINST TARGETS:")
        print("-" * 50)
        for target, result in report["validation_results"].items():
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(
                f"{status} {target}: {result['achieved']} (target: {result['target']} {result['metric']})"
            )

        print("\n⚡ PERFORMANCE SUMMARY:")
        print("-" * 50)
        summary = report["production_stress_test_summary"]
        perf = report["performance_metrics"]

        print(
            f"Test Success Rate: {summary['test_success_rate']:.1%} ({summary['successful_tests']}/{summary['total_tests']})"
        )
        print(
            f"Operation Success Rate: {summary['overall_success_rate']:.1%} ({summary['successful_operations']}/{summary['total_operations']})"
        )
        print(f"Peak CPU Usage: {perf['peak_cpu_percent']:.1f}%")
        print(f"Peak Memory Usage: {perf['peak_memory_mb']:.0f} MB")
        if perf["average_throughput"] > 0:
            print(
                f"Average Throughput: {perf['average_throughput']:.1f} operations/second"
            )

        print("\n🧪 TEST DETAILS:")
        print("-" * 50)
        for test in report["test_details"]:
            status = "✅" if test["success"] else "❌"
            print(
                f"{status} {test['test_name']}: {test['success_rate']:.1%} success rate"
            )
            print(
                f"   {test['operations']} operations in {test['duration']:.1f}s ({test['throughput']:.1f} ops/sec)"
            )

        print("\n💡 RECOMMENDATIONS:")
        print("-" * 50)
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"{i}. {rec}")

        print("\n" + "=" * 70)
        if readiness["ready_for_production"]:
            print("🎉 ASSESSMENT: System is ready for production deployment!")
        else:
            print("⚠️  ASSESSMENT: System needs optimization before production.")
        print("=" * 70)

        return 0 if readiness["ready_for_production"] else 1

    except Exception as e:
        print(f"\n❌ Production stress testing failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
