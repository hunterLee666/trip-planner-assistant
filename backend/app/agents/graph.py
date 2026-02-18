"""
智能旅行助手 - LangGraph图定义

定义旅行规划的状态图工作流
"""

from typing import Optional

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.postgres import PostgresSaver

from app.agents.nodes.attraction_node import attraction_node
from app.agents.nodes.hotel_node import hotel_node
from app.agents.nodes.planner_node import planner_node
from app.agents.nodes.weather_node import weather_node
from app.agents.state import TripPlanningState, is_all_parallel_nodes_completed
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# 全局图实例（单例）
_trip_planning_graph = None
_checkpointer = None


def create_trip_planning_graph(checkpointer=None) -> StateGraph:
    """创建旅行规划状态图

    定义完整的旅行规划工作流：
    1. 并行执行景点搜索、天气查询、酒店搜索
    2. 所有前置任务完成后，执行行程规划

    Args:
        checkpointer: 检查点保存器（可选）

    Returns:
        编译后的状态图
    """

    # 创建工作流
    workflow = StateGraph(TripPlanningState)

    # 添加节点
    workflow.add_node("search_attractions", attraction_node)
    workflow.add_node("query_weather", weather_node)
    workflow.add_node("search_hotels", hotel_node)
    workflow.add_node("generate_plan", planner_node)

    # 设置入口点
    workflow.set_entry_point("search_attractions")

    # 景点搜索完成后，并行启动天气和酒店查询
    workflow.add_edge("search_attractions", "query_weather")
    workflow.add_edge("search_attractions", "search_hotels")

    # 定义条件边：检查所有并行节点是否完成
    def should_generate_plan(state: TripPlanningState) -> str:
        """判断是否所有并行节点都已完成"""
        if is_all_parallel_nodes_completed(state):
            return "generate_plan"
        return END  # 如果未完成，等待（实际上不会执行到这里）

    # 天气和酒店完成后，进入行程生成
    workflow.add_edge("query_weather", "generate_plan")
    workflow.add_edge("search_hotels", "generate_plan")

    # 行程生成完成后结束
    workflow.add_edge("generate_plan", END)

    # 编译图
    return workflow.compile(checkpointer=checkpointer)


def get_checkpointer():
    """获取PostgreSQL检查点保存器（单例）"""
    global _checkpointer

    if _checkpointer is None:
        settings = get_settings()
        if settings.database_url:
            try:
                _checkpointer = PostgresSaver.from_conn_string(
                    settings.database_url.replace("+asyncpg", "")
                )
                logger.info("postgres_checkpointer_initialized")
            except Exception as e:
                logger.warning(
                    "postgres_checkpointer_failed",
                    error=str(e),
                    message="将使用内存检查点"
                )
                _checkpointer = None

    return _checkpointer


def get_trip_planning_graph():
    """获取旅行规划图实例（单例）

    Returns:
        编译后的状态图
    """
    global _trip_planning_graph

    if _trip_planning_graph is None:
        checkpointer = get_checkpointer()
        _trip_planning_graph = create_trip_planning_graph(checkpointer)
        logger.info(
            "trip_planning_graph_initialized",
            has_checkpointer=checkpointer is not None
        )

    return _trip_planning_graph


def reset_graph():
    """重置图实例（用于测试）"""
    global _trip_planning_graph, _checkpointer
    _trip_planning_graph = None
    _checkpointer = None
    logger.info("trip_planning_graph_reset")
