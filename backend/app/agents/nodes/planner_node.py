"""
智能旅行助手 - 行程规划Agent节点

LangGraph节点实现
"""

import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.agents.state import TripPlanningState, is_all_parallel_nodes_completed
from app.core.logging import get_logger
from app.models.schemas import (
    Attraction,
    Budget,
    DayPlan,
    Hotel,
    Location,
    Meal,
    TripPlan,
    WeatherInfo,
)

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """你是专业的行程规划专家。请根据提供的景点、天气和酒店信息，生成详细的旅行计划。

要求：
1. 每天安排2-3个景点，考虑距离和游览时间
2. 每天包含早中晚三餐推荐
3. 根据天气调整户外活动安排
4. 推荐合适的酒店（从提供的酒店列表中选择）
5. 计算预算，包括门票、餐饮、住宿、交通

输出格式必须是JSON：
{
  "city": "城市名称",
  "days": [
    {
      "date": "YYYY-MM-DD",
      "day_index": 0,
      "description": "当日行程概述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {
        "name": "酒店名称",
        "address": "酒店地址",
        "estimated_cost": 400
      },
      "attractions": [
        {
          "name": "景点名称",
          "address": "地址",
          "visit_duration": 120,
          "description": "景点描述",
          "ticket_price": 60
        }
      ],
      "meals": [
        {"type": "breakfast", "name": "早餐", "estimated_cost": 30},
        {"type": "lunch", "name": "午餐", "estimated_cost": 60},
        {"type": "dinner", "name": "晚餐", "estimated_cost": 100}
      ]
    }
  ],
  "budget": {
    "total_attractions": 0,
    "total_hotels": 0,
    "total_meals": 0,
    "total_transportation": 0,
    "total": 0
  },
  "overall_suggestions": "总体建议"
}"""


async def planner_node(
    state: TripPlanningState,
    config: RunnableConfig
) -> Dict[str, Any]:
    """行程规划节点

    整合景点、天气、酒店信息，生成完整的旅行计划

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
        "planner_node_started",
        city=request.city,
        days=request.travel_days,
        trace_id=trace_id
    )

    # 检查前置节点是否完成
    if not is_all_parallel_nodes_completed(state):
        logger.warning(
            "planner_node_waiting",
            node_status=state.get("node_status"),
            trace_id=trace_id
        )
        # 如果前置节点未完成，返回等待状态
        return {
            "node_status": {**state.get("node_status", {}), "generate_plan": "pending"}
        }

    try:
        # 获取前置节点结果
        attractions = state.get("attractions", [])
        weather = state.get("weather", [])
        hotels = state.get("hotels", [])

        # 如果景点为空，使用备用方案
        if not attractions:
            logger.warning(
                "planner_no_attractions",
                city=request.city,
                trace_id=trace_id
            )
            trip_plan = create_fallback_plan(request)
            execution_time_ms = int((time.time() - start_time) * 1000)

            return {
                "trip_plan": trip_plan,
                "fallback_activated": True,
                "node_status": {**state.get("node_status", {}), "generate_plan": "completed"},
                "node_timings": {**state.get("node_timings", {}), "generate_plan": execution_time_ms},
                "execution_time_ms": execution_time_ms
            }

        # 构建输入数据
        input_data = build_planner_input(request, attractions, weather, hotels)

        # 调用LLM生成计划
        from app.services.llm_service import get_llm
        llm = get_llm()

        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=input_data)
        ]

        response = await llm.ainvoke(messages)

        # 解析JSON响应
        trip_plan = parse_planner_response(response.content, request)

        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "planner_node_completed",
            city=request.city,
            days=len(trip_plan.days),
            execution_time_ms=execution_time_ms,
            trace_id=trace_id
        )

        return {
            "trip_plan": trip_plan,
            "node_status": {**state.get("node_status", {}), "generate_plan": "completed"},
            "node_timings": {**state.get("node_timings", {}), "generate_plan": execution_time_ms},
            "execution_time_ms": execution_time_ms
        }

    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.error(
            "planner_node_failed",
            error=str(e),
            city=request.city,
            execution_time_ms=execution_time_ms,
            trace_id=trace_id
        )

        # 失败时使用备用方案
        trip_plan = create_fallback_plan(request)

        return {
            "trip_plan": trip_plan,
            "fallback_activated": True,
            "error": str(e),
            "node_status": {**state.get("node_status", {}), "generate_plan": "completed"},
            "node_errors": {**state.get("node_errors", {}), "generate_plan": str(e)},
            "node_timings": {**state.get("node_timings", {}), "generate_plan": execution_time_ms},
            "execution_time_ms": execution_time_ms
        }


def build_planner_input(
    request,
    attractions: list,
    weather: list,
    hotels: list
) -> str:
    """构建规划器的输入数据"""

    input_parts = [
        f"目的地: {request.city}",
        f"旅行日期: {request.start_date} 至 {request.end_date}",
        f"天数: {request.travel_days}",
        f"交通方式: {request.transportation}",
        f"住宿偏好: {request.accommodation}",
        f"旅行偏好: {', '.join(request.preferences) if request.preferences else '无'}",
        "",
        "景点信息:",
    ]

    for i, attr in enumerate(attractions[:15], 1):  # 最多15个景点
        input_parts.append(f"{i}. {attr.name} - {attr.address} (游览约{attr.visit_duration}分钟)")

    if weather:
        input_parts.extend(["", "天气信息:"])
        for w in weather[:request.travel_days]:
            input_parts.append(
                f"{w.date}: 白天{w.day_weather} {w.day_temp}°C, "
                f"夜间{w.night_weather} {w.night_temp}°C"
            )

    if hotels:
        input_parts.extend(["", "可选酒店:"])
        for i, hotel in enumerate(hotels[:10], 1):
            input_parts.append(f"{i}. {hotel.name} - {hotel.address}")

    return "\n".join(input_parts)


def parse_planner_response(content: str, request) -> TripPlan:
    """解析规划器响应"""

    # 提取JSON
    json_str = content
    if "```json" in content:
        json_str = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        json_str = content.split("```")[1].split("```")[0].strip()

    data = json.loads(json_str)

    # 解析days
    days = []
    for day_data in data.get("days", []):
        day = DayPlan(
            date=day_data.get("date", ""),
            day_index=day_data.get("day_index", 0),
            description=day_data.get("description", ""),
            transportation=day_data.get("transportation", request.transportation),
            accommodation=day_data.get("accommodation", request.accommodation),
            hotel=_parse_hotel(day_data.get("hotel", {})),
            attractions=[_parse_attraction(a) for a in day_data.get("attractions", [])],
            meals=[_parse_meal(m) for m in day_data.get("meals", [])]
        )
        days.append(day)

    # 解析预算
    budget_data = data.get("budget", {})
    budget = Budget(
        total_attractions=budget_data.get("total_attractions", 0),
        total_hotels=budget_data.get("total_hotels", 0),
        total_meals=budget_data.get("total_meals", 0),
        total_transportation=budget_data.get("total_transportation", 0),
        total=budget_data.get("total", 0)
    )

    return TripPlan(
        city=data.get("city", request.city),
        start_date=request.start_date,
        end_date=request.end_date,
        days=days,
        weather_info=[],  # 可以从state获取
        overall_suggestions=data.get("overall_suggestions", ""),
        budget=budget
    )


def _parse_hotel(data: dict) -> Hotel:
    """解析酒店数据"""
    return Hotel(
        name=data.get("name", ""),
        address=data.get("address", ""),
        estimated_cost=data.get("estimated_cost", 0)
    )


def _parse_attraction(data: dict) -> Attraction:
    """解析景点数据"""
    return Attraction(
        name=data.get("name", ""),
        address=data.get("address", ""),
        location=Location(longitude=0, latitude=0),  # 简化处理
        visit_duration=data.get("visit_duration", 120),
        description=data.get("description", ""),
        ticket_price=data.get("ticket_price", 0)
    )


def _parse_meal(data: dict) -> Meal:
    """解析餐饮数据"""
    return Meal(
        type=data.get("type", "lunch"),
        name=data.get("name", ""),
        description=data.get("description", ""),
        estimated_cost=data.get("estimated_cost", 0)
    )


def create_fallback_plan(request) -> TripPlan:
    """创建备用旅行计划"""

    from datetime import datetime

    start = datetime.strptime(request.start_date, "%Y-%m-%d")
    days = []

    for i in range(request.travel_days):
        current_date = start + timedelta(days=i)

        day = DayPlan(
            date=current_date.strftime("%Y-%m-%d"),
            day_index=i,
            description=f"第{i+1}天：探索{request.city}",
            transportation=request.transportation,
            accommodation=request.accommodation,
            hotel=Hotel(
                name=f"{request.city}酒店推荐",
                address=request.city
            ),
            attractions=[
                Attraction(
                    name=f"{request.city}热门景点{j+1}",
                    address=request.city,
                    location=Location(longitude=116.4, latitude=39.9),
                    visit_duration=120,
                    description=f"{request.city}的著名景点",
                    ticket_price=50
                )
                for j in range(2)
            ],
            meals=[
                Meal(type="breakfast", name="当地特色早餐", estimated_cost=30),
                Meal(type="lunch", name="当地特色午餐", estimated_cost=60),
                Meal(type="dinner", name="当地特色晚餐", estimated_cost=100)
            ]
        )
        days.append(day)

    total_attractions = sum(len(d.attractions) * 50 for d in days)
    total_meals = sum(sum(m.estimated_cost for m in d.meals) for d in days)
    total_hotels = 400 * request.travel_days

    return TripPlan(
        city=request.city,
        start_date=request.start_date,
        end_date=request.end_date,
        days=days,
        weather_info=[],
        overall_suggestions=f"这是为您准备的{request.city}{request.travel_days}日游备用行程。建议提前查询各景点开放时间和预订酒店。",
        budget=Budget(
            total_attractions=total_attractions,
            total_hotels=total_hotels,
            total_meals=total_meals,
            total_transportation=100,
            total=total_attractions + total_hotels + total_meals + 100
        )
    )
