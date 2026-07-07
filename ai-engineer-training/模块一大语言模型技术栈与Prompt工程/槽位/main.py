# main.py - 统一入口文件
import logging
import sys
from typing import Optional
from dialog_manager import DialogManager
from config import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dialog_system.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class DialogSystem:
    """对话系统主类"""
    
    def __init__(self, session_id: Optional[str] = None):
        self.dialog_manager = DialogManager(session_id)
        logger.info(f"Initialized DialogSystem with session: {session_id}")
    
    def process_input(self, user_input: str) -> dict:
        """处理用户输入"""
        return self.dialog_manager.process_user_input(user_input)
    
    def reset(self):
        """重置系统状态"""
        self.dialog_manager.reset()
        logger.info("Reset DialogSystem")
    
    def get_state(self) -> dict:
        """获取当前状态"""
        return self.dialog_manager.workflow.get_state_summary()

def interactive_test():
    """交互式测试"""
    system = DialogSystem()
    
    print("🤖 智能预订助手 - 优化版")
    print("=" * 50)
    print("💡 新特性：")
    print("   • 统一的配置管理")
    print("   • 完善的错误处理")
    print("   • 详细的日志记录")
    print("   • 更好的代码结构")
    print("=" * 50)
    print("💡 请描述您的出行需求，或输入 'quit' 退出")
    print("-" * 50)
    
    while True:
        try:
            user_input = input("\n👤 您: ").strip()
            if user_input.lower() in ['quit', 'exit', '退出']:
                print("👋 感谢使用，再见！")
                break
            
            if user_input:
                print()
                result = system.process_input(user_input)
                
                # 格式化输出
                print(f"📍 {result.get('workflow_description', '')}")
                print(f"💬 {result.get('message', '')}")
                
                if 'question' in result:
                    print(f"❓ {result['question']}")
                
                if 'booking_summary' in result:
                    print("\n📋 预订摘要：")
                    print("=" * 30)
                    
                    if 'flight' in result['booking_summary']:
                        flight = result['booking_summary']['flight']
                        print("✈️ 航班信息：")
                        print(f"   出发城市：{flight.get('departure_city', '')}")
                        print(f"   目标城市：{flight.get('destination_city', '')}")
                        print(f"   出发日期：{flight.get('departure_date', '')}")
                    
                    if 'hotel' in result['booking_summary']:
                        hotel = result['booking_summary']['hotel']
                        print("🏨 酒店信息：")
                        print(f"   酒店城市：{hotel.get('city', '')}")
                        print(f"   入住日期：{hotel.get('checkin_date', '')}")
                        if 'room_type' in hotel:
                            print(f"   房型：{hotel['room_type']}")
                    
                    print("=" * 30)
                    print("✅ 可以开始预订流程！")
                
                print("-" * 50)
                
        except KeyboardInterrupt:
            print("\n👋 程序被中断，再见！")
            break
        except Exception as e:
            logger.error(f"Error in interactive test: {e}")
            print(f"❌ 发生错误：{e}")

def single_test():
    """单次测试"""
    system = DialogSystem()
    test_input = "我想明天从北京飞上海，然后在上海住一晚，要个大床房"
    
    print("🤖 单次测试")
    print("=" * 30)
    print(f"🗣️ 用户说：{test_input}")
    print("🤖 系统响应：")
    
    result = system.process_input(test_input)
    print(f"状态：{result.get('status', '')}")
    print(f"消息：{result.get('message', '')}")
    
    if 'booking_summary' in result:
        print("\n📋 预订摘要：")
        for category, info in result['booking_summary'].items():
            print(f"{category}: {info}")

def run_demo():
    """运行演示"""
    system = DialogSystem()
    
    test_scenarios = [
        {
            "description": "📋 场景1：完整流程演示",
            "inputs": [
                "我想明天从北京飞上海，然后在上海住一晚，要个大床房",
                "是",  # 确认城市
            ]
        },
        {
            "description": "📋 场景2：城市确认被拒绝的情况",
            "inputs": [
                "我要从广州飞深圳",
                "不是",  # 拒绝城市
                "我要飞到杭州",  # 重新提供城市
                "确认",  # 确认新城市
            ]
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{scenario['description']}")
        print("-" * 50)
        
        # 重置系统状态
        system.reset()
        
        for j, user_input in enumerate(scenario['inputs'], 1):
            print(f"\n👤 用户输入 {j}: {user_input}")
            print("🤖 系统响应:")
            
            result = system.process_input(user_input)
            print(f"状态：{result.get('status', '')}")
            print(f"消息：{result.get('message', '')}")
            
            if 'question' in result:
                print(f"问题：{result['question']}")
            
            if j < len(scenario['inputs']):
                print("\n" + "─" * 30)
        
        print("\n" + "=" * 50)
        
        if i < len(test_scenarios):
            input("\n按回车键继续下一个场景...")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='智能预订助手')
    parser.add_argument('--mode', choices=['interactive', 'single', 'demo'], 
                       default='interactive', help='运行模式')
    parser.add_argument('--session-id', type=str, help='会话ID')
    
    args = parser.parse_args()
    
    if args.mode == 'interactive':
        interactive_test()
    elif args.mode == 'single':
        single_test()
    elif args.mode == 'demo':
        run_demo()