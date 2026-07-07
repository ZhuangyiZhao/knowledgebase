# slot_manager.py - 优化后的槽位管理器
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from config import config
import logging

logger = logging.getLogger(__name__)

@dataclass
class Slot:
    value: Optional[str] = None
    filled: bool = False
    required: bool = True
    confidence: float = 1.0  # 新增置信度字段

class IntentSlots:
    def __init__(self):
        # 使用动态槽位管理，避免硬编码
        self._slots: Dict[str, Slot] = {}
        self.active_intents: Set[str] = set()
        self._initialize_default_slots()
    
    def _initialize_default_slots(self):
        """初始化默认槽位"""
        default_slots = {
            "flight_departure_city": Slot(required=True),
            "flight_destination_city": Slot(required=True),
            "flight_departure_date": Slot(required=True),
            "hotel_city": Slot(required=True),
            "hotel_checkin_date": Slot(required=True),
            "hotel_room_type": Slot(required=False)
        }
        self._slots.update(default_slots)
    
    def get_missing_slots(self) -> List[str]:
        """返回当前所有未填满的必填槽位（根据激活的意图）"""
        missing = []
        intent_prefixes = {
            "book_flight": "flight_",
            "book_hotel": "hotel_"
        }
        
        for intent in self.active_intents:
            prefix = intent_prefixes.get(intent)
            if prefix:
                for name, slot in self._slots.items():
                    if name.startswith(prefix) and slot.required and not slot.filled:
                        missing.append(name)
        
        logger.debug(f"Missing slots: {missing}")
        return missing
    
    def is_complete(self) -> bool:
        """检查所有激活意图的必填槽位是否都已填完"""
        return len(self.get_missing_slots()) == 0
    
    def update_slot(self, slot_name: str, value: str, confidence: float = 1.0):
        """更新槽位值并标记为已填"""
        try:
            if slot_name in self._slots:
                self._slots[slot_name].value = value
                self._slots[slot_name].filled = True
                self._slots[slot_name].confidence = confidence
                logger.info(f"Updated slot {slot_name} with value: {value}")
            else:
                # 动态添加非预定义槽位
                self._slots[slot_name] = Slot(value=value, filled=True, required=False, confidence=confidence)
                logger.info(f"Created new slot {slot_name} with value: {value}")
        except Exception as e:
            logger.error(f"Error updating slot {slot_name}: {e}")
            raise
    
    def activate_intent(self, intent: str):
        """激活某个意图"""
        self.active_intents.add(intent)
        logger.info(f"Activated intent: {intent}")
    
    def clear(self):
        """重置所有槽位和意图"""
        for slot in self._slots.values():
            slot.value = None
            slot.filled = False
            slot.confidence = 1.0
        self.active_intents.clear()
        logger.info("Cleared all slots and intents")
    
    def get_slot_value(self, slot_name: str) -> Optional[str]:
        """获取槽位值"""
        return self._slots.get(slot_name, Slot()).value
    
    def is_slot_filled(self, slot_name: str) -> bool:
        """检查槽位是否已填"""
        return self._slots.get(slot_name, Slot()).filled
    
    def __getattr__(self, name):
        """支持属性访问槽位"""
        if name in self._slots:
            return self._slots[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
