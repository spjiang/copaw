"""Weather query tool using China Weather Network (weather.com.cn)."""

import re
import json
import asyncio
import logging
from typing import Any

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

logger = logging.getLogger(__name__)

CITY_CODES: dict[str, str] = {
    "北京": "101010100",
    "上海": "101020100",
    "广州": "101280101",
    "深圳": "101280601",
    "杭州": "101210101",
    "成都": "101270101",
    "武汉": "101200101",
    "南京": "101190101",
    "西安": "101110101",
    "重庆": "101040100",
    "天津": "101030100",
    "苏州": "101190401",
    "长沙": "101250101",
    "郑州": "101180101",
    "济南": "101120101",
    "哈尔滨": "101050101",
    "沈阳": "101070101",
    "长春": "101060101",
    "昆明": "101290101",
    "贵阳": "101260101",
    "南宁": "101300101",
    "海口": "101310101",
    "乌鲁木齐": "101130101",
    "兰州": "101160101",
    "西宁": "101150101",
    "银川": "101170101",
    "呼和浩特": "101080101",
    "福州": "101230101",
    "厦门": "101230201",
    "南昌": "101240101",
    "合肥": "101220101",
    "石家庄": "101090101",
    "太原": "101100101",
    "青岛": "101120201",
    "大连": "101070201",
    "宁波": "101210401",
    "温州": "101210701",
    "沙坪坝": "101040106",
    "渝中": "101040100",
    "江北": "101040200",
    "南岸": "101040300",
    "北碚": "101040400",
    "九龙坡": "101040700",
    "佛山": "101280800",
    "东莞": "101281601",
}

WEATHER_CODE_MAP: dict[str, str] = {
    "00": "晴", "01": "多云", "02": "阴", "03": "阵雨", "04": "雷阵雨",
    "07": "小雨", "08": "中雨", "09": "大雨", "10": "暴雨",
    "11": "大暴雨", "13": "小雪", "14": "中雪", "15": "大雪",
    "16": "暴雪", "19": "冻雨", "53": "霾",
}


async def get_weather(city: str, **kwargs: Any) -> ToolResponse:
    """查询中国城市的实时天气和未来预报（使用中国天气网接口，无需 API Key）。

    Args:
        city (`str`):
            城市名称，例如"北京"、"上海"、"重庆"、"沙坪坝"等。
    """
    city_code = CITY_CODES.get(city)
    if not city_code:
        # 尝试模糊匹配
        for name, code in CITY_CODES.items():
            if city in name or name in city:
                city_code = code
                city = name
                break

    if not city_code:
        return ToolResponse(
            content=[TextBlock(
                type="text",
                text=f"未找到城市 '{city}' 的城市代码，请尝试使用更精确的城市名称（如'重庆'、'沙坪坝'等）。",
            )]
        )

    url = f"http://d1.weather.com.cn/weather_index/{city_code}.html"
    headers = (
        f"-H 'Referer: http://www.weather.com.cn' "
        f"-H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'"
    )
    cmd = f"curl -s --max-time 15 {headers} '{url}'"

    logger.info("🌤️ [Weather] 查询城市: %s (代码: %s)", city, city_code)

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
        raw = stdout.decode("utf-8", errors="replace")
    except Exception as e:
        return ToolResponse(
            content=[TextBlock(type="text", text=f"天气查询失败: {e}")]
        )

    if not raw or len(raw) < 100:
        return ToolResponse(
            content=[TextBlock(type="text", text=f"天气数据为空（城市代码: {city_code}），请稍后重试。")]
        )

    lines = []

    # 解析实时天气 dataSK
    m = re.search(r"dataSK\s*=\s*(\{.*?\})", raw)
    if m:
        try:
            d = json.loads(m.group(1))
            lines.append(f"📍 {d.get('cityname', city)} 实时天气（{d.get('date', '')} {d.get('time', '')} 更新）")
            lines.append(f"🌤️ 天气：{d.get('weather', '未知')}")
            lines.append(f"🌡️ 气温：{d.get('temp', '?')}℃")
            lines.append(f"💨 风况：{d.get('WD', '')} {d.get('WS', '')}")
            lines.append(f"💧 湿度：{d.get('SD', '?')}")
            aqi = d.get("aqi", "")
            if aqi:
                lines.append(f"🌫️ AQI：{aqi}")
        except Exception:
            pass

    # 解析今日高低温 cityDZ
    m2 = re.search(r'cityDZ\s*=\s*(\{"weatherinfo":\{.*?\}\})', raw)
    if m2:
        try:
            today = json.loads(m2.group(1))["weatherinfo"]
            lines.append(f"📊 今日：最高 {today.get('temp', '?')}℃ / 最低 {today.get('tempn', '?')}℃")
        except Exception:
            pass

    # 解析 5 天预报 fc
    m3 = re.search(r"var fc\s*=\s*(\{.*?\}\s*\})", raw, re.DOTALL)
    if m3:
        try:
            fc = json.loads(m3.group(1))
            forecast_lines = []
            for day in fc.get("f", [])[:5]:
                dw = WEATHER_CODE_MAP.get(day.get("fa", ""), day.get("fa", ""))
                nw = WEATHER_CODE_MAP.get(day.get("fb", ""), day.get("fb", ""))
                forecast_lines.append(
                    f"  {day.get('fi', '')}({day.get('fj', '')})  "
                    f"白天:{dw}  夜间:{nw}  "
                    f"{day.get('fc', '?')}℃/{day.get('fd', '?')}℃  "
                    f"{day.get('fe', '')} {day.get('fg', '')}"
                )
            if forecast_lines:
                lines.append("\n📅 未来预报：")
                lines.extend(forecast_lines)
        except Exception:
            pass

    if not lines:
        return ToolResponse(
            content=[TextBlock(
                type="text",
                text=f"获取到数据但解析失败，原始响应长度 {len(raw)} 字节。",
            )]
        )

    return ToolResponse(
        content=[TextBlock(type="text", text="\n".join(lines))]
    )
