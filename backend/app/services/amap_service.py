"""高德地图MCP服务封装

基于MCP协议的高德地图服务
"""

import json
import re
from typing import List, Dict, Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.core.exceptions import AmapServiceError
from app.core.logging import get_logger
from app.models.schemas import Location, POIInfo, WeatherInfo

logger = get_logger(__name__)


class AmapService:
    """高德地图服务封装类"""

    def __init__(self):
        """初始化服务"""
        self.settings = get_settings()
        self.api_key = self.settings.amap_api_key

    async def _get_mcp_session(self):
        """获取MCP会话"""
        server_params = StdioServerParameters(
            command="uvx",
            args=["amap-mcp-server"],
            env={"AMAP_MAPS_API_KEY": self.api_key}
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def search_poi(
        self,
        keywords: str,
        city: str,
        citylimit: bool = True
    ) -> List[POIInfo]:
        """搜索POI

        Args:
            keywords: 搜索关键词
            city: 城市
            citylimit: 是否限制在城市范围内

        Returns:
            POI信息列表
        """
        try:
            async for session in self._get_mcp_session():
                result = await session.call_tool(
                    "maps_text_search",
                    {
                        "keywords": keywords,
                        "city": city,
                        "citylimit": str(citylimit).lower()
                    }
                )
                return self._parse_poi_result(result)
        except Exception as e:
            logger.error("poi_search_failed", error=str(e), keywords=keywords, city=city)
            raise AmapServiceError(f"POI搜索失败: {str(e)}")

    def _parse_poi_result(self, result) -> List[POIInfo]:
        """解析POI搜索结果"""
        pois = []
        for content in result.content:
            if content.type == "text":
                try:
                    data = json.loads(content.text)
                    if data.get("status") == "1" and data.get("pois"):
                        for poi in data["pois"]:
                            location = self._parse_location(poi.get("location", ""))
                            pois.append(POIInfo(
                                id=poi.get("id", ""),
                                name=poi.get("name", ""),
                                type=poi.get("type", ""),
                                address=poi.get("address", ""),
                                location=location,
                                tel=poi.get("tel")
                            ))
                except json.JSONDecodeError:
                    continue
        return pois

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def get_weather(self, city: str) -> List[WeatherInfo]:
        """查询天气

        Args:
            city: 城市名称

        Returns:
            天气信息列表
        """
        try:
            async for session in self._get_mcp_session():
                result = await session.call_tool(
                    "maps_weather",
                    {"city": city}
                )
                return self._parse_weather_result(result)
        except Exception as e:
            logger.error("weather_query_failed", error=str(e), city=city)
            raise AmapServiceError(f"天气查询失败: {str(e)}")

    def _parse_weather_result(self, result) -> List[WeatherInfo]:
        """解析天气结果"""
        weather_list = []
        for content in result.content:
            if content.type == "text":
                try:
                    data = json.loads(content.text)
                    if data.get("status") == "1" and data.get("forecasts"):
                        for forecast in data["forecasts"]:
                            for cast in forecast.get("casts", []):
                                weather_list.append(WeatherInfo(
                                    date=cast.get("date", ""),
                                    day_weather=cast.get("dayweather", ""),
                                    night_weather=cast.get("nightweather", ""),
                                    day_temp=cast.get("daytemp", 0),
                                    night_temp=cast.get("nighttemp", 0),
                                    wind_direction=cast.get("daywind", ""),
                                    wind_power=cast.get("daypower", "")
                                ))
                except json.JSONDecodeError:
                    continue
        return weather_list

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def plan_route(
        self,
        origin_address: str,
        destination_address: str,
        origin_city: Optional[str] = None,
        destination_city: Optional[str] = None,
        route_type: str = "driving"
    ) -> Dict[str, Any]:
        """规划路线

        Args:
            origin_address: 起点地址
            destination_address: 终点地址
            origin_city: 起点城市
            destination_city: 终点城市
            route_type: 路线类型

        Returns:
            路线信息
        """
        tool_map = {
            "walking": "maps_direction_walking_by_address",
            "driving": "maps_direction_driving_by_address",
            "transit": "maps_direction_transit_integrated_by_address"
        }
        tool_name = tool_map.get(route_type, "maps_direction_driving_by_address")

        arguments = {
            "origin_address": origin_address,
            "destination_address": destination_address
        }
        if origin_city:
            arguments["origin_city"] = origin_city
        if destination_city:
            arguments["destination_city"] = destination_city

        try:
            async for session in self._get_mcp_session():
                result = await session.call_tool(tool_name, arguments)
                return self._parse_route_result(result)
        except Exception as e:
            logger.error("route_planning_failed", error=str(e))
            raise AmapServiceError(f"路线规划失败: {str(e)}")

    def _parse_route_result(self, result) -> Dict[str, Any]:
        """解析路线结果"""
        for content in result.content:
            if content.type == "text":
                try:
                    data = json.loads(content.text)
                    if data.get("status") == "1" and data.get("route"):
                        route = data["route"]
                        paths = route.get("paths", [])
                        if paths:
                            path = paths[0]
                            return {
                                "distance": path.get("distance", 0),
                                "duration": path.get("duration", 0),
                                "steps": path.get("steps", [])
                            }
                except json.JSONDecodeError:
                    continue
        return {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def geocode(self, address: str, city: Optional[str] = None) -> Optional[Location]:
        """地理编码

        Args:
            address: 地址
            city: 城市

        Returns:
            经纬度坐标
        """
        arguments = {"address": address}
        if city:
            arguments["city"] = city

        try:
            async for session in self._get_mcp_session():
                result = await session.call_tool("maps_geo", arguments)
                return self._parse_geocode_result(result)
        except Exception as e:
            logger.error("geocode_failed", error=str(e), address=address)
            raise AmapServiceError(f"地理编码失败: {str(e)}")

    def _parse_geocode_result(self, result) -> Optional[Location]:
        """解析地理编码结果"""
        for content in result.content:
            if content.type == "text":
                try:
                    data = json.loads(content.text)
                    if data.get("status") == "1" and data.get("geocodes"):
                        geocode = data["geocodes"][0]
                        location = geocode.get("location", "")
                        return self._parse_location(location)
                except (json.JSONDecodeError, IndexError):
                    continue
        return None

    def _parse_location(self, location_str: str) -> Location:
        """解析经纬度字符串"""
        if "," in location_str:
            try:
                lng, lat = location_str.split(",")
                return Location(longitude=float(lng), latitude=float(lat))
            except ValueError:
                pass
        return Location(longitude=0.0, latitude=0.0)


# 全局服务实例
_amap_service = None


def get_amap_service() -> AmapService:
    """获取高德地图服务实例(单例模式)"""
    global _amap_service
    if _amap_service is None:
        _amap_service = AmapService()
    return _amap_service
