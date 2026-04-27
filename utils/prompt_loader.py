from utils.config_handler import prompts_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger
from typing import Optional


def load_system_prompts(scene_name: Optional[str] = None):
    """
    加载系统提示词
    :param scene_name: 场景名称（如 "zhisaotong"、"ecommerce"、"hr"），不传则加载默认主Prompt
    :return: 提示词内容
    """
    try:
        if scene_name:
            # 场景Prompt路径规则：在配置的主Prompt目录下，按场景名命名
            # 例如：prompts/zhisaotong.txt, prompts/ecommerce.txt
            main_prompt_dir = get_abs_path(prompts_conf.get("main_prompt_dir", "prompts"))
            system_prompt_path = f"{main_prompt_dir}/{scene_name}.txt"
        else:
            # 向后兼容：加载原单个主Prompt
            system_prompt_path = get_abs_path(prompts_conf["main_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_system_prompts]在yaml配置项中缺少必要配置")
        raise e

    try:
        return open(system_prompt_path, "r", encoding="utf-8").read()
    except FileNotFoundError:
        logger.error(f"[load_system_prompts]场景Prompt文件不存在：{system_prompt_path}")
        raise FileNotFoundError(f"场景 {scene_name} 的Prompt文件不存在")
    except Exception as e:
        logger.error(f"[load_system_prompts]解析系统提示词出错，{str(e)}")
        raise e


def load_rag_prompts(scene_name: Optional[str] = None):
    """
    加载RAG总结提示词（支持多场景）
    """
    try:
        if scene_name:
            main_prompt_dir = get_abs_path(prompts_conf.get("main_prompt_dir", "prompts"))
            rag_prompt_path = f"{main_prompt_dir}/{scene_name}_rag.txt"
        else:
            rag_prompt_path = get_abs_path(prompts_conf["rag_summarize_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_rag_prompts]在yaml配置项中缺少必要配置")
        raise e

    try:
        return open(rag_prompt_path, "r", encoding="utf-8").read()
    except FileNotFoundError:
        logger.error(f"[load_rag_prompts]场景RAG Prompt文件不存在：{rag_prompt_path}")
        raise FileNotFoundError(f"场景 {scene_name} 的RAG Prompt文件不存在")
    except Exception as e:
        logger.error(f"[load_rag_prompts]解析RAG总结提示词出错，{str(e)}")
        raise e


def load_report_prompts(scene_name: Optional[str] = None):
    """
    加载报告生成提示词（支持多场景）
    """
    try:
        if scene_name:
            main_prompt_dir = get_abs_path(prompts_conf.get("main_prompt_dir", "prompts"))
            report_prompt_path = f"{main_prompt_dir}/{scene_name}_report.txt"
        else:
            report_prompt_path = get_abs_path(prompts_conf["report_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_report_prompts]在yaml配置项中缺少必要配置")
        raise e

    try:
        return open(report_prompt_path, "r", encoding="utf-8").read()
    except FileNotFoundError:
        logger.error(f"[load_report_prompts]场景报告Prompt文件不存在：{report_prompt_path}")
        raise FileNotFoundError(f"场景 {scene_name} 的报告Prompt文件不存在")
    except Exception as e:
        logger.error(f"[load_report_prompts]解析报告生成提示词出错，{str(e)}")
        raise e


if __name__ == '__main__':
    print("默认Prompt：", load_system_prompts()[:50])
