"""
智能旅行助手 - 天气查询Agent节点

LangGraph节点实现
"""

import time
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from app.agents.state import TripPlanningState
from app.agents.tools import query_weather
from app.core.logging import get_logger
from app.services.cache_service import get_cache_service

logger = get_logger(__name__)


async def weather_node(
    state: TripPlanningState,
    config: RunnableConfig
) -> Dict[str, Any]:
    """天气查询节点

    查询目的地城市的天气预报

    Args:
        state: 当前状态
        config: 运行配置

    Returns:
        更新后的状态字段
    """
    start_time = time.time()
    request = state["request"]
    trace_id = state.get("trace_id", "unknown")

    logger.info(
        "weather_node_started",
        city=request.city,
        trace_id=trace_id
    )

    try:
        # 检查缓存
        cache = get_cache_service()
        cache_key = f"weather:{request.city}"
        cached = await cache.get(cache_key)

        if cached:
            logger.info("weather_cache_hit", cache_key=cache_key, trace_id=trace_id)
            execution_time_ms = int((time.time() - start_time) * 1000)
            return {
                "weather": cached,
                "node_status": {**state.get("node_status", {}), "query_weather": "completed"},
                "node_timings": {**state.get("node_timings", {}), "query_weather": execution_time_ms}
            }

        # 调用工具查询天气
        result_str = await query_weather.ainvoke({
            "city": request.city
        })

        # 解析结果
        import json
        result = json.loads(result_str)

        # 转换为WeatherInfo对象
        from app.models.schemas import WeatherInfo
        weather_list = []
        for day in result.get("forecast", []):
            weather_list.append(WeatherInfo(
                date=day.get("date", ""),
                day_weather=day.get("day_weather", ""),
                night_weather=day.get("night_weather", ""),
                day_temp=day.get("day_temp", 0),
                night_temp=day.get("night_temp", 0),
                wind_direction=day.get("wind_direction", ""),
                wind_power=day.get("wind_power", "")
            ))

        # 存入缓存
        await cache.set(cache_key, weather_list, ttl=1800)  # 30分钟

        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "weather_node_completed",
            city=request.city,
            days=len(weather_list),
            execution_time_ms=execution_time_ms,
            trace_id=trace_id
        )

        return {
            "weather": weather_list,
            "node_status": {**state.get("node_status", {}), "query_weather": "completed"},
            "node_timings": {**state.get("node_timings", {}), "query_weather": execution_time_ms}
        }

    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.error(
            "weather_node_failed",
            error=str(e),
            city=request.city,
            execution_time_ms=execution_time_ms,
            trace_id=trace_id
        )

        # 天气查询失败不阻断流程，返回空列表
        return {
            "weather": [],
            "node_status": {**state.get("node_status", {}), "query_weather": "failed"},
            "node_errors": {**state.get("node_errors", {}), "query_weather": str(e)},
            "node_timings": {**state.get("node_timings", {}), "query_weather": execution_time_ms}
        }
