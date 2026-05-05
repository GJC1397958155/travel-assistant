from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from tools.amap_geo_tool import geocode_address, reverse_geocode
from tools.amap_hotel_tool import search_hotels
from tools.amap_nearby_tool import search_nearby_pois
from tools.amap_poi_tool import search_pois
from tools.amap_route_tool import plan_route
from tools.budget_tool import estimate_budget
from tools.rag_tool import search_travel_knowledge
from tools.weather_tool import get_weather


mcp = FastMCP("travel-assistant-tools")


@mcp.tool()
def weather(city: str, date: str = "") -> str:
    """Query real weather for a city and an optional date."""
    return get_weather.invoke({"city": city, "date": date})


@mcp.tool()
def poi_search(city: str, preference: str = "热门") -> str:
    """Search real AMap POI recommendations for a city."""
    return search_pois.invoke({"city": city, "preference": preference})


@mcp.tool()
def hotel_search(city: str, area: str = "") -> str:
    """Search real AMap hotel POIs in a city or nearby area."""
    return search_hotels.invoke({"city": city, "area": area})


@mcp.tool()
def nearby_poi_search(
    center: str,
    keywords: str = "餐厅",
    city: str = "",
    radius: int = 2000,
) -> str:
    """Search real AMap POIs around a center point."""
    return search_nearby_pois.invoke(
        {
            "center": center,
            "keywords": keywords,
            "city": city,
            "radius": radius,
        }
    )


@mcp.tool()
def geocode(address: str, city: str = "") -> str:
    """Convert an address to coordinates through AMap."""
    return geocode_address.invoke({"address": address, "city": city})


@mcp.tool()
def reverse_geocode_location(location: str) -> str:
    """Convert lng,lat coordinates to a structured address through AMap."""
    return reverse_geocode.invoke({"location": location})


@mcp.tool()
def route_plan(
    origin: str,
    destination: str,
    city: str = "",
    mode: str = "walking",
) -> str:
    """Plan a real route through AMap. mode supports walking, driving, transit."""
    return plan_route.invoke(
        {
            "origin": origin,
            "destination": destination,
            "city": city,
            "mode": mode,
        }
    )


@mcp.tool()
def budget_estimate(city: str, days: int, budget: int) -> str:
    """Estimate travel budget suitability."""
    return estimate_budget.invoke({"city": city, "days": days, "budget": budget})


@mcp.tool()
def travel_knowledge_search(query: str) -> str:
    """Search the local travel knowledge base."""
    return search_travel_knowledge.invoke({"query": query})


if __name__ == "__main__":
    mcp.run()
