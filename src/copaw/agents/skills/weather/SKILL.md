---
name: weather
description: "查询中国城市实时天气和未来预报。直接调用工具 get_weather(city='城市名') 即可，例如 get_weather(city='沙坪坝')、get_weather(city='北京')。禁止使用 execute_shell_command 调用 wttr.in 等境外服务（均已被封锁）。"
metadata:
  {
    "copaw": {
      "emoji": "🌤️",
      "requires": {}
    }
  }
---

# 天气查询

使用**中国天气网**免费接口查询天气，无需 API Key，国内网络可直接访问。

---

## 第一步：确定城市代码

根据用户提到的城市，从下表查找对应的城市代码：

| 城市 | 代码 | 城市 | 代码 | 城市 | 代码 |
|------|------|------|------|------|------|
| 北京 | 101010100 | 上海 | 101020100 | 广州 | 101280101 |
| 深圳 | 101280601 | 杭州 | 101210101 | 成都 | 101270101 |
| 武汉 | 101200101 | 南京 | 101190101 | 西安 | 101110101 |
| 重庆 | 101040100 | 天津 | 101030100 | 苏州 | 101190401 |
| 长沙 | 101250101 | 郑州 | 101180101 | 济南 | 101120101 |
| 哈尔滨 | 101050101 | 沈阳 | 101070101 | 长春 | 101060101 |
| 昆明 | 101290101 | 贵阳 | 101260101 | 南宁 | 101300101 |
| 海口 | 101310101 | 乌鲁木齐 | 101130101 | 兰州 | 101160101 |
| 西宁 | 101150101 | 银川 | 101170101 | 呼和浩特 | 101080101 |
| 福州 | 101230101 | 厦门 | 101230201 | 南昌 | 101240101 |
| 合肥 | 101220101 | 石家庄 | 101090101 | 太原 | 101100101 |
| 青岛 | 101120201 | 大连 | 101070201 | 宁波 | 101210401 |
| 温州 | 101210701 | 佛山 | 101280800 | 东莞 | 101281601 |
| 沙坪坝 | 101040106 | 渝中 | 101040100 | 江北(重庆) | 101040200 |
| 南岸(重庆) | 101040300 | 北碚 | 101040400 | 九龙坡 | 101040700 |

> 如果城市不在表中，询问用户后使用浏览器打开 `https://www.weather.com.cn` 搜索。

---

## 第二步：获取实时天气

使用以下命令获取实时天气数据（将 `{城市代码}` 替换为实际代码，如 `101010100`）：

```bash
curl -s "http://d1.weather.com.cn/weather_index/{城市代码}.html" \
  -H "Referer: http://www.weather.com.cn" \
  -H "User-Agent: Mozilla/5.0"
```

**返回格式说明**：响应是多个 JavaScript 变量赋值，关键字段在 `dataSK` 变量中：

| 字段 | 含义 |
|------|------|
| `cityname` | 城市名 |
| `temp` | 实时温度（℃） |
| `WD` + `WS` | 风向 + 风力等级 |
| `SD` | 湿度 |
| `weather` | 天气状况（如 晴、多云、小雨） |
| `aqi` | 空气质量指数 |
| `date` | 日期 |
| `time` | 数据更新时间 |

`cityDZ` 变量包含今日最高温（`temp`）和最低温（`tempn`）。

**解析示例命令**（提取关键字段）：

```bash
curl -s "http://d1.weather.com.cn/weather_index/101010100.html" \
  -H "Referer: http://www.weather.com.cn" \
  -H "User-Agent: Mozilla/5.0" | \
  grep -o 'dataSK.*};' | head -1 | \
  python3 -c "
import sys, re, json
raw = sys.stdin.read()
m = re.search(r'dataSK\s*=\s*(\{.*?\})', raw)
if m:
    d = json.loads(m.group(1))
    print(f\"城市：{d['cityname']}\")
    print(f\"天气：{d['weather']}\")
    print(f\"温度：{d['temp']}℃\")
    print(f\"风况：{d['WD']} {d['WS']}\")
    print(f\"湿度：{d['SD']}\")
    print(f\"AQI：{d['aqi']}\")
    print(f\"更新：{d['date']} {d['time']}\")
"
```

---

## 第三步：获取未来 5 天预报

```bash
curl -s "http://d1.weather.com.cn/weather_index/{城市代码}.html" \
  -H "Referer: http://www.weather.com.cn" \
  -H "User-Agent: Mozilla/5.0" | \
  python3 -c "
import sys, re, json
raw = sys.stdin.read()

# 解析今明气温（cityDZ）
m1 = re.search(r'cityDZ\s*=\s*(\{\"weatherinfo\":\{.*?\}\})', raw)
if m1:
    today = json.loads(m1.group(1))['weatherinfo']
    print(f\"今天  {today.get('weather','')}  {today.get('temp','?')}℃/{today.get('tempn','?')}℃\")

# 解析 5 天预报（fc 变量）
m2 = re.search(r'var fc\s*=\s*(\{.*?\}\s*\})', raw, re.DOTALL)
if m2:
    fc = json.loads(m2.group(1))
    weather_map = {
        '00':'晴','01':'多云','02':'阴','03':'阵雨','04':'雷阵雨',
        '07':'小雨','08':'中雨','09':'大雨','10':'暴雨',
        '11':'大暴雨','13':'小雪','14':'中雪','15':'大雪',
        '16':'暴雪','19':'冻雨','53':'霾'
    }
    for day in fc.get('f', []):
        day_weather = weather_map.get(day.get('fa',''), day.get('fa',''))
        night_weather = weather_map.get(day.get('fb',''), day.get('fb',''))
        print(f\"{day.get('fi','')}({day.get('fj','')})  白天:{day_weather}  夜间:{night_weather}  {day.get('fc','?')}℃/{day.get('fd','?')}℃  {day.get('fe','')} {day.get('fg','')}\")
"
```

---

## 备用方案（浏览器）

若 `curl` 命令失败，使用 `browser_use` 打开以下网址，然后 `snapshot` 获取内容：

```json
{"action": "open", "url": "https://tianqi.qq.com/weather/{城市代码}"}
```

或直接打开：
- 腾讯天气：`https://tianqi.qq.com/`（搜索城市名）
- 中国天气网：`https://www.weather.com.cn/`

---

## 回复格式建议

```
📍 北京天气（03月03日 10:15更新）

🌡️ 当前：1.9℃ | 霾
📊 今日：最高 5℃ / 最低 0℃
💨 风况：南风 1级
💧 湿度：86%  |  AQI：148（中度污染）

📅 未来预报：
3/3（今天）  多云  10℃/-1℃  东北风<3级
3/4（星期三）阴    3℃/-2℃   东南风<3级
3/5（星期四）阴    3℃/-4℃   东风<3级
```

> 提示用户 AQI > 100 时建议减少户外活动；根据温差提醒加减衣物。
