# ABOUTME: Performance monitoring decorators for automatic metrics collection
# ABOUTME: Provides decorators for timing functions, monitoring agent skills, and resource tracking

import asyncio
import functools
import logging
import time
from collections.abc import Callable

from .resource_monitor import get_resource_monitor

logger = logging.getLogger(__name__)


def performance_monitor(
    operation_name: str | None = None,
    include_args: bool = False,
    include_result: bool = False,
):
    """
    Decorator to automatically monitor function performance.

    Args:
        operation_name: Custom name for the operation (defaults to function name)
        include_args: Whether to include function arguments in metadata
        include_result: Whether to include function result in metadata
    """

    def decorator(func: Callable) -> Callable:
        op_name = operation_name or f"{func.__module__}.{func.__name__}"
        monitor = get_resource_monitor()

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                metadata = {}

                if include_args:
                    metadata["args"] = str(args)
                    metadata["kwargs"] = str(kwargs)

                try:
                    result = await func(*args, **kwargs)

                    if include_result:
                        metadata["result"] = str(result)[:100]  # Truncate large results

                    end_time = time.time()
                    monitor.record_performance(
                        op_name, start_time, end_time, True, None, metadata
                    )

                    return result

                except Exception as e:
                    end_time = time.time()
                    monitor.record_performance(
                        op_name, start_time, end_time, False, str(e), metadata
                    )
                    raise

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                metadata = {}

                if include_args:
                    metadata["args"] = str(args)
                    metadata["kwargs"] = str(kwargs)

                try:
                    result = func(*args, **kwargs)

                    if include_result:
                        metadata["result"] = str(result)[:100]  # Truncate large results

                    end_time = time.time()
                    monitor.record_performance(
                        op_name, start_time, end_time, True, None, metadata
                    )

                    return result

                except Exception as e:
                    end_time = time.time()
                    monitor.record_performance(
                        op_name, start_time, end_time, False, str(e), metadata
                    )
                    raise

            return sync_wrapper

    return decorator


def agent_skill_monitor(agent_type: str | None = None):
    """
    Decorator to automatically monitor A2A agent skill performance.

    Args:
        agent_type: Type of agent (auto-detected from class if not provided)
    """

    def decorator(func: Callable) -> Callable:
        monitor = get_resource_monitor()

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(self, *args, **kwargs):
                # Auto-detect agent type from class
                detected_agent_type = agent_type or getattr(
                    self, "agent_type", "unknown"
                )
                skill_name = func.__name__

                start_time = time.time()

                # Get initial memory usage if psutil is available
                initial_memory = 0.0
                try:
                    import os

                    import psutil

                    process = psutil.Process(os.getpid())
                    initial_memory = process.memory_info().rss / (1024 * 1024)
                except ImportError:
                    pass

                try:
                    result = await func(self, *args, **kwargs)

                    end_time = time.time()
                    execution_time = end_time - start_time

                    # Calculate memory usage delta
                    final_memory = 0.0
                    try:
                        final_memory = process.memory_info().rss / (1024 * 1024)
                    except:
                        pass

                    memory_delta = max(0, final_memory - initial_memory)

                    monitor.record_agent_metrics(
                        agent_type=detected_agent_type,
                        skill_name=skill_name,
                        execution_time=execution_time,
                        success=True,
                        memory_usage_mb=memory_delta,
                        metadata={"args_count": len(args), "kwargs_count": len(kwargs)},
                    )

                    return result

                except Exception as e:
                    end_time = time.time()
                    execution_time = end_time - start_time

                    monitor.record_agent_metrics(
                        agent_type=detected_agent_type,
                        skill_name=skill_name,
                        execution_time=execution_time,
                        success=False,
                        metadata={"error": str(e), "error_type": type(e).__name__},
                    )

                    raise

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(self, *args, **kwargs):
                # Auto-detect agent type from class
                detected_agent_type = agent_type or getattr(
                    self, "agent_type", "unknown"
                )
                skill_name = func.__name__

                start_time = time.time()

                # Get initial memory usage if psutil is available
                initial_memory = 0.0
                try:
                    import os

                    import psutil

                    process = psutil.Process(os.getpid())
                    initial_memory = process.memory_info().rss / (1024 * 1024)
                except ImportError:
                    pass

                try:
                    result = func(self, *args, **kwargs)

                    end_time = time.time()
                    execution_time = end_time - start_time

                    # Calculate memory usage delta
                    final_memory = 0.0
                    try:
                        final_memory = process.memory_info().rss / (1024 * 1024)
                    except:
                        pass

                    memory_delta = max(0, final_memory - initial_memory)

                    monitor.record_agent_metrics(
                        agent_type=detected_agent_type,
                        skill_name=skill_name,
                        execution_time=execution_time,
                        success=True,
                        memory_usage_mb=memory_delta,
                        metadata={"args_count": len(args), "kwargs_count": len(kwargs)},
                    )

                    return result

                except Exception as e:
                    end_time = time.time()
                    execution_time = end_time - start_time

                    monitor.record_agent_metrics(
                        agent_type=detected_agent_type,
                        skill_name=skill_name,
                        execution_time=execution_time,
                        success=False,
                        metadata={"error": str(e), "error_type": type(e).__name__},
                    )

                    raise

            return sync_wrapper

    return decorator


def database_monitor(operation_type: str = "database"):
    """
    Decorator to monitor database operations.

    Args:
        operation_type: Type of database operation (e.g., 'query', 'insert', 'update')
    """

    def decorator(func: Callable) -> Callable:
        monitor = get_resource_monitor()

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                operation_name = f"db_{operation_type}_{func.__name__}"
                start_time = time.time()

                try:
                    result = await func(*args, **kwargs)

                    end_time = time.time()
                    monitor.record_performance(
                        operation_name,
                        start_time,
                        end_time,
                        True,
                        None,
                        {"operation_type": operation_type},
                    )

                    return result

                except Exception as e:
                    end_time = time.time()
                    monitor.record_performance(
                        operation_name,
                        start_time,
                        end_time,
                        False,
                        str(e),
                        {"operation_type": operation_type},
                    )
                    raise

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                operation_name = f"db_{operation_type}_{func.__name__}"
                start_time = time.time()

                try:
                    result = func(*args, **kwargs)

                    end_time = time.time()
                    monitor.record_performance(
                        operation_name,
                        start_time,
                        end_time,
                        True,
                        None,
                        {"operation_type": operation_type},
                    )

                    return result

                except Exception as e:
                    end_time = time.time()
                    monitor.record_performance(
                        operation_name,
                        start_time,
                        end_time,
                        False,
                        str(e),
                        {"operation_type": operation_type},
                    )
                    raise

            return sync_wrapper

    return decorator


def ml_model_monitor(model_type: str):
    """
    Decorator to monitor ML model operations.

    Args:
        model_type: Type of ML model (e.g., 'sentence_transformer', 'spacy')
    """

    def decorator(func: Callable) -> Callable:
        monitor = get_resource_monitor()

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                operation_name = f"ml_{model_type}_{func.__name__}"
                start_time = time.time()

                # Extract input size if possible
                input_size = 0
                if args and hasattr(args[0], "__len__"):
                    try:
                        input_size = len(args[0])
                    except:
                        pass

                try:
                    result = await func(*args, **kwargs)

                    end_time = time.time()
                    monitor.record_performance(
                        operation_name,
                        start_time,
                        end_time,
                        True,
                        None,
                        {
                            "model_type": model_type,
                            "input_size": input_size,
                            "throughput": input_size / (end_time - start_time)
                            if input_size > 0
                            else 0,
                        },
                    )

                    return result

                except Exception as e:
                    end_time = time.time()
                    monitor.record_performance(
                        operation_name,
                        start_time,
                        end_time,
                        False,
                        str(e),
                        {"model_type": model_type, "input_size": input_size},
                    )
                    raise

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                operation_name = f"ml_{model_type}_{func.__name__}"
                start_time = time.time()

                # Extract input size if possible
                input_size = 0
                if args and hasattr(args[0], "__len__"):
                    try:
                        input_size = len(args[0])
                    except:
                        pass

                try:
                    result = func(*args, **kwargs)

                    end_time = time.time()
                    monitor.record_performance(
                        operation_name,
                        start_time,
                        end_time,
                        True,
                        None,
                        {
                            "model_type": model_type,
                            "input_size": input_size,
                            "throughput": input_size / (end_time - start_time)
                            if input_size > 0
                            else 0,
                        },
                    )

                    return result

                except Exception as e:
                    end_time = time.time()
                    monitor.record_performance(
                        operation_name,
                        start_time,
                        end_time,
                        False,
                        str(e),
                        {"model_type": model_type, "input_size": input_size},
                    )
                    raise

            return sync_wrapper

    return decorator


def api_monitor(api_name: str, rate_limit: int | None = None):
    """
    Decorator to monitor API calls with optional rate limiting.

    Args:
        api_name: Name of the API being called
        rate_limit: Optional rate limit (requests per minute)
    """

    def decorator(func: Callable) -> Callable:
        monitor = get_resource_monitor()

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                operation_name = f"api_{api_name}_{func.__name__}"
                start_time = time.time()

                try:
                    result = await func(*args, **kwargs)

                    end_time = time.time()
                    monitor.record_performance(
                        operation_name,
                        start_time,
                        end_time,
                        True,
                        None,
                        {
                            "api_name": api_name,
                            "rate_limit": rate_limit,
                            "response_time": end_time - start_time,
                        },
                    )

                    return result

                except Exception as e:
                    end_time = time.time()
                    monitor.record_performance(
                        operation_name,
                        start_time,
                        end_time,
                        False,
                        str(e),
                        {
                            "api_name": api_name,
                            "rate_limit": rate_limit,
                            "response_time": end_time - start_time,
                        },
                    )
                    raise

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                operation_name = f"api_{api_name}_{func.__name__}"
                start_time = time.time()

                try:
                    result = func(*args, **kwargs)

                    end_time = time.time()
                    monitor.record_performance(
                        operation_name,
                        start_time,
                        end_time,
                        True,
                        None,
                        {
                            "api_name": api_name,
                            "rate_limit": rate_limit,
                            "response_time": end_time - start_time,
                        },
                    )

                    return result

                except Exception as e:
                    end_time = time.time()
                    monitor.record_performance(
                        operation_name,
                        start_time,
                        end_time,
                        False,
                        str(e),
                        {
                            "api_name": api_name,
                            "rate_limit": rate_limit,
                            "response_time": end_time - start_time,
                        },
                    )
                    raise

            return sync_wrapper

    return decorator
