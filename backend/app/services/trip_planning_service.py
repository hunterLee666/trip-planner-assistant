"""
智能旅行助手 - 新版旅行规划服务

集成LangGraph的行程规划服务
"""

import time
import uuid
from typing import Optional

from app.agents.graph import get_trip_planning_graph
from app.agents.state import create_initial_state
from app.core.logging import get_logger
from app.models.schemas import TripPlan, TripRequest

logger = get_logger(__name__)


class TripPlanningService:
    """旅行规划服务

    使用LangGraph状态图生成旅行计划
    """

    def __init__(self):
        self.graph = get_trip_planning_graph()

    async def plan_trip(
        self,
        request: TripRequest,
        user_id: Optional[str] = None
    ) -> TripPlan:
        """生成旅行计划

        Args:
            request: 旅行请求
            user_id: 用户ID（可选）

        Returns:
            旅行计划
        """
        trace_id = str(uuid.uuid4())
        start_time = time.time()

        logger.info(
            "trip_planning_started",
            city=request.city,
            days=request.travel_days,
            user_id=user_id,
            trace_id=trace_id
        )

        try:
            # 创建初始状态
            initial_state = create_initial_state(
                request=request,
                trace_id=trace_id,
                user_id=user_id
            )

            # 执行状态图
            config = {
                "configurable": {
                    "thread_id": trace_id,
                }
            }

            final_state = await self.graph.ainvoke(
                initial_state,
                config=config
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            # 获取结果
            trip_plan = final_state.get("trip_plan")

            if trip_plan is None:
                logger.error(
                    "trip_planning_failed_no_result",
                    trace_id=trace_id
                )
                raise ValueError("未能生成旅行计划")

            # 更新执行时间
            trip_plan.execution_time_ms = execution_time_ms

            logger.info(
                "trip_planning_completed",
                city=request.city,
                days=len(trip_plan.days),
                execution_time_ms=execution_time_ms,
                fallback_activated=final_state.get("fallback_activated", False),
                trace_id=trace_id
            )

            return trip_plan

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.error(
                "trip_planning_failed",
                error=str(e),
                city=request.city,
                execution_time_ms=execution_time_ms,
                trace_id=trace_id
            )

            raise


# 全局服务实例
_trip_planning_service: Optional[TripPlanningService] = None


def get_trip_planning_service() -> TripPlanningService:
    """获取旅行规划服务实例（单例）

    Returns:
        TripPlanningService: 旅行规划服务
    """
    global _trip_planning_service

    if _trip_planning_service is None:
        _trip_planning_service = TripPlanningService()

    return _trip_planning_service
