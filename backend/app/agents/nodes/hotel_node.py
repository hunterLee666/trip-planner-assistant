"""
智能旅行助手 - 酒店搜索Agent节点

LangGraph节点实现
"""

import time
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from app.agents.state import TripPlanningState
from app.agents.tools import search_hotels
from app.core.logging import get_logger
from app.services.cache_service import get_cache_service

logger = get_logger(__name__)


async def hotel_node(
    state: TripPlanningState,
    config: RunnableConfig
) -> Dict[str, Any]:
    """酒店搜索节点

    根据城市和住宿偏好搜索酒店

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
        "hotel_node_started",
        city=request.city,
        accommodation=request.accommodation,
        trace_id=trace_id
    )

    try:
        # 检查缓存
        cache = get_cache_service()
        cache_key = f"hotels:{request.city}:{request.accommodation}"
        cached = await cache.get(cache_key)

        if cached:
            logger.info("hotel_cache_hit", cache_key=cache_key, trace_id=trace_id)
            execution_time_ms = int((time.time() - start_time) * 1000)
            return {
                "hotels": cached,
                "node_status": {**state.get("node_status", {}), "search_hotels": "completed"},
                "node_timings": {**state.get("node_timings", {}), "search_hotels": execution_time_ms}
            }

        # 调用工具搜索酒店
        result_str = await search_hotels.ainvoke({
            "city": request.city,
            "keywords": request.accommodation or "酒店"
        })

        # 解析结果
        import json
        result = json.loads(result_str)

        # 转换为Hotel对象
        from app.models.schemas import Hotel, Location
        hotels = []
        for h in result.get("hotels", []):
            location = h.get("location", {})
            hotels.append(Hotel(
                name=h.get("name", ""),
                address=h.get("address", ""),
                location=Location(
                    longitude=location.get("longitude", 0),
                    latitude=location.get("latitude", 0)
                ),
                type=h.get("type", "酒店"),
                price_range="",
                rating="",
                distance="",
            ))

        # 存入缓存
        await cache.set(cache_key, hotels, ttl=7200)  # 2小时

        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "hotel_node_completed",
            city=request.city,
            count=len(hotels),
            execution_time_ms=execution_time_ms,
            trace_id=trace_id
        )

        return {
            "hotels": hotels,
            "node_status": {**state.get("node_status", {}), "search_hotels": "completed"},
            "node_timings": {**state.get("node_timings", {}), "search_hotels": execution_time_ms}
        }

    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.error(
            "hotel_node_failed",
            error=str(e),
            city=request.city,
            execution_time_ms=execution_time_ms,
            trace_id=trace_id
        )

        # 酒店搜索失败不阻断流程，返回空列表
        return {
            "hotels": [],
            "node_status": {**state.get("node_status", {}), "search_hotels": "failed"},
            "node_errors": {**state.get("node_errors", {}), "search_hotels": str(e)},
            "node_timings": {**state.get("node_timings", {}), "search_hotels": execution_time_ms}
        }
