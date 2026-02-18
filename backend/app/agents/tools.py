"""
智能旅行助手 - LangGraph工具定义

使用LangChain的@tool装饰器定义Agent可用工具
"""

import json
from typing import List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.exceptions import AmapServiceError
from app.core.logging import get_logger
from app.models.schemas import Location, POIInfo, WeatherInfo
from app.services.amap_service import get_amap_service

logger = get_logger(__name__)


# ============ POI搜索工具 ============

class SearchPOIInput(BaseModel):
    """POI搜索输入参数"""
    keywords: str = Field(
        description="搜索关键词，如'故宫'、'历史文化'、'美食街'",
        examples=["故宫", "公园", "博物馆"]
    )
    city: str = Field(
        description="城市名称，如'北京'、'上海'",
        examples=["北京", "上海"]
    )
    citylimit: bool = Field(
        default=True,
        description="是否限制在城市范围内搜索，默认为True"
    )


@tool(args_schema=SearchPOIInput)
async def search_poi(
    keywords: str,
    city: str,
    citylimit: bool = True
) -> str:
    """搜索城市中的景点、POI（兴趣点）。
    
    这是旅行规划的核心工具，用于查找用户可能感兴趣的景点。
    支持搜索各种类型的地点，包括历史景点、公园、博物馆、购物中心等。
    
    Args:
        keywords: 搜索关键词
        city: 城市名称
        citylimit: 是否限制在城市范围内
        
    Returns:
        JSON格式的POI列表字符串
        
    Examples:
        >>> result = await search_poi("故宫", "北京")
        >>> result = await search_poi("历史文化", "西安")
        >>> result = await search_poi("亲子乐园", "上海")
    """
    try:
        logger.info(
            "poi_search_tool_called",
            keywords=keywords,
            city=city,
            citylimit=citylimit
        )
        
        service = get_amap_service()
        pois = await service.search_poi(keywords, city, citylimit)
        
        # 格式化为易读的JSON
        result = {
            "total": len(pois),
            "pois": [
                {
                    "name": poi.name,
                    "address": poi.address,
                    "location": {
                        "longitude": poi.location.longitude,
                        "latitude": poi.location.latitude
                    },
                    "type": poi.type,
                    "tel": poi.tel,
                }
                for poi in pois[:10]  # 只返回前10个
            ]
        }
        
        logger.info(
            "poi_search_tool_completed",
            keywords=keywords,
            city=city,
            count=len(pois)
        )
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(
            "poi_search_tool_failed",
            keywords=keywords,
            city=city,
            error=str(e)
        )
        raise AmapServiceError(f"POI搜索失败: {str(e)}") from e


# ============ 天气查询工具 ============

class QueryWeatherInput(BaseModel):
    """天气查询输入参数"""
    city: str = Field(
        description="城市名称，如'北京'、'上海'",
        examples=["北京", "杭州"]
    )


@tool(args_schema=QueryWeatherInput)
async def query_weather(city: str) -> str:
    """查询城市天气信息。
    
    获取指定城市的天气预报，用于旅行规划时考虑天气因素。
    返回包括温度、天气状况、风力等信息。
    
    Args:
        city: 城市名称
        
    Returns:
        JSON格式的天气信息字符串
        
    Examples:
        >>> result = await query_weather("北京")
        >>> result = await query_weather("三亚")
    """
    try:
        logger.info("weather_query_tool_called", city=city)
        
        service = get_amap_service()
        weather_list = await service.get_weather(city)
        
        # 格式化为易读的JSON
        result = {
            "city": city,
            "forecast": [
                {
                    "date": w.date,
                    "day_weather": w.day_weather,
                    "night_weather": w.night_weather,
                    "day_temp": w.day_temp,
                    "night_temp": w.night_temp,
                    "wind_direction": w.wind_direction,
                    "wind_power": w.wind_power,
                }
                for w in weather_list
            ]
        }
        
        logger.info(
            "weather_query_tool_completed",
            city=city,
            days=len(weather_list)
        )
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error("weather_query_tool_failed", city=city, error=str(e))
        raise AmapServiceError(f"天气查询失败: {str(e)}") from e


# ============ 路线规划工具 ============

class PlanRouteInput(BaseModel):
    """路线规划输入参数"""
    origin_address: str = Field(
        description="起点地址",
        examples=["北京市朝阳区天安门"]
    )
    destination_address: str = Field(
        description="终点地址",
        examples=["北京市海淀区颐和园"]
    )
    route_type: str = Field(
        default="driving",
        description="路线类型: driving(驾车), walking(步行), transit(公交)",
        examples=["driving", "walking", "transit"]
    )
    origin_city: Optional[str] = Field(
        default=None,
        description="起点城市（可选，用于提高准确性）"
    )
    destination_city: Optional[str] = Field(
        default=None,
        description="终点城市（可选，用于提高准确性）"
    )


@tool(args_schema=PlanRouteInput)
async def plan_route(
    origin_address: str,
    destination_address: str,
    route_type: str = "driving",
    origin_city: Optional[str] = None,
    destination_city: Optional[str] = None
) -> str:
    """规划两点之间的路线。
    
    支持驾车、步行、公交三种路线类型。
    返回距离、时间、路线描述等信息。
    
    Args:
        origin_address: 起点地址
        destination_address: 终点地址
        route_type: 路线类型 (driving/walking/transit)
        origin_city: 起点城市（可选）
        destination_city: 终点城市（可选）
        
    Returns:
        JSON格式的路线信息字符串
        
    Examples:
        >>> result = await plan_route("天安门", "颐和园", "driving")
        >>> result = await plan_route("酒店", "故宫", "walking", origin_city="北京")
    """
    try:
        logger.info(
            "route_planning_tool_called",
            origin=origin_address,
            destination=destination_address,
            route_type=route_type
        )
        
        service = get_amap_service()
        route_info = await service.plan_route(
            origin_address=origin_address,
            destination_address=destination_address,
            origin_city=origin_city,
            destination_city=destination_city,
            route_type=route_type
        )
        
        result = {
            "origin": origin_address,
            "destination": destination_address,
            "route_type": route_type,
            "distance_meters": route_info.get("distance", 0),
            "duration_seconds": route_info.get("duration", 0),
            "distance_km": round(route_info.get("distance", 0) / 1000, 2),
            "duration_minutes": round(route_info.get("duration", 0) / 60, 1),
            "description": route_info.get("description", ""),
        }
        
        logger.info(
            "route_planning_tool_completed",
            origin=origin_address,
            destination=destination_address,
            distance=result["distance_km"],
            duration=result["duration_minutes"]
        )
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(
            "route_planning_tool_failed",
            origin=origin_address,
            destination=destination_address,
            error=str(e)
        )
        raise AmapServiceError(f"路线规划失败: {str(e)}") from e


# ============ 地理编码工具 ============

class GeocodeInput(BaseModel):
    """地理编码输入参数"""
    address: str = Field(
        description="要编码的地址",
        examples=["北京市东城区景山前街4号"]
    )
    city: Optional[str] = Field(
        default=None,
        description="城市（可选，用于提高准确性）"
    )


@tool(args_schema=GeocodeInput)
async def geocode_address(address: str, city: Optional[str] = None) -> str:
    """将地址转换为经纬度坐标。
    
    用于获取精确的位置信息，在地图上标记或计算距离。
    
    Args:
        address: 完整地址
        city: 城市（可选）
        
    Returns:
        JSON格式的坐标信息字符串
        
    Examples:
        >>> result = await geocode_address("故宫博物院", "北京")
    """
    try:
        logger.info("geocode_tool_called", address=address, city=city)
        
        service = get_amap_service()
        location = await service.geocode(address, city)
        
        if location:
            result = {
                "address": address,
                "longitude": location.longitude,
                "latitude": location.latitude,
                "found": True
            }
        else:
            result = {
                "address": address,
                "found": False,
                "error": "无法解析该地址"
            }
        
        logger.info(
            "geocode_tool_completed",
            address=address,
            found=result["found"]
        )
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error("geocode_tool_failed", address=address, error=str(e))
        raise AmapServiceError(f"地理编码失败: {str(e)}") from e


# ============ 酒店搜索工具 ============

class SearchHotelInput(BaseModel):
    """酒店搜索输入参数"""
    city: str = Field(
        description="城市名称",
        examples=["北京", "上海"]
    )
    keywords: str = Field(
        default="酒店",
        description="搜索关键词，如'酒店'、'民宿'、'经济型酒店'",
        examples=["酒店", "五星级", "民宿"]
    )
    location: Optional[str] = Field(
        default=None,
        description="附近地点（可选），如'天安门附近'"
    )


@tool(args_schema=SearchHotelInput)
async def search_hotels(
    city: str,
    keywords: str = "酒店",
    location: Optional[str] = None
) -> str:
    """搜索城市中的酒店。
    
    根据城市和关键词搜索酒店信息，支持按位置筛选。
    
    Args:
        city: 城市名称
        keywords: 搜索关键词
        location: 附近地点（可选）
        
    Returns:
        JSON格式的酒店列表字符串
        
    Examples:
        >>> result = await search_hotels("北京", "五星级")
        >>> result = await search_hotels("上海", "民宿", "外滩附近")
    """
    try:
        search_keyword = f"{keywords}"
        if location:
            search_keyword = f"{location}{keywords}"
        
        logger.info(
            "hotel_search_tool_called",
            city=city,
            keywords=search_keyword
        )
        
        service = get_amap_service()
        hotels = await service.search_poi(search_keyword, city, citylimit=True)
        
        # 过滤出酒店类型的POI
        hotel_list = []
        for poi in hotels:
            if any(keyword in poi.type for keyword in ["酒店", "宾馆", "住宿", "旅馆"]):
                hotel_list.append({
                    "name": poi.name,
                    "address": poi.address,
                    "location": {
                        "longitude": poi.location.longitude,
                        "latitude": poi.location.latitude
                    },
                    "type": poi.type,
                    "tel": poi.tel,
                })
        
        result = {
            "total": len(hotel_list),
            "hotels": hotel_list[:10]  # 只返回前10个
        }
        
        logger.info(
            "hotel_search_tool_completed",
            city=city,
            keywords=search_keyword,
            count=len(hotel_list)
        )
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(
            "hotel_search_tool_failed",
            city=city,
            keywords=keywords,
            error=str(e)
        )
        raise AmapServiceError(f"酒店搜索失败: {str(e)}") from e


# ============ 工具列表 ============

TRIP_PLANNING_TOOLS = [
    search_poi,
    query_weather,
    plan_route,
    geocode_address,
    search_hotels,
]
"""旅行规划工具列表 - 供LangGraph使用"""
