# intent_classifier.py - 优化后的意图分类器
import re
from typing import List, Dict, Tuple
from config import config
import logging

logger = logging.getLogger(__name__)

class IntentClassifier:
    def __init__(self):
        self.intent_patterns = config.INTENT_KEYWORDS
        self.compiled_patterns = self._compile_patterns()
        logger.info("Initialized IntentClassifier")
    
    def _compile_patterns(self) -> Dict[str, List[re.Pattern]]:
        """预编译正则表达式模式"""
        compiled = {}
        for intent, patterns in self.intent_patterns.items():
            compiled[intent] = [re.compile(pattern) for pattern in patterns]
        return compiled
    
    def classify_intent(self, utterance: str) -> List[str]:
        """基于关键词匹配的意图识别"""
        try:
            detected = []
            utterance_lower = utterance.lower()
            
            for intent, patterns in self.compiled_patterns.items():
                for pattern in patterns:
                    if pattern.search(utterance_lower):
                        detected.append(intent)
                        break
            
            result = detected if detected else ["unknown"]
            logger.debug(f"Classified intent for '{utterance}': {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            return ["unknown"]
    
    def get_intent_confidence(self, utterance: str) -> List[Tuple[str, float]]:
        """获取意图及其置信度"""
        try:
            utterance_lower = utterance.lower()
            intent_scores = {}
            
            for intent, patterns in self.compiled_patterns.items():
                score = 0
                for pattern in patterns:
                    if pattern.search(utterance_lower):
                        score += 1
                
                if score > 0:
                    # 归一化分数
                    confidence = score / len(patterns)
                    intent_scores[intent] = confidence
            
            # 按置信度排序
            sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
            
            if not sorted_intents:
                return [("unknown", 0.0)]
            
            logger.debug(f"Intent confidence for '{utterance}': {sorted_intents}")
            return sorted_intents
            
        except Exception as e:
            logger.error(f"Error getting intent confidence: {e}")
            return [("unknown", 0.0)]

# 全局实例
intent_classifier = IntentClassifier()

def classify_intent(utterance: str) -> List[str]:
    """兼容性函数"""
    return intent_classifier.classify_intent(utterance)
