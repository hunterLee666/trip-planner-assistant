"""
智能旅行助手 - 景点搜索Agent节点

LangGraph节点实现
"""

import time
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from app.agents.state import TripPlanningState, update_node_status
from app.agents.tools import search_poi
from app.core.logging import get_logger
from app.services.cache_service import get_cache_service

logger = get_logger(__name__)


async def attraction_node(
    state: TripPlanningState,
    config: RunnableConfig
) -> Dict[str, Any]:
    """景点搜索节点

    根据用户偏好搜索城市景点，支持缓存

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
        "attraction_node_started",
        city=request.city,
        preferences=request.preferences,
        trace_id=trace_id
    )

    try:
        # 检查缓存
        cache = get_cache_service()
        keywords = request.preferences[0] if request.preferences else "景点"
        cache_key = f"attractions:{request.city}:{keywords}"
        cached = await cache.get(cache_key)

        if cached:
            logger.info("attraction_cache_hit", cache_key=cache_key, trace_id=trace_id)
            execution_time_ms = int((time.time() - start_time) * 1000)
            return {
                "attractions": cached,
                "node_status": {**state.get("node_status", {}), "search_attractions": "completed"},
                "node_timings": {**state.get("node_timings", {}), "search_attractions": execution_time_ms}
            }

        # 调用工具搜索景点
        result_str = await search_poi.ainvoke({
            "keywords": keywords,
            "city": request.city,
            "citylimit": True
        })

        # 解析结果
        import json
        result = json.loads(result_str)

        # 转换为Attraction对象
        from app.models.schemas import Attraction, Location
        attractions = []
        for poi in result.get("pois", []):
            location = poi.get("location", {})
            attractions.append(Attraction(
                name=poi.get("name", ""),
                address=poi.get("address", ""),
                location=Location(
                    longitude=location.get("longitude", 0),
                    latitude=location.get("latitude", 0)
                ),
                visit_duration=120,  # 默认2小时
                description=f"{poi.get('type', '景点')} - {poi.get('address', '')}",
                category=poi.get("type", "景点"),
                poi_id=poi.get("id", "")
            ))

        # 存入缓存
        await cache.set(cache_key, attractions, ttl=7200)  # 2小时

        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "attraction_node_completed",
            city=request.city,
            count=len(attractions),
            execution_time_ms=execution_time_ms,
            trace_id=trace_id
        )

        return {
            "attractions": attractions,
            "node_status": {**state.get("node_status", {}), "search_attractions": "completed"},
            "node_timings": {**state.get("node_timings", {}), "search_attractions": execution_time_ms}
        }

    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.error(
            "attraction_node_failed",
            error=str(e),
            city=request.city,
            execution_time_ms=execution_time_ms,
            trace_id=trace_id
        )

        # 返回错误状态，让流程继续
        return {
            "attractions": [],
            "node_status": {**state.get("node_status", {}), "search_attractions": "failed"},
            "node_errors": {**state.get("node_errors", {}), "search_attractions": str(e)},
            "node_timings": {**state.get("node_timings", {}), "search_attractions": execution_time_ms}
        }
