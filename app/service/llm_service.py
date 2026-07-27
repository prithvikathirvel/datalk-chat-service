from langchain.messages import HumanMessage
from langchain_core.messages import BaseMessage
from app.core.logging import logger
from app.langraph.utils.models import llm_models
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class LLMRegistry:
    @classmethod
    def get_model(cls, model_name):
        for model in llm_models:
            if model["name"] == model_name:
                return model["llm"]
        logger.error(f"Model {model_name} not found in registry.")
        return None

    @classmethod
    def get_all_models(cls):
        return [{"name": model["name"], "provider": model["provider"]} for model in llm_models]


class LLMService:
    def __init__(self, model_name):
        self.llm = LLMRegistry.get_model(model_name)
        if not self.llm:
            raise ValueError(f"Model {model_name} not found in registry.")

    def get_llm(self, structured: bool = True, output_schema=None, include_raw: bool = False):
        if structured:
            return self.llm.with_structured_output(output_schema, include_raw=include_raw)
        return self.llm

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def ainvoke(self, llm_runnable, messages: list[BaseMessage]):
        try:
            if not isinstance(messages, list):
                messages = [HumanMessage(content=messages)]
            response = await llm_runnable.ainvoke(messages)
            logger.info(f"Model response received")
            return response
        except Exception as e:
            logger.error(f"Error invoking model: {e}")
            raise

    def invoke(self, messages: list[BaseMessage]):
        try:
            if not isinstance(messages, list):
                messages = [HumanMessage(content=messages)]
            response = self.llm.invoke(messages)
            logger.info(f"Model response: {response}")
            return response
        except Exception as e:
            logger.error(f"Error invoking model: {e}")
            raise

