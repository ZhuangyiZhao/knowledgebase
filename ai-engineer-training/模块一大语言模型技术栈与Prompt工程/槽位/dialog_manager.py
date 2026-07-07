# dialog_manager.py - 统一的对话管理器
from typing import List, Dict, Optional, Tuple
from intent_classifier import classify_intent
from entity_extractor import EntityExtractor
from slot_manager import IntentSlots
from workflow_manager import WorkflowManager, WorkflowStep
from config import config
import logging

logger = logging.getLogger(__name__)

class DialogManager:
    def __init__(self, session_id: Optional[str] = None):
        self.slots = IntentSlots()
        self.workflow = WorkflowManager(session_id)
        self.entity_extractor = EntityExtractor()
        self.pending_city_confirmation = None
        self.session_id = session_id
        
        # 步骤处理器映射
        self.step_handlers = {
            WorkflowStep.INTENT_DETECTION: self._handle_intent_detection,
            WorkflowStep.FLIGHT_INFO_COLLECTION: self._handle_flight_info_collection,
            WorkflowStep.CITY_CONFIRMATION: self._handle_city_confirmation,
            WorkflowStep.HOTEL_SELECTION: self._handle_hotel_selection,
            WorkflowStep.FINAL_CONFIRMATION: self._handle_final_confirmation,
            WorkflowStep.COMPLETED: self._handle_completed
        }
        
        logger.info(f"Initialized dialog manager for session: {session_id}")
    
    def process_user_input(self, utterance: str) -> Dict:
        """处理用户输入的主函数"""
        try:
            logger.info(f"Processing user input: {utterance}")
            
            # 获取当前步骤处理器
            current_step = self.workflow.state.current_step
            handler = self.step_handlers.get(current_step, self._handle_general_input)
            
            # 执行处理
            response = handler(utterance)
            
            # 添加系统状态信息
            response.update({
                "session_id": self.session_id,
                "current_step": current_step.value,
                "workflow_description": self.workflow.get_current_step_description(),
                "state_summary": self.workflow.get_state_summary()
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing user input: {e}")
            return {
                "status": "error",
                "message": "处理用户输入时发生错误",
                "error": str(e)
            }
    
    def _handle_intent_detection(self, utterance: str) -> Dict:
        """处理意图识别阶段"""
        intents = classify_intent(utterance)
        
        if intents and intents != ["unknown"]:
            for intent in intents:
                self.slots.activate_intent(intent)
            
            if "book_flight" in intents:
                self.workflow.advance_step(WorkflowStep.FLIGHT_INFO_COLLECTION)
                return self._handle_flight_info_collection(utterance)
            else:
                self._extract_and_fill_slots(utterance)
                return self._check_completion()
        else:
            return {
                "status": "need_clarification",
                "message": "未能识别明确意图，请重新描述您的需求"
            }
    
    def _handle_flight_info_collection(self, utterance: str) -> Dict:
        """处理航班信息收集阶段"""
        self._extract_and_fill_slots(utterance)
        
        # 检查是否有目标城市需要确认
        if self.slots.is_slot_filled("flight_destination_city"):
            destination = self.slots.get_slot_value("flight_destination_city")
            if destination and not self.workflow.can_proceed_to_hotel_selection():
                self.pending_city_confirmation = destination
                self.workflow.advance_step(WorkflowStep.CITY_CONFIRMATION)
                return {
                    "status": "need_confirmation",
                    "message": f"检测到目标城市：{destination}",
                    "question": f"请确认您要前往 {destination} 吗？(回答：是/确认/对 或 否/不是)"
                }
        
        return self._check_flight_completion()
    
    def _handle_city_confirmation(self, utterance: str) -> Dict:
        """处理城市确认阶段"""
        user_response = utterance.strip().lower()
        
        if self._is_confirmation_response(user_response):
            if self.pending_city_confirmation:
                success = self.workflow.confirm_destination_city(self.pending_city_confirmation)
                if success:
                    # 自动设置酒店城市
                    if "book_hotel" in self.slots.active_intents:
                        self.slots.update_slot("hotel_city", self.pending_city_confirmation)
                    
                    self.pending_city_confirmation = None
                    
                    if "book_hotel" in self.slots.active_intents:
                        self.workflow.advance_step(WorkflowStep.HOTEL_SELECTION)
                        return self._handle_hotel_selection(utterance)
                    else:
                        return self._check_completion()
            
        elif self._is_rejection_response(user_response):
            self.slots.update_slot("flight_destination_city", "", confidence=0.0)
            self.pending_city_confirmation = None
            self.workflow.advance_step(WorkflowStep.FLIGHT_INFO_COLLECTION)
            return {
                "status": "need_info",
                "message": "城市信息有误，请重新提供正确的目标城市",
                "question": "请问您要飞往哪个城市？"
            }
        
        else:
            return {
                "status": "need_clarification",
                "message": "请明确回答：是否确认目标城市？(回答：是/确认 或 否/不是)"
            }
    
    def _handle_hotel_selection(self, utterance: str) -> Dict:
        """处理酒店选择阶段"""
        if not self.workflow.can_proceed_to_hotel_selection():
            return {
                "status": "error",
                "message": "请先确认目标城市，然后才能选择酒店"
            }
        
        self._extract_and_fill_slots(utterance)
        
        # 自动设置酒店城市
        if (self.workflow.state.confirmed_cities and 
            not self.slots.is_slot_filled("hotel_city")):
            confirmed_city = self.workflow.state.confirmed_cities[-1]
            self.slots.update_slot("hotel_city", confirmed_city)
        
        return self._check_hotel_completion()
    
    def _handle_final_confirmation(self, utterance: str) -> Dict:
        """处理最终确认阶段"""
        if self._is_confirmation_response(utterance):
            self.workflow.advance_step(WorkflowStep.COMPLETED)
            return self._handle_completed(utterance)
        else:
            return {
                "status": "need_clarification",
                "message": "请确认是否要执行预订？"
            }
    
    def _handle_completed(self, utterance: str) -> Dict:
        """处理完成状态"""
        return {
            "status": "completed",
            "message": "所有必填信息已收集完成！",
            "booking_summary": self._generate_booking_summary()
        }
    
    def _handle_general_input(self, utterance: str) -> Dict:
        """处理一般输入"""
        self._extract_and_fill_slots(utterance)
        return self._check_completion()
    
    def _extract_and_fill_slots(self, utterance: str):
        """提取并填充槽位"""
        entities = self.entity_extractor.extract_entities(utterance)
        
        # 填充槽位
        for entity_type, value in entities.items():
            slot_name = config.SLOT_MAPPING.get(entity_type)
            if slot_name:
                self.slots.update_slot(slot_name, value)
        
        # 智能推断逻辑
        if "到达城市" in entities and "住" in utterance:
            if self.workflow.can_proceed_to_hotel_selection():
                self.slots.update_slot("hotel_city", entities["到达城市"])
        
        if "出发日期" in entities and "住" in utterance:
            self.slots.update_slot("hotel_checkin_date", entities["出发日期"])
    
    def _check_completion(self) -> Dict:
        """检查整体完成情况"""
        if self.slots.is_complete():
            self.workflow.advance_step(WorkflowStep.FINAL_CONFIRMATION)
            return {
                "status": "ready_for_confirmation",
                "message": "所有必填信息已收集完成！",
                "booking_summary": self._generate_booking_summary()
            }
        else:
            missing = self.slots.get_missing_slots()
            next_question = self._get_next_question(missing)
            return {
                "status": "need_info",
                "message": f"还需要补充信息：{missing}",
                "question": next_question
            }
    
    def _check_flight_completion(self) -> Dict:
        """检查航班信息是否完整"""
        missing_flight_slots = self._get_missing_slots_by_prefix("flight_")
        
        if missing_flight_slots:
            next_question = self._get_next_question(missing_flight_slots)
            return {
                "status": "need_info",
                "message": f"航班信息不完整，缺少：{missing_flight_slots}",
                "question": next_question
            }
        else:
            if "book_hotel" in self.slots.active_intents:
                if self.workflow.can_proceed_to_hotel_selection():
                    self.workflow.advance_step(WorkflowStep.HOTEL_SELECTION)
                    return self._handle_hotel_selection("")
            return self._check_completion()
    
    def _check_hotel_completion(self) -> Dict:
        """检查酒店信息是否完整"""
        missing_hotel_slots = self._get_missing_slots_by_prefix("hotel_")
        
        if missing_hotel_slots:
            next_question = self._get_next_question(missing_hotel_slots)
            return {
                "status": "need_info",
                "message": f"酒店信息不完整，缺少：{missing_hotel_slots}",
                "question": next_question
            }
        else:
            return self._check_completion()
    
    def _get_missing_slots_by_prefix(self, prefix: str) -> List[str]:
        """根据前缀获取缺失的槽位"""
        return [name for name, slot in self.slots._slots.items() 
                if name.startswith(prefix) and slot.required and not slot.filled]
    
    def _get_next_question(self, missing_slots: List[str]) -> str:
        """获取下一个问题"""
        if missing_slots:
            return config.PROMPT_TEMPLATES.get(missing_slots[0], "请补充更多信息。")
        return ""
    
    def _is_confirmation_response(self, response: str) -> bool:
        """检查是否为确认响应"""
        return any(keyword in response for keyword in config.CONFIRMATION_KEYWORDS["confirmation"])
    
    def _is_rejection_response(self, response: str) -> bool:
        """检查是否为拒绝响应"""
        return any(keyword in response for keyword in config.CONFIRMATION_KEYWORDS["rejection"])
    
    def _generate_booking_summary(self) -> Dict:
        """生成预订摘要"""
        summary = {}
        
        if "book_flight" in self.slots.active_intents:
            summary["flight"] = {
                "departure_city": self.slots.get_slot_value("flight_departure_city"),
                "destination_city": self.slots.get_slot_value("flight_destination_city"),
                "departure_date": self.slots.get_slot_value("flight_departure_date")
            }
        
        if "book_hotel" in self.slots.active_intents:
            summary["hotel"] = {
                "city": self.slots.get_slot_value("hotel_city"),
                "checkin_date": self.slots.get_slot_value("hotel_checkin_date")
            }
            
            if self.slots.is_slot_filled("hotel_room_type"):
                summary["hotel"]["room_type"] = self.slots.get_slot_value("hotel_room_type")
        
        return summary
    
    def reset(self):
        """重置对话状态"""
        self.slots.clear()
        self.workflow.reset()
        self.pending_city_confirmation = None
        logger.info("Reset dialog manager state")