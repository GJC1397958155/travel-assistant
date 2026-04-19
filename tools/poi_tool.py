from langchain.tools import tool


CITY_POIS = {
    "杭州": {
        "美食": ["河坊街", "胜利河美食街", "武林夜市"],
        "拍照": ["西湖", "灵隐寺", "西溪湿地"],
        "轻松": ["西湖游船", "太子湾公园", "湖滨步行街"],
    },
    "重庆": {
        "美食": ["解放碑", "八一路好吃街", "观音桥"],
        "拍照": ["洪崖洞", "李子坝", "南山一棵树"],
        "轻松": ["磁器口", "弹子石老街", "两江夜游"],
    },
    "上海": {
        "美食": ["云南南路美食街", "城隍庙", "黄河路"],
        "拍照": ["外滩", "武康路", "陆家嘴滨江"],
        "轻松": ["徐汇滨江", "世博文化公园", "前滩休闲公园"],
    },
}


@tool
def search_pois(city: str, preference: str = "热门") -> str:
    """根据城市和偏好返回推荐景点或街区。"""
    data = CITY_POIS.get(city)
    if not data:
        return f"暂时没有{city}的本地景点数据。"

    results = []
    for key, values in data.items():
        if preference in key or key in preference:
            results.extend(values)

    if not results:
        for values in data.values():
            results.extend(values)

    uniq = list(dict.fromkeys(results))
    return f"{city}推荐：{', '.join(uniq[:6])}"
