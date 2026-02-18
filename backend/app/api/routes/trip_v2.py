"""
智能旅行助手 - 新版API路由

旅行规划相关API端点
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.api.dependencies import get_current_user, get_optional_user
from app.core.exceptions import TripPlanningError, ValidationError
from app.core.logging import bind_context, get_logger
from app.models.schemas import (
    ErrorResponse,
    TripPlanResponse,
    TripRequest,
)
from app.services.trip_planning_service import get_trip_planning_service

logger = get_logger(__name__)

router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post(
    "/plan",
    response_model=TripPlanResponse,
    summary="生成旅行计划",
    description="根据用户输入的旅行需求，使用LangGraph生成详细的旅行计划",
    responses={
        200: {"description": "成功生成旅行计划"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        401: {"description": "未认证", "model": ErrorResponse},
        500: {"description": "服务器内部错误", "model": ErrorResponse},
    }
)
async def plan_trip(
    request: TripRequest,
    user_id: str = Depends(get_optional_user)
):
    """生成旅行计划

    使用LangGraph状态图并行处理景点搜索、天气查询和酒店搜索，
    然后整合结果生成完整行程。

    Args:
        request: 旅行请求参数
        user_id: 用户ID（可选，用于关联用户历史）

    Returns:
        旅行计划响应
    """
    # 绑定上下文到日志
    bind_context(user_id=user_id, city=request.city)

    logger.info(
        "plan_trip_api_called",
        city=request.city,
        start_date=request.start_date,
        end_date=request.end_date,
        days=request.travel_days,
        user_id=user_id
    )

    try:
        # 验证请求
        if request.travel_days < 1 or request.travel_days > 30:
            raise ValidationError("旅行天数必须在1-30天之间")

        # 调用服务生成计划
        service = get_trip_planning_service()
        trip_plan = await service.plan_trip(request, user_id)

        logger.info(
            "plan_trip_api_completed",
            city=request.city,
            days=len(trip_plan.days),
            user_id=user_id
        )

        return TripPlanResponse(
            success=True,
            message="旅行计划生成成功",
            data=trip_plan
        )

    except ValidationError as e:
        logger.warning(
            "plan_trip_validation_error",
            error=e.message,
            user_id=user_id
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )

    except TripPlanningError as e:
        logger.error(
            "plan_trip_failed",
            error=e.message,
            user_id=user_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成旅行计划失败: {e.message}"
        )

    except Exception as e:
        logger.exception("plan_trip_unexpected_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )


@router.get(
    "/health",
    summary="健康检查",
    description="检查旅行规划服务是否正常"
)
async def health_check():
    """健康检查

    检查服务各组件状态：
    - LangGraph图实例
    - 数据库连接
    - 缓存服务

    Returns:
        健康状态
    """
    try:
        # 检查LangGraph
        from app.agents.graph import get_trip_planning_graph
        graph = get_trip_planning_graph()

        # 检查缓存
        from app.services.cache_service import get_cache_service
        cache = get_cache_service()

        return {
            "status": "healthy",
            "service": "trip-planner",
            "version": "2.0.0",
            "components": {
                "langgraph": "available",
                "cache": "available"
            }
        }

    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@router.get(
    "/status/{trace_id}",
    summary="查询任务状态",
    description="根据trace_id查询行程规划任务的执行状态"
)
async def get_planning_status(trace_id: str):
    """查询规划任务状态

    Args:
        trace_id: 追踪ID

    Returns:
        任务状态信息
    """
    # TODO: 实现从数据库或检查点恢复状态
    return {
        "trace_id": trace_id,
        "status": "not_implemented",
        "message": "此功能正在开发中"
    }
