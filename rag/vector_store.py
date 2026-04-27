from langchain_chroma import Chroma
from langchain_core.documents import Document
from utils.config_handler import chroma_conf, get_scene_by_id
from model.factory import embed_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.path_tool import get_abs_path
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import logger
import os
from typing import Literal, Optional, Dict

class VectorStoreService:
    def __init__(self, scene_config: Optional[Dict] = None):
        """
        向量库服务初始化
        :param scene_config: 场景配置（来自 scenes.yml），不传则使用原有 chroma_conf（向后兼容）
        """
        if scene_config:
            self.collection_name = scene_config["collection_name"]
            self.data_path = get_abs_path(scene_config["data_path"])
            self.md5_path = get_abs_path(f"{scene_config['data_path']}/.md5_store")
        else:
            self.collection_name = chroma_conf["collection_name"]
            self.data_path = get_abs_path(chroma_conf["data_path"])
            self.md5_path = get_abs_path(chroma_conf["md5_hex_store"])

        os.makedirs(self.data_path, exist_ok=True)

        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=embed_model,
            persist_directory=get_abs_path(chroma_conf["persist_directory"]),
        )

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})

    def load_document(self):
        """全量扫描文件夹加载知识库（初始化用）"""
        # MD5 校验工具函数
        def check_md5_hex(md5_for_check: str):
            if not os.path.exists(self.md5_path):
                open(self.md5_path, "w", encoding="utf-8").close()
                return False
            with open(self.md5_path, "r", encoding="utf-8") as f:
                return md5_for_check in [line.strip() for line in f.readlines()]

        def save_md5_hex(md5_for_check: str):
            with open(self.md5_path, "a", encoding="utf-8") as f:
                f.write(md5_for_check + "\n")

        def get_file_documents(read_path: str):
            if read_path.endswith(("txt", "md")):
                return txt_loader(read_path)
            if read_path.endswith("pdf"):
                return pdf_loader(read_path)
            return []

        allowed_files_path: tuple[...] = listdir_with_allowed_type( # type: ignore
            self.data_path,
            tuple(chroma_conf["allow_knowledge_file_type"]),
        )

        for path in allowed_files_path:
            md5_hex = get_file_md5_hex(path)
            if check_md5_hex(md5_hex):
                logger.info(f"[加载知识库][{self.collection_name}]{path} 已存在，跳过")
                continue
            try:
                documents = get_file_documents(path)
                if not documents:
                    logger.warning(f"[加载知识库][{self.collection_name}]{path} 无有效内容，跳过")
                    continue
                split_docs = self.spliter.split_documents(documents)
                self.vector_store.add_documents(split_docs)
                save_md5_hex(md5_hex)
                logger.info(f"[加载知识库][{self.collection_name}]{path} 加载成功")
            except Exception as e:
                logger.error(f"[加载知识库][{self.collection_name}]{path} 加载失败：{str(e)}", exc_info=True)

    def load_single_document(self, file_path: str) -> Literal["exists", "success", "failed", "empty"]:
        """
        加载单个文件（管理员上传专用）
        return: exists=已存在 | success=成功 | failed=失败 | empty=无内容
        """
        # 1. 校验MD5（复用你的去重逻辑）
        if not os.path.exists(self.md5_path):
            open(self.md5_path, "w", encoding="utf-8").close()
        with open(self.md5_path, "r", encoding="utf-8") as f:
            md5_list = [line.strip() for line in f.readlines()]
        md5_hex = get_file_md5_hex(file_path)
        if md5_hex in md5_list:
            logger.info(f"[单文件加载][{self.collection_name}]{file_path} 已存在")
            return "exists"

        # 2. 读取文件
        try:
            if file_path.endswith(("txt", "md")):
                documents = txt_loader(file_path)
            elif file_path.endswith("pdf"):
                documents = pdf_loader(file_path)
            else:
                return "failed"

            if not documents:
                logger.warning(f"[单文件加载][{self.collection_name}]{file_path} 无有效内容")
                return "empty"

            # 3. 分片+存入向量库
            split_docs = self.spliter.split_documents(documents)
            self.vector_store.add_documents(split_docs)

            # 4. 保存MD5
            with open(self.md5_path, "a", encoding="utf-8") as f:
                f.write(md5_hex + "\n")

            logger.info(f"[单文件加载][{self.collection_name}]{file_path} 加载成功")
            return "success"
        except Exception as e:
            logger.error(f"[单文件加载][{self.collection_name}]{file_path} 失败：{str(e)}", exc_info=True)
            return "failed"

if __name__ == '__main__':
    vs = VectorStoreService()
    vs.load_document()
    retriever = vs.get_retriever()
    res = retriever.invoke("迷路")
    for r in res:
        print(r.page_content)
        print("-"*20)
