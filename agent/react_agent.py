from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import (rag_summarize, get_weather, get_user_location, get_user_id,
                                     get_current_month, fetch_external_data, fill_context_for_report)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch
from dotenv import load_dotenv
from rag.vector_store import VectorStoreService
from rag.rag_service import RagSummarizeService
from typing import Optional, Dict, List
import time  
load_dotenv()

ALL_TOOLS = {
    "rag_summarize": rag_summarize,
    "get_weather": get_weather,
    "get_user_location": get_user_location,
    "get_user_id": get_user_id,
    "get_current_month": get_current_month,
    "fetch_external_data": fetch_external_data,
    "fill_context_for_report": fill_context_for_report,
}

class ReactAgent:
    def __init__(self, scene_config: Optional[Dict] = None):
        """
        多场景Agent初始化
        :param scene_config: 场景配置（来自 scenes.yml），不传则使用原有配置（向后兼容）
        """
        self.scene_config = scene_config
        self.vs = VectorStoreService(scene_config=scene_config)
        self.rag_service = RagSummarizeService(scene_config=scene_config)

        scene_name = scene_config.get("id") if scene_config else None
        system_prompt = load_system_prompts(scene_name=scene_name)

        if scene_config and "tools" in scene_config:
            tools = [ALL_TOOLS[tool_name] for tool_name in scene_config["tools"] if tool_name in ALL_TOOLS]
        else:
            tools = [rag_summarize, get_weather, get_user_location, get_user_id,
                   get_current_month, fetch_external_data, fill_context_for_report]
        
        self.agent = create_agent(
            model=chat_model,
            system_prompt=system_prompt,
            tools=tools,
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    def execute_stream(self, query: str):
        input_dict = {"messages": [{"role": "user", "content": query}]}
        scene_name = self.scene_config.get("id") if self.scene_config else None

        result = self.agent.invoke(
            input_dict,
            context={"report": False, "scene_name": scene_name}
        )

        full_response = ""
        if "messages" in result:
            last_msg = result["messages"][-1]
            if hasattr(last_msg, "content"):
                full_response = last_msg.content or ""
            elif isinstance(last_msg, dict):
                full_response = last_msg.get("content", "")
        else:
            full_response = str(result)
        
        for i in range(0, len(full_response), 1):
            yield full_response[i]
            time.sleep(0.03)  # 控制速度，可调

    def reload_knowledge_base(self):
        self.vs.load_document()
        print("✅ 全量知识库已重新加载")
    def upload_single_file(self, file_path: str):
        return self.vs.load_single_document(file_path)


if __name__ == '__main__':
    agent = ReactAgent()

    for chunk in agent.execute_stream("给我生成我的使用报告"):
        print(chunk, end="", flush=True)
