"""
总结服务类：用户提问，搜索参考资料，将提问和参考资料提交给模型，让模型总结回复。

RAG 层负责两件事：
1. 将检索结果格式化为带编号的可引用证据；
2. 在没有任何证据时提前拒答，避免模型脱离知识库自由发挥。
"""
from typing import Dict, Optional

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from model.factory import chat_model
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from utils.rag_formatting import NO_EVIDENCE_RESPONSE, format_rag_context


def print_prompt(prompt):
    print("="*20)
    print(prompt.to_string())
    print("="*20)
    return prompt


class RagSummarizeService(object):
    def __init__(self, scene_config: Optional[Dict] = None):
        """
        RAG总结服务初始化
        :param scene_config: 场景配置（来自 scenes.yml），不传则使用原有配置（向后兼容）
        """
        # 1. 按场景初始化向量库
        self.vector_store = VectorStoreService(scene_config=scene_config)
        self.retriever = self.vector_store.get_retriever()

        # 2. 按场景加载RAG Prompt
        scene_name = scene_config.get("id") if scene_config else None
        self.prompt_text = load_rag_prompts(scene_name=scene_name)
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)

        # 3. 初始化模型和链
        self.model = chat_model
        self.chain = self._init_chain()

    def _init_chain(self):
        chain = self.prompt_template | print_prompt | self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str) -> list[Document]:
        return self.retriever.invoke(query)

    def rag_summarize(self, query: str) -> str:
        context_docs = self.retriever_docs(query)
        context = format_rag_context(context_docs)

        if not context:
            return NO_EVIDENCE_RESPONSE

        return self.chain.invoke(
            {
                "input": query,
                "context": context,
                "no_evidence_response": NO_EVIDENCE_RESPONSE,
            }
        )


if __name__ == '__main__':
    # 测试：向后兼容（不传场景配置）
    rag = RagSummarizeService()
    print(rag.rag_summarize("小户型适合哪些扫地机器人"))
