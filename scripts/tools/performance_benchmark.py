#!/usr/bin/env python3

# ABOUTME: Performance benchmark tool for testing system optimizations and resource usage
# ABOUTME: Measures ML model loading, database performance, and overall throughput improvements

import asyncio
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from reddit_watcher.agents.filter_agent import FilterAgent
from reddit_watcher.agents.summarise_agent import SummariseAgent
from reddit_watcher.config import get_settings
from reddit_watcher.database.utils import check_database_health, get_database_engine
from reddit_watcher.performance.ml_model_cache import (
    get_model_cache,
)
from reddit_watcher.performance.resource_monitor import (
    PerformanceTimer,
    cleanup_resource_monitoring,
    get_resource_monitor,
    initialize_resource_monitoring,
)


@dataclass
class BenchmarkResults:
    """Results from performance benchmarks."""

    test_name: str
    duration: float
    success: bool
    throughput: float = 0.0
    memory_usage_mb: float = 0.0
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class PerformanceBenchmark:
    """
    Performance benchmark suite for testing system optimizations.

    Tests:
    - ML model loading and caching performance
    - Database connection pooling and query performance
    - Agent skill execution benchmarks
    - Resource usage monitoring validation
    - Overall system throughput measurements
    """

    def __init__(self):
        self.config = get_settings()
        self.resource_monitor = get_resource_monitor()
        self.model_cache = get_model_cache()
        self.results: list[BenchmarkResults] = []

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

    async def run_all_benchmarks(self) -> dict[str, Any]:
        """Run the complete benchmark suite."""
        self.logger.info("Starting performance benchmark suite...")

        # Initialize monitoring
        await initialize_resource_monitoring()

        try:
            # Run benchmarks in order
            await self._benchmark_ml_model_loading()
            await self._benchmark_ml_model_inference()
            await self._benchmark_database_operations()
            await self._benchmark_agent_performance()
            await self._benchmark_system_throughput()

            # Collect final metrics
            final_summary = self._generate_summary()

            # Export results
            await self._export_results()

            return final_summary

        finally:
            await cleanup_resource_monitoring()

    async def _benchmark_ml_model_loading(self):
        """Benchmark ML model loading and caching performance."""
        self.logger.info("🔬 Benchmarking ML model loading performance...")

        # Test sentence transformer loading
        with PerformanceTimer("ml_model_loading_sentence_transformer"):
            try:
                start_time = time.time()
                await self.model_cache.get_sentence_transformer("all-MiniLM-L6-v2")
                duration = time.time() - start_time

                self.results.append(
                    BenchmarkResults(
                        test_name="sentence_transformer_loading",
                        duration=duration,
                        success=True,
                        metadata={
                            "model_name": "all-MiniLM-L6-v2",
                            "gpu_available": self.model_cache._gpu_available,
                            "device": self.model_cache._get_device(),
                        },
                    )
                )

                self.logger.info(f"✅ SentenceTransformer loaded in {duration:.2f}s")

            except Exception as e:
                self.results.append(
                    BenchmarkResults(
                        test_name="sentence_transformer_loading",
                        duration=0.0,
                        success=False,
                        error_message=str(e),
                    )
                )
                self.logger.error(f"❌ SentenceTransformer loading failed: {e}")

        # Test spaCy model loading
        with PerformanceTimer("ml_model_loading_spacy"):
            try:
                start_time = time.time()
                nlp = await self.model_cache.get_spacy_model(
                    "en_core_web_sm", fallback_to_blank=True
                )
                duration = time.time() - start_time

                self.results.append(
                    BenchmarkResults(
                        test_name="spacy_model_loading",
                        duration=duration,
                        success=True,
                        metadata={
                            "model_name": "en_core_web_sm",
                            "pipe_names": list(nlp.pipe_names),
                        },
                    )
                )

                self.logger.info(f"✅ spaCy model loaded in {duration:.2f}s")

            except Exception as e:
                self.results.append(
                    BenchmarkResults(
                        test_name="spacy_model_loading",
                        duration=0.0,
                        success=False,
                        error_message=str(e),
                    )
                )
                self.logger.error(f"❌ spaCy model loading failed: {e}")

        # Test cache performance (second load should be faster)
        with PerformanceTimer("ml_model_cached_loading"):
            try:
                start_time = time.time()
                await self.model_cache.get_sentence_transformer("all-MiniLM-L6-v2")
                duration = time.time() - start_time

                self.results.append(
                    BenchmarkResults(
                        test_name="cached_model_loading",
                        duration=duration,
                        success=True,
                        metadata={"from_cache": True},
                    )
                )

                self.logger.info(f"✅ Cached model loaded in {duration:.4f}s")

            except Exception as e:
                self.results.append(
                    BenchmarkResults(
                        test_name="cached_model_loading",
                        duration=0.0,
                        success=False,
                        error_message=str(e),
                    )
                )

    async def _benchmark_ml_model_inference(self):
        """Benchmark ML model inference performance."""
        self.logger.info("🧠 Benchmarking ML model inference performance...")

        # Get model
        model = await self.model_cache.get_sentence_transformer("all-MiniLM-L6-v2")

        # Test data
        test_texts = [
            "Claude Code is an AI-powered development tool",
            "Agent-to-Agent protocol enables distributed AI systems",
            "Reddit monitoring for technical content discovery",
            "Performance optimization for machine learning models",
            "Database connection pooling improves system efficiency",
        ] * 10  # 50 texts total

        # Benchmark optimized encoding
        with PerformanceTimer("ml_optimized_inference"):
            try:
                start_time = time.time()
                embeddings = await self.model_cache.encode_texts_optimized(
                    model, test_texts, batch_size=32
                )
                duration = time.time() - start_time
                throughput = len(test_texts) / duration

                self.results.append(
                    BenchmarkResults(
                        test_name="optimized_text_encoding",
                        duration=duration,
                        success=True,
                        throughput=throughput,
                        metadata={
                            "text_count": len(test_texts),
                            "batch_size": 32,
                            "embedding_dim": embeddings.shape[1]
                            if len(embeddings) > 0
                            else 0,
                        },
                    )
                )

                self.logger.info(
                    f"✅ Encoded {len(test_texts)} texts in {duration:.2f}s "
                    f"({throughput:.1f} texts/sec)"
                )

            except Exception as e:
                self.results.append(
                    BenchmarkResults(
                        test_name="optimized_text_encoding",
                        duration=0.0,
                        success=False,
                        error_message=str(e),
                    )
                )
                self.logger.error(f"❌ Text encoding failed: {e}")

    async def _benchmark_database_operations(self):
        """Benchmark database connection pooling and query performance."""
        self.logger.info("🗄️ Benchmarking database operations...")

        # Test database health check
        with PerformanceTimer("database_health_check"):
            try:
                start_time = time.time()
                health = check_database_health()
                duration = time.time() - start_time

                self.results.append(
                    BenchmarkResults(
                        test_name="database_health_check",
                        duration=duration,
                        success=health.get("status") == "healthy",
                        metadata=health,
                    )
                )

                self.logger.info(
                    f"✅ Database health check completed in {duration:.3f}s "
                    f"(status: {health.get('status')})"
                )

            except Exception as e:
                self.results.append(
                    BenchmarkResults(
                        test_name="database_health_check",
                        duration=0.0,
                        success=False,
                        error_message=str(e),
                    )
                )
                self.logger.error(f"❌ Database health check failed: {e}")

        # Test connection pool performance
        with PerformanceTimer("database_connection_pool"):
            try:
                start_time = time.time()
                engine = get_database_engine()

                # Test multiple concurrent connections
                async def test_connection():
                    from reddit_watcher.database.utils import get_db_session

                    with get_db_session() as session:
                        from sqlalchemy import text

                        result = session.execute(text("SELECT 1"))
                        return result.scalar()

                # Run 10 concurrent connection tests
                tasks = [test_connection() for _ in range(10)]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                duration = time.time() - start_time
                successes = sum(1 for r in results if r == 1)

                self.results.append(
                    BenchmarkResults(
                        test_name="connection_pool_concurrency",
                        duration=duration,
                        success=successes == 10,
                        throughput=10 / duration,
                        metadata={
                            "concurrent_connections": 10,
                            "successful_connections": successes,
                            "pool_size": engine.pool.size(),
                            "checked_out": engine.pool.checkedout(),
                        },
                    )
                )

                self.logger.info(
                    f"✅ Connection pool test: {successes}/10 connections in {duration:.3f}s"
                )

            except Exception as e:
                self.results.append(
                    BenchmarkResults(
                        test_name="connection_pool_concurrency",
                        duration=0.0,
                        success=False,
                        error_message=str(e),
                    )
                )
                self.logger.error(f"❌ Connection pool test failed: {e}")

    async def _benchmark_agent_performance(self):
        """Benchmark A2A agent performance."""
        self.logger.info("🤖 Benchmarking agent performance...")

        # Test FilterAgent semantic similarity
        try:
            filter_agent = FilterAgent(self.config)

            with PerformanceTimer("filter_agent_semantic_similarity"):
                start_time = time.time()

                result = await filter_agent._filter_content_by_semantic_similarity(
                    {
                        "content": "Claude Code is revolutionizing AI development with agent-to-agent protocols",
                        "title": "Claude Code A2A Implementation",
                        "topics": ["Claude Code", "A2A", "Agent-to-Agent"],
                    }
                )

                duration = time.time() - start_time

                self.results.append(
                    BenchmarkResults(
                        test_name="filter_agent_semantic_similarity",
                        duration=duration,
                        success=result.get("status") == "success",
                        metadata={
                            "max_similarity": result.get("result", {}).get(
                                "max_similarity", 0.0
                            ),
                            "is_relevant": result.get("result", {}).get(
                                "is_relevant", False
                            ),
                        },
                    )
                )

                self.logger.info(
                    f"✅ FilterAgent semantic similarity in {duration:.3f}s "
                    f"(similarity: {result.get('result', {}).get('max_similarity', 0.0):.3f})"
                )

        except Exception as e:
            self.results.append(
                BenchmarkResults(
                    test_name="filter_agent_semantic_similarity",
                    duration=0.0,
                    success=False,
                    error_message=str(e),
                )
            )
            self.logger.error(f"❌ FilterAgent benchmark failed: {e}")

        # Test SummariseAgent (if Gemini is configured)
        if self.config.has_gemini_credentials():
            try:
                summarise_agent = SummariseAgent(self.config)

                with PerformanceTimer("summarise_agent_fallback"):
                    start_time = time.time()

                    # Test extractive summarization (fallback)
                    content = """
                    Claude Code represents a significant advancement in AI development tools.
                    The Agent-to-Agent protocol enables distributed AI systems to communicate effectively.
                    Performance optimization is crucial for production deployment.
                    Machine learning models require careful resource management.
                    Database connection pooling improves system efficiency significantly.
                    """

                    result = summarise_agent._extractive_summarization(
                        content, max_sentences=2
                    )
                    duration = time.time() - start_time

                    self.results.append(
                        BenchmarkResults(
                            test_name="summarise_agent_extractive",
                            duration=duration,
                            success=bool(result),
                            metadata={
                                "input_length": len(content),
                                "output_length": len(result) if result else 0,
                            },
                        )
                    )

                    self.logger.info(
                        f"✅ SummariseAgent extractive summary in {duration:.3f}s"
                    )

            except Exception as e:
                self.results.append(
                    BenchmarkResults(
                        test_name="summarise_agent_extractive",
                        duration=0.0,
                        success=False,
                        error_message=str(e),
                    )
                )
                self.logger.error(f"❌ SummariseAgent benchmark failed: {e}")

    async def _benchmark_system_throughput(self):
        """Benchmark overall system throughput."""
        self.logger.info("⚡ Benchmarking system throughput...")

        # Simulate workflow processing
        try:
            filter_agent = FilterAgent(self.config)

            # Test batch processing
            test_posts = [
                {
                    "title": f"Claude Code Development Update {i}",
                    "content": f"Latest improvements to the A2A protocol implementation for post {i}",
                    "topics": ["Claude Code", "A2A"],
                }
                for i in range(50)
            ]

            with PerformanceTimer("system_throughput_test"):
                start_time = time.time()

                # Process posts in batches
                batch_size = 10
                processed = 0

                for i in range(0, len(test_posts), batch_size):
                    batch = test_posts[i : i + batch_size]

                    # Process batch concurrently
                    tasks = [
                        filter_agent._filter_content_by_semantic_similarity(post)
                        for post in batch
                    ]

                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    successful = sum(
                        1
                        for r in results
                        if isinstance(r, dict) and r.get("status") == "success"
                    )
                    processed += successful

                duration = time.time() - start_time
                throughput = processed / duration

                self.results.append(
                    BenchmarkResults(
                        test_name="system_throughput",
                        duration=duration,
                        success=processed > 0,
                        throughput=throughput,
                        metadata={
                            "total_posts": len(test_posts),
                            "processed_posts": processed,
                            "batch_size": batch_size,
                        },
                    )
                )

                self.logger.info(
                    f"✅ System throughput: {processed} posts in {duration:.2f}s "
                    f"({throughput:.1f} posts/sec)"
                )

        except Exception as e:
            self.results.append(
                BenchmarkResults(
                    test_name="system_throughput",
                    duration=0.0,
                    success=False,
                    error_message=str(e),
                )
            )
            self.logger.error(f"❌ System throughput test failed: {e}")

    def _generate_summary(self) -> dict[str, Any]:
        """Generate benchmark summary."""
        successful_tests = [r for r in self.results if r.success]
        failed_tests = [r for r in self.results if not r.success]

        # Calculate metrics
        total_duration = sum(r.duration for r in successful_tests)
        avg_throughput = sum(
            r.throughput for r in successful_tests if r.throughput > 0
        ) / max(1, len([r for r in successful_tests if r.throughput > 0]))

        # Get current resource metrics
        current_metrics = self.resource_monitor.get_current_metrics()
        performance_summary = self.resource_monitor.get_performance_summary()
        agent_summary = self.resource_monitor.get_agent_performance_summary()
        cache_info = self.model_cache.get_cache_info()

        summary = {
            "benchmark_results": {
                "total_tests": len(self.results),
                "successful_tests": len(successful_tests),
                "failed_tests": len(failed_tests),
                "success_rate": len(successful_tests) / len(self.results)
                if self.results
                else 0.0,
                "total_duration": total_duration,
                "average_throughput": avg_throughput,
            },
            "test_details": [
                {
                    "test_name": r.test_name,
                    "duration": r.duration,
                    "success": r.success,
                    "throughput": r.throughput,
                    "error": r.error_message if not r.success else None,
                    "metadata": r.metadata,
                }
                for r in self.results
            ],
            "resource_metrics": {
                "current": current_metrics.__dict__ if current_metrics else None,
                "performance_summary": performance_summary,
                "agent_summary": agent_summary,
            },
            "ml_model_cache": cache_info,
            "recommendations": self._generate_recommendations(),
        }

        return summary

    def _generate_recommendations(self) -> list[str]:
        """Generate performance optimization recommendations."""
        recommendations = []

        # Analyze results and provide recommendations
        ml_loading_tests = [r for r in self.results if "loading" in r.test_name]
        slow_loading = [r for r in ml_loading_tests if r.duration > 5.0]

        if slow_loading:
            recommendations.append(
                "Consider preloading ML models during application startup for faster response times"
            )

        throughput_tests = [r for r in self.results if r.throughput > 0]
        if throughput_tests:
            avg_throughput = sum(r.throughput for r in throughput_tests) / len(
                throughput_tests
            )
            if avg_throughput < 10:
                recommendations.append(
                    "System throughput is below optimal. Consider increasing batch sizes or optimizing model inference"
                )

        # Check for failed tests
        failed_tests = [r for r in self.results if not r.success]
        if failed_tests:
            recommendations.append(
                f"Address {len(failed_tests)} failed tests to improve system reliability"
            )

        # Resource usage recommendations
        current_metrics = self.resource_monitor.get_current_metrics()
        if current_metrics:
            if current_metrics.memory_percent > 80:
                recommendations.append(
                    "High memory usage detected. Consider implementing memory optimization strategies"
                )
            if current_metrics.cpu_percent > 80:
                recommendations.append(
                    "High CPU usage detected. Consider scaling horizontally or optimizing CPU-intensive operations"
                )

        if not recommendations:
            recommendations.append(
                "System performance is optimal. No immediate optimizations needed."
            )

        return recommendations

    async def _export_results(self):
        """Export benchmark results."""
        timestamp = int(time.time())
        export_file = f"performance_benchmark_results_{timestamp}.json"

        try:
            self.resource_monitor.export_metrics(export_file)
            self.logger.info(f"📊 Benchmark results exported to {export_file}")
        except Exception as e:
            self.logger.error(f"Failed to export results: {e}")


async def main():
    """Run the performance benchmark suite."""
    print("🚀 Reddit Technical Watcher - Performance Benchmark Suite")
    print("=" * 60)

    benchmark = PerformanceBenchmark()

    try:
        results = await benchmark.run_all_benchmarks()

        # Print summary
        print("\n📊 BENCHMARK SUMMARY")
        print("=" * 40)

        bench_results = results["benchmark_results"]
        print(f"Total Tests: {bench_results['total_tests']}")
        print(f"Successful: {bench_results['successful_tests']}")
        print(f"Failed: {bench_results['failed_tests']}")
        print(f"Success Rate: {bench_results['success_rate']:.1%}")
        print(f"Total Duration: {bench_results['total_duration']:.2f}s")

        if bench_results["average_throughput"] > 0:
            print(
                f"Average Throughput: {bench_results['average_throughput']:.1f} ops/sec"
            )

        # Print test details
        print("\n📋 TEST RESULTS")
        print("-" * 40)
        for test in results["test_details"]:
            status = "✅" if test["success"] else "❌"
            print(f"{status} {test['test_name']}: {test['duration']:.3f}s")
            if test["throughput"] > 0:
                print(f"   Throughput: {test['throughput']:.1f} ops/sec")
            if test["error"]:
                print(f"   Error: {test['error']}")

        # Print recommendations
        print("\n💡 RECOMMENDATIONS")
        print("-" * 40)
        for i, rec in enumerate(results["recommendations"], 1):
            print(f"{i}. {rec}")

        print("\n🎉 Benchmark completed successfully!")

        return 0

    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
