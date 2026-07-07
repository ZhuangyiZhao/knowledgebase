# entity_extractor.py - 优化后的实体识别器
import re
from typing import List, Tuple, Dict, Optional
from config import config
import logging

logger = logging.getLogger(__name__)

class EntityExtractor:
    def __init__(self):
        self.city_pattern = self._compile_city_pattern()
        self.date_pattern = r"(明天|后天|大后天|\d{4}年\d{1,2}月\d{1,2}日)"
        self.room_pattern = r"(大床房|双床房|套房|标准间|大床|双床)"
    
    def _compile_city_pattern(self) -> str:
        """编译城市名称正则表达式"""
        cities = "|".join(re.escape(city) for city in config.CITIES)
        return f"({cities})"
    
    def extract_entities(self, utterance: str) -> Dict[str, str]:
        """提取实体信息"""
        entities = {}
        
        try:
            # 提取出发城市
            departure_match = re.search(rf"从({self.city_pattern})", utterance)
            if departure_match:
                entities["出发城市"] = departure_match.group(2)
            
            # 提取到达城市
            destination_match = re.search(rf"到({self.city_pattern})", utterance)
            if destination_match:
                entities["到达城市"] = destination_match.group(2)
                self._check_hotel_context(entities["到达城市"], utterance, entities)
            
            # 提取飞行目的地
            fly_destination_match = re.search(rf"飞({self.city_pattern})", utterance)
            if fly_destination_match:
                entities["到达城市"] = fly_destination_match.group(2)
                self._check_hotel_context(entities["到达城市"], utterance, entities)
            
            # 提取酒店城市（直接模式）
            hotel_city_match = re.search(rf"在({self.city_pattern})住", utterance)
            if hotel_city_match:
                entities["酒店城市"] = hotel_city_match.group(2)
            
            # 提取日期
            date_match = re.search(self.date_pattern, utterance)
            if date_match:
                date_value = date_match.group(1)
                entities["出发日期"] = date_value
                if "住" in utterance:
                    entities["入住日期"] = date_value
            
            # 提取房型
            room_match = re.search(self.room_pattern, utterance)
            if room_match:
                room_type = room_match.group(1)
                if room_type in ["大床", "双床"]:
                    room_type += "房"
                entities["房型"] = room_type
            
            logger.debug(f"Extracted entities: {entities}")
            return entities
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return {}
    
    def _check_hotel_context(self, city: str, utterance: str, entities: Dict[str, str]):
        """检查酒店上下文"""
        if re.search(rf"(到|飞){city}.*住", utterance):
            entities["酒店城市"] = city
    
    def generate_bio_tags(self, utterance: str, entities: Dict[str, str]) -> List[Tuple[str, str]]:
        """生成BIO标签"""
        tags = ["O"] * len(utterance)
        
        # 实体优先级
        priority_order = ["出发城市", "到达城市", "出发日期", "入住日期", "房型", "酒店城市"]
        
        for entity_type in priority_order:
            if entity_type in entities:
                entity_value = entities[entity_type]
                start_pos = utterance.find(entity_value)
                if start_pos != -1:
                    end_pos = start_pos + len(entity_value)
                    if tags[start_pos] == "O":
                        tags[start_pos] = f"B-{entity_type}"
                        for i in range(start_pos + 1, end_pos):
                            if tags[i] == "O":
                                tags[i] = f"I-{entity_type}"
        
        return [(utterance[i], tags[i]) for i in range(len(utterance))]