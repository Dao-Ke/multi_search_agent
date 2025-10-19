from typing import Dict, List, Optional
import os
import json
from src.geo.region import REGION_PATTERNS
from src.config import CHROMA_PERSIST_DIR


def _load_provinces_from_registry() -> List[str]:
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", CHROMA_PERSIST_DIR)
    path = os.path.join(persist_dir, "kb_registry.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            provs = [p for p in data.get("provinces", []) if isinstance(p, str) and p]
            if provs:
                return provs
    except Exception:
        pass
    return list(REGION_PATTERNS.keys())


def build_partition_filters(province: Optional[str]) -> List[Dict]:
    """
    构建动态划分知识库的过滤器定义（原始版本）。

    规则：
    - 若有省份：分三组
      1) 核心文档：{"kb_type": "core"}
      2) 目标地域文档：{"province": <省份>}
      3) 余下地域文档：{"kb_type": "regional"}，并在查询后排除同省份结果
    - 若省份为 None：分两组
      1) 核心文档：{"kb_type": "core"}
      2) 余下文档：{"kb_type": "regional"}

    返回值为列表，每项包含：
    - name: 组名
    - where: Chroma 的 where 过滤条件（简单相等匹配）
    - exclude_province: 可选，用于第三组在查询结果中排除该省份（Chroma 不支持直接取反）
    """
    if province:
        return [
            {"name": "core", "where": {"kb_type": "core"}},
            {"name": "target_region", "where": {"province": province}},
            {"name": "other_regions", "where": {"kb_type": "regional"}, "exclude_province": province},
        ]
    else:
        return [
            {"name": "core", "where": {"kb_type": "core"}},
            {"name": "others", "where": {"kb_type": "regional"}},
        ]


def build_partition_filters_precise(province: Optional[str]) -> List[Dict]:
    """
    精确版过滤器构造：第三组直接用元数据过滤排除目标省份，避免“先取topK再后置过滤”。

    规则：
    - 若有省份：分三组
      1) 核心文档：{"kb_type": "core"}
      2) 目标地域文档：{"province": <省份>}
      3) 其他地域文档：{"$and": [{"kb_type": "regional"}, {"province": {"$in": 可穷举地域且不含目标省份}}]}
    - 若省份为 None：分两组（与原版一致）
    """
    provinces_all = _load_provinces_from_registry()
    if province and province in provinces_all:
        provinces_others = [p for p in provinces_all if p != province]
        return [
            {"name": "core", "where": {"kb_type": "core"}},
            {"name": "target_region", "where": {"province": province}},
            {"name": "other_regions", "where": {"$and": [{"kb_type": "regional"}, {"province": {"$in": provinces_others}}]}},
        ]
    elif province:
        # 识别到的省份不在枚举/注册集，退化为不使用 $in，仅排除目标（兼容性）
        return [
            {"name": "core", "where": {"kb_type": "core"}},
            {"name": "target_region", "where": {"province": province}},
            {"name": "other_regions", "where": {"$and": [{"kb_type": "regional"}, {"province": {"$ne": province}}]}},
        ]
    else:
        return [
            {"name": "core", "where": {"kb_type": "core"}},
            {"name": "others", "where": {"kb_type": "regional"}},
        ]

__all__ = ["build_partition_filters", "build_partition_filters_precise"]