import re

# 简单的敏感词与恶意注入黑名单库
SENSITIVE_WORDS = [
    "忽略之前的指令", "ignore previous", "系统提示词", "system prompt",
    "黄", "赌", "毒", "政治", "反动"  # 实际项目中应接入更完善的词库或第三方 API
]

# 非面试相关的恶意越界词（如果用户试图让 AI 帮写代码或干私活）
OFF_TOPIC_PATTERNS = [
    r"(帮我|给我).*(写|做).*(代码|作业|论文|请假条)",
    r"(今天|明天).*(天气|新闻|股票)",
    r"(推荐|分享).*(电影|音乐|游戏)"
]

def check_input_security(text: str) -> tuple[bool, str]:
    """
    检查用户输入是否安全。
    返回: (是否安全, 提示信息)
    """
    text_lower = text.lower()
    
    # 1. 检查注入与敏感词
    for word in SENSITIVE_WORDS:
        if word.lower() in text_lower:
            return False, "您好，由于输入包含敏感词汇或违规指令，已触发安全拦截。请保持正常的面试交流。"

    # 2. 检查非面试相关的越界提问
    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, text_lower):
            return False, "抱歉，我是您的专属面试官，只能回答与当前岗位和面试相关的问题哦。我们继续面试吧。"
            
    return True, ""