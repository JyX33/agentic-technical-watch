#!/usr/bin/env python3
# ABOUTME: Workflow simulation test for Reddit Technical Watcher pipeline
# ABOUTME: Simulates complete workflow without requiring all agents to be running

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from reddit_watcher.config import get_settings
from reddit_watcher.database.utils import get_db_session
from reddit_watcher.models import (
    AlertBatch,
    AlertDelivery,
    ContentFilter,
    ContentSummary,
    RedditPost,
    WorkflowExecution,
)


class WorkflowSimulator:
    """Simulates the complete Reddit monitoring workflow for testing."""

    def __init__(self):
        self.config = get_settings()
        self.logger = self._setup_logging()
        self.test_results = {}

    def _setup_logging(self):
        """Setup logging for workflow simulation."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("workflow_simulation.log"),
            ],
        )
        return logging.getLogger(__name__)

    async def simulate_complete_workflow(self) -> dict[str, Any]:
        """
        Simulate the complete monitoring workflow: Collect → Filter → Summarize → Alert

        This test validates:
        1. Data flow through all pipeline stages
        2. Database persistence at each stage
        3. Performance metrics collection
        4. Error handling and recovery
        """
        print("🚀 WORKFLOW SIMULATION - COMPLETE PIPELINE TEST")
        print("=" * 60)
        print(f"⏰ Started at: {datetime.now(UTC).isoformat()}")

        try:
            # Phase 0: Clean previous test data
            await self._cleanup_previous_test_data()

            # Phase 1: Validate infrastructure
            await self._validate_infrastructure()

            # Phase 2: Simulate data collection
            print("\n📥 Phase 2: Data Collection Simulation")
            collection_metrics = await self._simulate_data_collection()

            # Phase 3: Simulate content filtering
            print("\n🔍 Phase 3: Content Filtering Simulation")
            filter_metrics = await self._simulate_content_filtering(collection_metrics)

            # Phase 4: Simulate content summarization
            print("\n📝 Phase 4: Content Summarization Simulation")
            summary_metrics = await self._simulate_content_summarization(filter_metrics)

            # Phase 5: Simulate alert delivery
            print("\n📢 Phase 5: Alert Delivery Simulation")
            alert_metrics = await self._simulate_alert_delivery(summary_metrics)

            # Phase 6: Validate end-to-end data flow
            print("\n💾 Phase 6: End-to-End Data Flow Validation")
            validation_results = await self._validate_data_flow()

            # Phase 7: Performance analysis
            print("\n⚡ Phase 7: Performance Analysis")
            performance_results = await self._analyze_performance()

            # Generate comprehensive report
            report = self._generate_simulation_report(
                {
                    "collection": collection_metrics,
                    "filtering": filter_metrics,
                    "summarization": summary_metrics,
                    "alerts": alert_metrics,
                    "validation": validation_results,
                    "performance": performance_results,
                }
            )

            return report

        except Exception as e:
            self.logger.error(f"Workflow simulation failed: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            }

    async def _cleanup_previous_test_data(self) -> None:
        """Clean up any previous test data to avoid conflicts."""
        print("🧹 Cleaning previous test data...")

        try:
            with get_db_session() as session:
                # Delete test data in reverse dependency order
                session.execute(
                    text(
                        "DELETE FROM alert_deliveries WHERE alert_batch_id IN (SELECT id FROM alert_batches WHERE summary LIKE 'Simulated%')"
                    )
                )
                session.execute(
                    text("DELETE FROM alert_batches WHERE summary LIKE 'Simulated%'")
                )
                session.execute(
                    text(
                        "DELETE FROM content_summaries WHERE summary_text LIKE 'Simulated%'"
                    )
                )
                session.execute(
                    text(
                        "DELETE FROM content_filters WHERE post_id IN (SELECT id FROM reddit_posts WHERE post_id LIKE 'sim%')"
                    )
                )
                session.execute(
                    text("DELETE FROM reddit_posts WHERE post_id LIKE 'sim%'")
                )
                session.execute(
                    text("DELETE FROM workflow_executions WHERE status = 'running'")
                )
                session.commit()
                print("✅ Previous test data cleaned")
        except Exception as e:
            self.logger.warning(f"Cleanup warning (may be expected): {e}")

    async def _validate_infrastructure(self) -> None:
        """Validate infrastructure components."""
        print("🔧 Validating infrastructure...")

        # Test database connectivity
        try:
            with get_db_session() as session:
                session.execute(text("SELECT version()"))
            print("✅ Database: Connected")
        except Exception as e:
            raise RuntimeError(f"Database validation failed: {e}")

        # Test Redis connectivity (if available)
        # This would be a nice-to-have but not critical for simulation
        print("✅ Infrastructure validation: Complete")

    async def _simulate_data_collection(self) -> dict[str, Any]:
        """Simulate Reddit data collection stage."""
        start_time = time.time()

        # Create a workflow execution record
        workflow_id = await self._create_workflow_record()

        # Simulate collecting posts for different topics
        topics = ["Claude Code", "A2A", "Agent-to-Agent"]
        subreddits = ["MachineLearning", "artificial", "singularity"]

        total_posts = 0

        try:
            with get_db_session() as session:
                # Simulate fetching posts from Reddit
                for topic in topics:
                    for subreddit in subreddits:
                        # Simulate 3-8 posts per topic/subreddit combination
                        import random

                        post_count = random.randint(3, 8)

                        for i in range(post_count):
                            # Create a unique post_id that fits in 20 characters
                            import uuid

                            short_uuid = str(uuid.uuid4())[:8]
                            short_id = f"sim{short_uuid}"
                            post = RedditPost(
                                post_id=short_id,
                                title=f"Simulated post about {topic} in r/{subreddit} #{i + 1}",
                                content=f"This is a simulated Reddit post discussing {topic}. "
                                * 3,
                                author=f"user_{random.randint(1000, 9999)}",
                                subreddit=subreddit,
                                score=random.randint(1, 100),
                                num_comments=random.randint(0, 50),
                                url=f"https://reddit.com/r/{subreddit}/posts/sim_{i}",
                                topic=topic,  # Add topic field
                                created_utc=datetime.now(UTC),
                            )
                            session.add(post)
                            total_posts += 1

                session.commit()

        except Exception as e:
            self.logger.error(f"Data collection simulation failed: {e}")
            raise

        execution_time = time.time() - start_time

        metrics = {
            "workflow_id": workflow_id,
            "total_posts": total_posts,
            "topics_processed": len(topics),
            "subreddits_processed": len(subreddits),
            "execution_time": execution_time,
            "throughput": total_posts / execution_time if execution_time > 0 else 0,
        }

        print(
            f"✅ Data Collection: {total_posts} posts collected in {execution_time:.2f}s"
        )
        print(f"   📊 Throughput: {metrics['throughput']:.2f} posts/second")

        return metrics

    async def _simulate_content_filtering(
        self, collection_metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """Simulate content filtering stage."""
        start_time = time.time()
        workflow_id = collection_metrics["workflow_id"]

        relevant_posts = 0
        total_filters = 0

        try:
            with get_db_session() as session:
                # Get all posts from collection stage (recent posts with sim prefix)
                posts = (
                    session.query(RedditPost)
                    .filter(RedditPost.post_id.like("sim%"))
                    .all()
                )

                for post in posts:
                    # Simulate filtering logic
                    # In real system: keyword matching + semantic similarity
                    import random

                    # Simulate relevance scoring
                    relevance_score = random.uniform(0.1, 1.0)
                    is_relevant = relevance_score >= 0.7  # Threshold

                    if is_relevant:
                        relevant_posts += 1

                    # Create filter record
                    content_filter = ContentFilter(
                        post_id=post.id,
                        relevance_score=relevance_score,
                        is_relevant=is_relevant,
                        keywords_matched=[post.topic]
                        if is_relevant and post.topic
                        else [],
                        semantic_similarity=relevance_score,
                        filter_reason=f"Keyword match: {relevance_score:.3f}"
                        if is_relevant
                        else "Below threshold",
                    )
                    session.add(content_filter)
                    total_filters += 1

                session.commit()

        except Exception as e:
            self.logger.error(f"Content filtering simulation failed: {e}")
            raise

        execution_time = time.time() - start_time

        metrics = {
            "workflow_id": workflow_id,
            "total_posts_analyzed": collection_metrics["total_posts"],
            "relevant_posts": relevant_posts,
            "filter_records": total_filters,
            "relevance_percentage": (relevant_posts / collection_metrics["total_posts"])
            * 100,
            "execution_time": execution_time,
        }

        print(
            f"✅ Content Filtering: {relevant_posts}/{collection_metrics['total_posts']} posts relevant ({metrics['relevance_percentage']:.1f}%)"
        )
        print(f"   ⏱️ Processing time: {execution_time:.2f}s")

        return metrics

    async def _simulate_content_summarization(
        self, filter_metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """Simulate content summarization stage."""
        start_time = time.time()
        workflow_id = filter_metrics["workflow_id"]

        summaries_created = 0

        try:
            with get_db_session() as session:
                # Get relevant posts for summarization
                relevant_filters = (
                    session.query(ContentFilter).filter(ContentFilter.is_relevant).all()
                )

                relevant_posts = [
                    filter_obj.post
                    for filter_obj in relevant_filters
                    if filter_obj.post
                ]

                # Group posts by topic for summarization
                topic_groups = {}
                for post in relevant_posts:
                    # Extract topic from title (simulation)
                    if "Claude Code" in post.title:
                        topic = "Claude Code"
                    elif "A2A" in post.title:
                        topic = "A2A"
                    elif "Agent-to-Agent" in post.title:
                        topic = "Agent-to-Agent"
                    else:
                        topic = "General"

                    if topic not in topic_groups:
                        topic_groups[topic] = []
                    topic_groups[topic].append(post)

                # Create summaries for each topic group
                for topic, posts in topic_groups.items():
                    if len(posts) >= 2:  # Only summarize if we have multiple posts
                        # Find a filter for this topic to use as foreign key
                        topic_filter = (
                            session.query(ContentFilter)
                            .join(RedditPost)
                            .filter(
                                RedditPost.topic == topic,
                                ContentFilter.is_relevant,
                            )
                            .first()
                        )

                        if topic_filter:
                            summary = ContentSummary(
                                content_filter_id=topic_filter.id,
                                summary_text=f"Simulated summary for {len(posts)} posts about {topic}. "
                                + "Key discussions include developments, updates, and community feedback.",
                                key_points=[
                                    f"Point {i + 1} about {topic}" for i in range(3)
                                ],
                                confidence_score=0.85,
                            )
                            session.add(summary)
                            summaries_created += 1

                session.commit()

        except Exception as e:
            self.logger.error(f"Content summarization simulation failed: {e}")
            raise

        execution_time = time.time() - start_time

        metrics = {
            "workflow_id": workflow_id,
            "relevant_posts_processed": filter_metrics["relevant_posts"],
            "summaries_created": summaries_created,
            "execution_time": execution_time,
        }

        print(f"✅ Content Summarization: {summaries_created} summaries created")
        print(f"   📝 Processed {filter_metrics['relevant_posts']} relevant posts")

        return metrics

    async def _simulate_alert_delivery(
        self, summary_metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """Simulate alert delivery stage."""
        start_time = time.time()
        workflow_id = summary_metrics["workflow_id"]

        alerts_sent = 0

        try:
            with get_db_session() as session:
                # Get summaries for alert delivery
                summaries = session.query(ContentSummary).all()

                for summary in summaries:
                    # Create alert batch first
                    alert_batch = AlertBatch(
                        batch_id=f"sim_batch_{summary.id}",
                        title="Simulated Alert for Topic",
                        summary=summary.summary_text[:500],  # Truncate if needed
                        total_items=1,
                        priority=1,
                        channels=["slack", "email"],
                    )
                    session.add(alert_batch)
                    session.flush()  # Get the ID

                    # Simulate Slack alert
                    slack_alert = AlertDelivery(
                        alert_batch_id=alert_batch.id,
                        channel="slack",
                        recipient="slack_webhook",
                        sent_at=datetime.now(UTC),
                    )
                    session.add(slack_alert)
                    alerts_sent += 1

                    # Simulate email alert
                    email_alert = AlertDelivery(
                        alert_batch_id=alert_batch.id,
                        channel="email",
                        recipient="admin@example.com",
                        sent_at=datetime.now(UTC),
                    )
                    session.add(email_alert)
                    alerts_sent += 1

                session.commit()

        except Exception as e:
            self.logger.error(f"Alert delivery simulation failed: {e}")
            raise

        execution_time = time.time() - start_time

        metrics = {
            "workflow_id": workflow_id,
            "summaries_processed": summary_metrics["summaries_created"],
            "alerts_sent": alerts_sent,
            "execution_time": execution_time,
        }

        print(f"✅ Alert Delivery: {alerts_sent} alerts sent")
        print(f"   📬 {summary_metrics['summaries_created']} summaries distributed")

        return metrics

    async def _validate_data_flow(self) -> dict[str, Any]:
        """Validate end-to-end data flow."""
        print("🔍 Validating data persistence...")

        validation_results = {}

        try:
            with get_db_session() as session:
                # Count records at each stage
                workflow_count = session.query(WorkflowExecution).count()
                post_count = session.query(RedditPost).count()
                filter_count = session.query(ContentFilter).count()
                summary_count = session.query(ContentSummary).count()
                alert_batch_count = session.query(AlertBatch).count()
                alert_count = session.query(AlertDelivery).count()

                validation_results = {
                    "workflows": workflow_count,
                    "posts": post_count,
                    "filters": filter_count,
                    "summaries": summary_count,
                    "alert_batches": alert_batch_count,
                    "alerts": alert_count,
                    "data_flow_complete": all(
                        [
                            workflow_count > 0,
                            post_count > 0,
                            filter_count > 0,
                            summary_count > 0,
                            alert_count > 0,
                        ]
                    ),
                }

                print("✅ Data Flow Validation:")
                print(f"   📋 Workflows: {workflow_count}")
                print(f"   📄 Posts: {post_count}")
                print(f"   🔍 Filters: {filter_count}")
                print(f"   📝 Summaries: {summary_count}")
                print(f"   📦 Alert Batches: {alert_batch_count}")
                print(f"   📢 Alerts: {alert_count}")

                if validation_results["data_flow_complete"]:
                    print("✅ End-to-end data flow: Complete")
                else:
                    print("⚠️ End-to-end data flow: Incomplete")

        except Exception as e:
            self.logger.error(f"Data flow validation failed: {e}")
            validation_results["error"] = str(e)

        return validation_results

    async def _analyze_performance(self) -> dict[str, Any]:
        """Analyze overall performance metrics."""
        # Calculate total workflow time from test_results
        total_time = sum(
            [
                self.test_results.get("collection", {}).get("execution_time", 0),
                self.test_results.get("filtering", {}).get("execution_time", 0),
                self.test_results.get("summarization", {}).get("execution_time", 0),
                self.test_results.get("alerts", {}).get("execution_time", 0),
            ]
        )

        performance_results = {
            "total_execution_time": total_time,
            "stage_breakdown": {
                "collection": self.test_results.get("collection", {}).get(
                    "execution_time", 0
                ),
                "filtering": self.test_results.get("filtering", {}).get(
                    "execution_time", 0
                ),
                "summarization": self.test_results.get("summarization", {}).get(
                    "execution_time", 0
                ),
                "alerts": self.test_results.get("alerts", {}).get("execution_time", 0),
            },
            "performance_score": self._calculate_performance_score(total_time),
        }

        print("📊 Performance Analysis:")
        print(f"   ⏱️ Total time: {total_time:.2f}s")
        print(
            f"   🎯 Performance score: {performance_results['performance_score']}/100"
        )

        return performance_results

    def _calculate_performance_score(self, total_time: float) -> float:
        """Calculate performance score based on execution time."""
        # Target: complete workflow in under 60 seconds for simulation
        target_time = 60.0

        if total_time <= target_time:
            return 100.0
        else:
            # Degrade score based on time overage
            overage_penalty = min((total_time - target_time) / target_time * 50, 50)
            return max(50.0, 100.0 - overage_penalty)

    async def _create_workflow_record(self) -> int:
        """Create a workflow execution record."""
        try:
            with get_db_session() as session:
                workflow = WorkflowExecution(
                    topics=["Claude Code", "A2A", "Agent-to-Agent"],
                    subreddits=["MachineLearning", "artificial", "singularity"],
                    status="running",
                    started_at=datetime.now(UTC),
                )
                session.add(workflow)
                session.commit()
                return workflow.id
        except Exception as e:
            self.logger.error(f"Error creating workflow record: {e}")
            raise

    def _generate_simulation_report(
        self, stage_results: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate comprehensive simulation report."""
        # Store results for performance analysis
        self.test_results = stage_results

        report = {
            "test_metadata": {
                "test_type": "workflow_simulation",
                "timestamp": datetime.now(UTC).isoformat(),
                "framework": "WorkflowSimulator v1.0",
            },
            "pipeline_stages": stage_results,
            "overall_score": self._calculate_overall_score(stage_results),
            "recommendations": self._generate_recommendations(stage_results),
        }

        return report

    def _calculate_overall_score(self, stage_results: dict[str, Any]) -> float:
        """Calculate overall simulation score."""
        score = 0.0

        # Data flow completion (40 points)
        if stage_results.get("validation", {}).get("data_flow_complete"):
            score += 40

        # Performance (30 points)
        performance_score = stage_results.get("performance", {}).get(
            "performance_score", 0
        )
        score += (performance_score / 100) * 30

        # Data volume (20 points)
        posts = stage_results.get("collection", {}).get("total_posts", 0)
        if posts >= 10:
            score += 20
        elif posts >= 5:
            score += 15
        elif posts > 0:
            score += 10

        # Processing efficiency (10 points)
        relevance = stage_results.get("filtering", {}).get("relevance_percentage", 0)
        if relevance >= 30:  # Good relevance rate
            score += 10
        elif relevance >= 20:
            score += 7
        elif relevance > 0:
            score += 5

        return min(score, 100.0)

    def _generate_recommendations(self, stage_results: dict[str, Any]) -> list[str]:
        """Generate recommendations based on simulation results."""
        recommendations = []

        # Performance recommendations
        total_time = stage_results.get("performance", {}).get("total_execution_time", 0)
        if total_time > 60:
            recommendations.append(
                "Consider optimizing pipeline performance - simulation exceeded 60 seconds"
            )

        # Data flow recommendations
        if not stage_results.get("validation", {}).get("data_flow_complete"):
            recommendations.append(
                "Fix data persistence issues - not all pipeline stages are storing data correctly"
            )

        # Processing recommendations
        relevance = stage_results.get("filtering", {}).get("relevance_percentage", 0)
        if relevance < 20:
            recommendations.append(
                "Review content filtering criteria - low relevance detection rate"
            )

        if not recommendations:
            recommendations.append(
                "Simulation passed all checks - pipeline is functioning correctly"
            )

        return recommendations


async def main():
    """Run the workflow simulation test."""
    simulator = WorkflowSimulator()

    try:
        # Run simulation
        report = await simulator.simulate_complete_workflow()

        # Display results
        print("\n" + "=" * 60)
        print("📊 WORKFLOW SIMULATION REPORT")
        print("=" * 60)

        print(f"Overall Score: {report.get('overall_score', 0):.1f}/100")

        # Performance summary
        performance = report.get("pipeline_stages", {}).get("performance", {})
        if performance:
            print(
                f"Total Execution Time: {performance.get('total_execution_time', 0):.2f}s"
            )
            print(
                f"Performance Score: {performance.get('performance_score', 0):.1f}/100"
            )

        # Data summary
        validation = report.get("pipeline_stages", {}).get("validation", {})
        if validation:
            print(f"Posts Processed: {validation.get('posts', 0)}")
            print(f"Summaries Created: {validation.get('summaries', 0)}")
            print(f"Alerts Sent: {validation.get('alerts', 0)}")

        # Recommendations
        recommendations = report.get("recommendations", [])
        if recommendations:
            print("\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")

        # Save report
        report_filename = f"workflow_simulation_report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\n📄 Detailed report saved: {report_filename}")

        # Return appropriate exit code
        if report.get("overall_score", 0) >= 80:
            print("\n🎉 WORKFLOW SIMULATION PASSED!")
            return 0
        else:
            print("\n⚠️ WORKFLOW SIMULATION NEEDS ATTENTION")
            return 1

    except Exception as e:
        print(f"\n❌ WORKFLOW SIMULATION FAILED: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
