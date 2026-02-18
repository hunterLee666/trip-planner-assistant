"""LLM服务模块

基于LangChain的LLM服务
"""

from langchain_openai import ChatOpenAI
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# 全局LLM实例
_llm_instance = None


def get_llm():
    """获取LLM实例(单例模式)

    Returns:
        ChatOpenAI实例
    """
    global _llm_instance

    if _llm_instance is None:
        settings = get_settings()

        llm_config = settings.get_llm_config()

        _llm_instance = ChatOpenAI(
            api_key=llm_config["api_key"],
            base_url=llm_config["base_url"],
            model=llm_config["model"],
            temperature=settings.openai_temperature,
        )

        logger.info(
            "llm_initialized",
            model=llm_config["model"],
            base_url=llm_config["base_url"]
        )

    return _llm_instance


def reset_llm():
    """重置LLM实例(用于测试或重新配置)"""
    global _llm_instance
    _llm_instance = None
    logger.info("llm_reset")
