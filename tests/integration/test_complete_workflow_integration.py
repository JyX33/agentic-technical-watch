#!/usr/bin/env python3
# ABOUTME: Complete end-to-end workflow integration test for Reddit Technical Watcher
# ABOUTME: Tests full pipeline: Collect → Filter → Summarize → Alert with performance metrics

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from reddit_watcher.agents.coordinator_agent import CoordinatorAgent
from reddit_watcher.config import get_settings
from reddit_watcher.database.utils import get_db_session
from reddit_watcher.models import (
    ContentFilter,
    ContentSummary,
    RedditPost,
    WorkflowExecution,
)


class WorkflowIntegrationTester:
    """Complete workflow integration test framework."""

    def __init__(self):
        self.config = get_settings()
        self.coordinator = CoordinatorAgent(self.config)
        self.test_results = {
            "execution_time": {},
            "data_flow": {},
            "performance_metrics": {},
            "error_handling": {},
            "workflow_validation": {},
        }
        self.setup_logging()

    def setup_logging(self):
        """Setup comprehensive logging for workflow testing."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("workflow_integration_test.log"),
            ],
        )
        self.logger = logging.getLogger(__name__)

    async def test_complete_workflow_pipeline(self) -> dict[str, Any]:
        """
        CRITICAL MISSION: Execute and validate the complete monitoring workflow.

        Pipeline: Collect → Filter → Summarize → Alert
        Test Cases:
        1. Real Reddit data collection for target topics
        2. Content filtering with keyword + semantic similarity
        3. AI summarization using Gemini 2.5 Flash
        4. Alert distribution via Slack and email
        """
        print("🚀 COMPLETE WORKFLOW INTEGRATION TEST")
        print("=" * 60)
        print(f"⏰ Started at: {datetime.now(UTC).isoformat()}")

        # Target topics for testing
        test_topics = ["Claude Code", "A2A", "Agent-to-Agent"]
        test_subreddits = ["MachineLearning", "artificial", "singularity"]

        try:
            # Phase 1: Pre-flight checks
            print("\n📋 Phase 1: Pre-flight System Checks")
            await self._validate_system_requirements()

            # Phase 2: Execute complete workflow
            print("\n🔄 Phase 2: Complete Workflow Execution")
            workflow_result = await self._execute_complete_workflow(
                test_topics, test_subreddits
            )

            # Phase 3: Validate data persistence
            print("\n💾 Phase 3: Data Persistence Validation")
            await self._validate_data_persistence(workflow_result)

            # Phase 4: Performance analysis
            print("\n⚡ Phase 4: Performance Analysis")
            await self._analyze_performance_metrics(workflow_result)

            # Phase 5: Error handling tests
            print("\n🛡️ Phase 5: Error Handling Tests")
            await self._test_error_handling()

            # Phase 6: Generate comprehensive report
            print("\n📊 Phase 6: Comprehensive Report Generation")
            report = await self._generate_integration_report(workflow_result)

            return report

        except Exception as e:
            self.logger.error(f"Complete workflow test failed: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        finally:
            await self._cleanup_resources()

    async def _validate_system_requirements(self) -> None:
        """Validate all system requirements before workflow execution."""
        print("🔍 Validating system requirements...")

        # Check database connectivity
        try:
            with get_db_session() as session:
                session.execute(text("SELECT 1"))
            print("✅ Database connectivity: OK")
        except Exception as e:
            raise RuntimeError(f"Database connectivity failed: {e}")

        # Check agent health
        try:
            health_result = await self.coordinator.execute_skill("health_check", {})
            if health_result.get("status") == "success":
                print("✅ Coordinator agent health: OK")
            else:
                print(f"⚠️ Coordinator agent health: {health_result}")
        except Exception as e:
            print(f"⚠️ Coordinator agent health check failed: {e}")

        # Check configuration
        required_config = ["reddit_client_id", "reddit_client_secret", "gemini_api_key"]

        for config_key in required_config:
            if not getattr(self.config, config_key, None):
                raise RuntimeError(f"Missing required configuration: {config_key}")

        print("✅ Configuration validation: OK")

    async def _execute_complete_workflow(
        self, topics: list[str], subreddits: list[str]
    ) -> dict[str, Any]:
        """Execute the complete workflow with performance tracking."""
        print(f"🎯 Executing workflow for topics: {topics}")
        print(f"🏠 Target subreddits: {subreddits}")

        start_time = time.time()

        try:
            # Execute monitoring cycle through coordinator
            result = await self.coordinator.execute_skill(
                "run_monitoring_cycle", {"topics": topics, "subreddits": subreddits}
            )

            total_time = time.time() - start_time

            # Store performance metrics
            self.test_results["execution_time"]["total_workflow"] = total_time
            self.test_results["execution_time"]["workflow_start"] = start_time

            if result.get("status") == "success":
                print(f"✅ Workflow completed successfully in {total_time:.2f}s")

                workflow_data = result["result"]
                workflow_id = workflow_data.get("workflow_id")

                # Extract stage metrics
                stages = ["retrieval", "filter", "summarise", "alert"]
                for stage in stages:
                    stage_key = f"{stage}_result"
                    if stage_key in workflow_data:
                        stage_data = workflow_data[stage_key]
                        print(
                            f"  📊 {stage.title()}: {self._extract_stage_metrics(stage_data)}"
                        )

                self.test_results["workflow_validation"]["workflow_id"] = workflow_id
                self.test_results["workflow_validation"]["stages_completed"] = len(
                    [s for s in stages if f"{s}_result" in workflow_data]
                )

                return result
            else:
                error_msg = result.get("error", "Unknown error")
                print(f"❌ Workflow failed: {error_msg}")
                raise RuntimeError(f"Workflow execution failed: {error_msg}")

        except Exception as e:
            self.logger.error(f"Workflow execution failed: {e}", exc_info=True)
            raise

    def _extract_stage_metrics(self, stage_data: dict[str, Any]) -> str:
        """Extract and format stage metrics for display."""
        if not isinstance(stage_data, dict):
            return str(stage_data)

        # Common metrics to display
        metrics = []

        # Post counts
        if "total_posts" in stage_data:
            metrics.append(f"{stage_data['total_posts']} posts")
        if "relevant_posts" in stage_data:
            metrics.append(f"{stage_data['relevant_posts']} relevant")
        if "summaries_created" in stage_data:
            metrics.append(f"{stage_data['summaries_created']} summaries")
        if "alerts_sent" in stage_data:
            metrics.append(f"{stage_data['alerts_sent']} alerts")

        # Timing
        if "execution_time" in stage_data:
            metrics.append(f"{stage_data['execution_time']:.2f}s")

        return ", ".join(metrics) if metrics else "completed"

    async def _validate_data_persistence(self, workflow_result: dict[str, Any]) -> None:
        """Validate that data is properly persisted at each stage."""
        print("🔍 Validating data persistence...")

        if workflow_result.get("status") != "success":
            print("⚠️ Skipping data persistence validation (workflow failed)")
            return

        workflow_id = workflow_result["result"].get("workflow_id")
        if not workflow_id:
            print("⚠️ No workflow ID found")
            return

        try:
            with get_db_session() as session:
                # Check workflow execution record
                workflow = (
                    session.query(WorkflowExecution).filter_by(id=workflow_id).first()
                )
                if workflow:
                    print(f"✅ Workflow record persisted: ID {workflow_id}")
                    self.test_results["data_flow"]["workflow_persisted"] = True
                else:
                    print(f"❌ Workflow record not found: ID {workflow_id}")
                    self.test_results["data_flow"]["workflow_persisted"] = False

                # Check Reddit posts
                posts = (
                    session.query(RedditPost).filter_by(workflow_id=workflow_id).all()
                )
                print(f"✅ Reddit posts persisted: {len(posts)} posts")
                self.test_results["data_flow"]["posts_persisted"] = len(posts)

                # Check content filters
                filters = (
                    session.query(ContentFilter)
                    .filter_by(workflow_id=workflow_id)
                    .all()
                )
                print(f"✅ Content filters persisted: {len(filters)} filters")
                self.test_results["data_flow"]["filters_persisted"] = len(filters)

                # Check summaries
                summaries = (
                    session.query(ContentSummary)
                    .filter_by(workflow_id=workflow_id)
                    .all()
                )
                print(f"✅ Content summaries persisted: {len(summaries)} summaries")
                self.test_results["data_flow"]["summaries_persisted"] = len(summaries)

        except Exception as e:
            self.logger.error(f"Data persistence validation failed: {e}")
            self.test_results["data_flow"]["validation_error"] = str(e)

    async def _analyze_performance_metrics(
        self, workflow_result: dict[str, Any]
    ) -> None:
        """Analyze performance metrics and identify bottlenecks."""
        print("📊 Analyzing performance metrics...")

        total_time = self.test_results["execution_time"].get("total_workflow", 0)

        # Performance targets
        performance_targets = {
            "total_workflow": 300,  # 5 minutes max
            "retrieval_stage": 60,  # 1 minute max
            "filter_stage": 30,  # 30 seconds max
            "summarise_stage": 120,  # 2 minutes max
            "alert_stage": 30,  # 30 seconds max
        }

        print(f"📈 Total workflow time: {total_time:.2f}s")

        # Analyze against targets
        if total_time > performance_targets["total_workflow"]:
            print("⚠️ Performance warning: Workflow exceeded target time")
            self.test_results["performance_metrics"]["performance_warning"] = True
        else:
            print(
                f"✅ Performance: Within target ({performance_targets['total_workflow']}s)"
            )
            self.test_results["performance_metrics"]["performance_warning"] = False

        # Store detailed metrics
        self.test_results["performance_metrics"]["total_time"] = total_time
        self.test_results["performance_metrics"]["targets"] = performance_targets

        # Estimate throughput
        if workflow_result.get("status") == "success":
            result_data = workflow_result["result"]
            posts_processed = 0

            # Count posts from retrieval
            if "retrieval_result" in result_data:
                posts_processed = result_data["retrieval_result"].get("total_posts", 0)

            if posts_processed > 0 and total_time > 0:
                throughput = posts_processed / total_time
                print(f"📊 Throughput: {throughput:.2f} posts/second")
                self.test_results["performance_metrics"]["throughput"] = throughput

    async def _test_error_handling(self) -> None:
        """Test error handling and graceful degradation."""
        print("🛡️ Testing error handling...")

        # Test 1: Invalid topic
        try:
            print("🧪 Testing invalid topic handling...")
            result = await self.coordinator.execute_skill(
                "run_monitoring_cycle",
                {"topics": ["nonexistent_topic_12345"], "subreddits": ["test"]},
            )

            if result.get("status") == "success":
                print("✅ Invalid topic handled gracefully")
                self.test_results["error_handling"]["invalid_topic"] = "handled"
            else:
                print(f"⚠️ Invalid topic result: {result.get('error', 'unknown')}")
                self.test_results["error_handling"]["invalid_topic"] = "error"

        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            self.test_results["error_handling"]["invalid_topic"] = "exception"

        # Test 2: Network resilience (simulate by using very short timeout)
        print("🧪 Testing network resilience...")
        # This would require modifying the coordinator for test injection
        self.test_results["error_handling"]["network_resilience"] = "not_tested"

        # Test 3: Agent health check
        try:
            health_result = await self.coordinator.execute_skill(
                "check_agent_status", {}
            )
            if health_result.get("status") == "success":
                print("✅ Agent health monitoring functional")
                self.test_results["error_handling"]["health_monitoring"] = "functional"
            else:
                print("⚠️ Agent health monitoring issues")
                self.test_results["error_handling"]["health_monitoring"] = "issues"
        except Exception as e:
            print(f"❌ Health monitoring test failed: {e}")
            self.test_results["error_handling"]["health_monitoring"] = "failed"

    async def _generate_integration_report(
        self, workflow_result: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate comprehensive integration test report."""
        print("📋 Generating integration report...")

        report = {
            "test_metadata": {
                "test_type": "complete_workflow_integration",
                "timestamp": datetime.now(UTC).isoformat(),
                "duration": self.test_results["execution_time"].get(
                    "total_workflow", 0
                ),
                "test_framework": "WorkflowIntegrationTester v1.0",
            },
            "workflow_execution": {
                "status": workflow_result.get("status", "unknown"),
                "workflow_id": self.test_results["workflow_validation"].get(
                    "workflow_id"
                ),
                "stages_completed": self.test_results["workflow_validation"].get(
                    "stages_completed", 0
                ),
                "total_stages": 4,
            },
            "data_flow_validation": self.test_results["data_flow"],
            "performance_metrics": self.test_results["performance_metrics"],
            "error_handling": self.test_results["error_handling"],
            "recommendations": self._generate_recommendations(),
            "raw_results": workflow_result,
        }

        # Calculate overall test score
        report["test_score"] = self._calculate_test_score(report)

        return report

    def _generate_recommendations(self) -> list[str]:
        """Generate recommendations based on test results."""
        recommendations = []

        # Performance recommendations
        if self.test_results["performance_metrics"].get("performance_warning"):
            recommendations.append(
                "Consider optimizing workflow performance - exceeded target time"
            )

        # Data flow recommendations
        if not self.test_results["data_flow"].get("workflow_persisted"):
            recommendations.append(
                "Fix workflow persistence - data not being stored correctly"
            )

        # Error handling recommendations
        if self.test_results["error_handling"].get("health_monitoring") != "functional":
            recommendations.append("Improve agent health monitoring implementation")

        if not recommendations:
            recommendations.append("All tests passed - system is performing well")

        return recommendations

    def _calculate_test_score(self, report: dict[str, Any]) -> float:
        """Calculate overall test score (0-100)."""
        score = 0.0
        max_score = 100.0

        # Workflow execution (40 points)
        if report["workflow_execution"]["status"] == "success":
            score += 40

        # Data persistence (20 points)
        if report["data_flow_validation"].get("workflow_persisted"):
            score += 10
        if report["data_flow_validation"].get("posts_persisted", 0) > 0:
            score += 5
        if report["data_flow_validation"].get("filters_persisted", 0) > 0:
            score += 3
        if report["data_flow_validation"].get("summaries_persisted", 0) > 0:
            score += 2

        # Performance (20 points)
        if not report["performance_metrics"].get("performance_warning", True):
            score += 20

        # Error handling (20 points)
        if report["error_handling"].get("health_monitoring") == "functional":
            score += 10
        if report["error_handling"].get("invalid_topic") == "handled":
            score += 10

        return min(score, max_score)

    async def _cleanup_resources(self) -> None:
        """Cleanup resources after testing."""
        try:
            if hasattr(self.coordinator, "_cleanup_http_session"):
                await self.coordinator._cleanup_http_session()
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")


async def main():
    """Run the complete workflow integration test."""
    tester = WorkflowIntegrationTester()

    try:
        print("🚀 REDDIT TECHNICAL WATCHER - COMPLETE WORKFLOW INTEGRATION TEST")
        print("=" * 80)

        # Execute complete test suite
        report = await tester.test_complete_workflow_pipeline()

        # Display results
        print("\n" + "=" * 80)
        print("📊 FINAL INTEGRATION TEST REPORT")
        print("=" * 80)

        print(f"Overall Test Score: {report.get('test_score', 0):.1f}/100")
        print(
            f"Workflow Status: {report.get('workflow_execution', {}).get('status', 'unknown')}"
        )

        if report.get("workflow_execution", {}).get("workflow_id"):
            print(f"Workflow ID: {report['workflow_execution']['workflow_id']}")

        # Performance summary
        perf = report.get("performance_metrics", {})
        if "total_time" in perf:
            print(f"Total Execution Time: {perf['total_time']:.2f}s")

        if "throughput" in perf:
            print(f"Processing Throughput: {perf['throughput']:.2f} posts/second")

        # Data flow summary
        data_flow = report.get("data_flow_validation", {})
        print(f"Posts Processed: {data_flow.get('posts_persisted', 0)}")
        print(f"Filters Applied: {data_flow.get('filters_persisted', 0)}")
        print(f"Summaries Created: {data_flow.get('summaries_persisted', 0)}")

        # Recommendations
        recommendations = report.get("recommendations", [])
        if recommendations:
            print("\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")

        # Save detailed report
        import json

        report_filename = f"workflow_integration_report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\n📄 Detailed report saved: {report_filename}")

        # Exit with appropriate code
        if report.get("test_score", 0) >= 80:
            print("\n🎉 INTEGRATION TEST PASSED!")
            return 0
        else:
            print("\n⚠️ INTEGRATION TEST NEEDS ATTENTION")
            return 1

    except Exception as e:
        print(f"\n❌ INTEGRATION TEST FAILED: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
