# config.py - 统一配置管理
from typing import Dict, List, Set
from dataclasses import dataclass,field

@dataclass
class SystemConfig:
    # 城市配置
    CITIES: List[str] = field(default_factory=lambda: [
        "北京", "上海", "广州", "深圳", "杭州", "南京", "苏州", 
        "成都", "重庆", "武汉", "西安", "天津", "青岛", "大连", 
        "厦门", "宁波", "无锡", "佛山", "温州", "泉州", "长沙", 
        "郑州", "石家庄", "济南", "哈尔滨", "长春", "沈阳", 
        "太原", "合肥", "南昌", "福州", "贵阳", "昆明", "南宁", 
        "海口", "银川", "西宁", "兰州", "乌鲁木齐", "拉萨", "呼和浩特"
    ])
    
    # 意图关键词配置
    INTENT_KEYWORDS: Dict[str, List[str]] = field(default_factory=lambda: {
        "book_flight": ["机票", "航班", "订飞", "出发", "从.*飞", "飞.*到", "飞"],
        "book_hotel": ["酒店", "住宿", "入住", "住一晚", "订房", "住", "房"]
    })
    
    # 槽位映射配置
    SLOT_MAPPING: Dict[str, str] = field(default_factory=lambda: {
        "出发城市": "flight_departure_city",
        "到达城市": "flight_destination_city",
        "出发日期": "flight_departure_date",
        "酒店城市": "hotel_city",
        "入住日期": "hotel_checkin_date",
        "房型": "hotel_room_type"
    })
    
    # 提示信息配置
    PROMPT_TEMPLATES: Dict[str, str] = field(default_factory=lambda: {
        "flight_departure_city": "请问您从哪个城市出发？",
        "flight_destination_city": "请问您要飞往哪个城市？",
        "flight_departure_date": "请问出发时间是？",
        "hotel_city": "请问酒店所在城市是？",
        "hotel_checkin_date": "请问入住时间是？",
        "hotel_room_type": "请问需要什么房型？"
    })
    
    # 确认关键词配置
    CONFIRMATION_KEYWORDS: Dict[str, List[str]] = field(default_factory=lambda: {
        "confirmation": ["是", "对", "确认", "没错", "正确", "yes", "好的"],
        "rejection": ["不是", "否", "不对", "错了", "no", "不"]
    })
    
    # 工作流步骤描述
    WORKFLOW_DESCRIPTIONS: Dict[str, str] = field(default_factory=lambda: {
        "intent_detection": "🔍 正在识别您的需求...",
        "flight_info_collection": "✈️ 正在收集航班信息...",
        "city_confirmation": "🏙️ 请确认目标城市信息",
        "hotel_selection": "🏨 现在可以选择酒店信息",
        "final_confirmation": "✅ 请确认最终预订信息",
        "completed": "🎉 预订流程已完成"
    })

# 全局配置实例
config = SystemConfig()