# workflow_manager.py - 优化后的工作流管理器
from typing import Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass, field
from config import config
import logging

logger = logging.getLogger(__name__)

class WorkflowStep(Enum):
    INTENT_DETECTION = "intent_detection"
    FLIGHT_INFO_COLLECTION = "flight_info_collection"
    CITY_CONFIRMATION = "city_confirmation"
    HOTEL_SELECTION = "hotel_selection"
    FINAL_CONFIRMATION = "final_confirmation"
    COMPLETED = "completed"

@dataclass
class WorkflowState:
    current_step: WorkflowStep = WorkflowStep.INTENT_DETECTION
    confirmed_cities: List[str] = field(default_factory=list)
    pending_confirmation: Optional[str] = None
    hotel_selection_unlocked: bool = False
    session_id: Optional[str] = None  # 新增会话ID
    
    def to_dict(self) -> Dict:
        """转换为字典格式，便于序列化"""
        return {
            "current_step": self.current_step.value,
            "confirmed_cities": self.confirmed_cities,
            "pending_confirmation": self.pending_confirmation,
            "hotel_selection_unlocked": self.hotel_selection_unlocked,
            "session_id": self.session_id
        }

class WorkflowManager:
    def __init__(self, session_id: Optional[str] = None):
        self.state = WorkflowState(session_id=session_id)
        self.step_transitions = self._define_step_transitions()
        logger.info(f"Initialized workflow manager for session: {session_id}")
    
    def _define_step_transitions(self) -> Dict[WorkflowStep, List[WorkflowStep]]:
        """定义合法的状态转换"""
        return {
            WorkflowStep.INTENT_DETECTION: [
                WorkflowStep.FLIGHT_INFO_COLLECTION,
                WorkflowStep.HOTEL_SELECTION
            ],
            WorkflowStep.FLIGHT_INFO_COLLECTION: [
                WorkflowStep.CITY_CONFIRMATION,
                WorkflowStep.FINAL_CONFIRMATION
            ],
            WorkflowStep.CITY_CONFIRMATION: [
                WorkflowStep.FLIGHT_INFO_COLLECTION,
                WorkflowStep.HOTEL_SELECTION
            ],
            WorkflowStep.HOTEL_SELECTION: [
                WorkflowStep.FINAL_CONFIRMATION
            ],
            WorkflowStep.FINAL_CONFIRMATION: [
                WorkflowStep.COMPLETED
            ]
        }
    
    def get_current_step_description(self) -> str:
        """获取当前步骤的描述"""
        return config.WORKFLOW_DESCRIPTIONS.get(
            self.state.current_step.value, 
            "未知状态"
        )
    
    def can_proceed_to_hotel_selection(self) -> bool:
        """检查是否可以进入酒店选择步骤"""
        return self.state.hotel_selection_unlocked
    
    def confirm_destination_city(self, city: str) -> bool:
        """确认目标城市，解锁酒店选择"""
        if city and city not in self.state.confirmed_cities:
            self.state.confirmed_cities.append(city)
            self.state.hotel_selection_unlocked = True
            self.advance_step(WorkflowStep.HOTEL_SELECTION)
            logger.info(f"Confirmed destination city: {city}")
            return True
        return False
    
    def advance_step(self, next_step: WorkflowStep) -> bool:
        """推进到下一步骤"""
        # 检查状态转换的合法性
        if not self._is_valid_transition(next_step):
            logger.warning(f"Invalid transition from {self.state.current_step} to {next_step}")
            return False
        
        # 特殊检查：酒店选择需要解锁
        if next_step == WorkflowStep.HOTEL_SELECTION and not self.state.hotel_selection_unlocked:
            logger.warning("Attempted to access hotel selection without unlocking")
            return False
        
        old_step = self.state.current_step
        self.state.current_step = next_step
        logger.info(f"Workflow advanced from {old_step} to {next_step}")
        return True
    
    def _is_valid_transition(self, next_step: WorkflowStep) -> bool:
        """检查状态转换是否合法"""
        valid_transitions = self.step_transitions.get(self.state.current_step, [])
        return next_step in valid_transitions
    
    def reset(self):
        """重置工作流状态"""
        old_session_id = self.state.session_id
        self.state = WorkflowState(session_id=old_session_id)
        logger.info("Reset workflow state")
    
    def get_state_summary(self) -> Dict:
        """获取状态摘要"""
        return {
            "current_step": self.state.current_step.value,
            "confirmed_cities": len(self.state.confirmed_cities),
            "hotel_unlocked": self.state.hotel_selection_unlocked,
            "has_pending_confirmation": self.state.pending_confirmation is not None
        }