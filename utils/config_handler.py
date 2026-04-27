"""
yaml
k: v
"""
import yaml
from utils.path_tool import get_abs_path
from typing import Dict, List, Optional


def load_rag_config(config_path: str=get_abs_path("config/rag.yml"), encoding: str="utf-8"):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def load_chroma_config(config_path: str=get_abs_path("config/chroma.yml"), encoding: str="utf-8"):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def load_prompts_config(config_path: str=get_abs_path("config/prompts.yml"), encoding: str="utf-8"):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def load_agent_config(config_path: str=get_abs_path("config/agent.yml"), encoding: str="utf-8"):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


# ===================== 新增：多场景配置加载器 =====================
def load_scenes_config(config_path: str=get_abs_path("config/scenes.yml"), encoding: str="utf-8") -> Dict:
    """
    加载多场景配置文件
    配置文件格式示例：
    scenes:
      - id: zhisaotong
        name: 智扫通客服
        description: 设备使用、故障排查智能客服
        collection_name: zhisaotong_knowledge_base
        data_path: data/zhisaotong
      - id: ecommerce
        name: 电商售后客服
        description: 订单、退换货、产品使用售后客服
        collection_name: ecommerce_knowledge_base
        data_path: data/ecommerce
    """
    try:
        with open(config_path, "r", encoding=encoding) as f:
            return yaml.load(f, Loader=yaml.FullLoader)
    except FileNotFoundError:
        # 如果场景配置文件不存在，返回默认的单场景配置（向后兼容）
        return {
            "scenes": [
                {
                    "id": "default",
                    "name": "默认场景",
                    "description": "默认智能客服场景",
                    "collection_name": load_chroma_config().get("collection_name", "default_collection"),
                    "data_path": load_chroma_config().get("data_path", "data")
                }
            ]
        }


def get_scene_by_id(scene_id: str) -> Optional[Dict]:
    """
    根据场景ID获取场景配置
    """
    scenes_config = load_scenes_config()
    for scene in scenes_config.get("scenes", []):
        if scene.get("id") == scene_id:
            return scene
    return None


def get_all_scenes() -> List[Dict]:
    """
    获取所有可用场景列表
    """
    scenes_config = load_scenes_config()
    return scenes_config.get("scenes", [])


rag_conf = load_rag_config()
chroma_conf = load_chroma_config()
prompts_conf = load_prompts_config()
agent_conf = load_agent_config()
scenes_conf = load_scenes_config()


if __name__ == '__main__':
    print("原有配置测试：", rag_conf.get("chat_model_name"))
    print("所有可用场景：", get_all_scenes())
