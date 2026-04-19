from langchain.tools import tool

@tool
def estimate_budget(city: str, days: int, budget: int) -> str:
    """根据城市、天数和预算，评估旅行预算是否合理。"""
    if days <= 0 or budget <= 0:
        return "预算评估失败：days 和 budget 必须大于 0。"

    avg_per_day = budget / days

    if avg_per_day >= 800:
        level = "预算充足"
        suggestion = "可考虑较舒适住宿、热门餐厅和核心景点。"
    elif avg_per_day >= 400:
        level = "预算中等"
        suggestion = "建议控制住宿和交通成本，餐饮以本地特色为主。"
    else:
        level = "预算偏紧"
        suggestion = "建议优先免费景点、公共交通和经济型住宿。"

    return (
        f"{city}{days}天总预算{budget}元，日均约{avg_per_day:.0f}元，"
        f"判断：{level}。建议：{suggestion}"
    )