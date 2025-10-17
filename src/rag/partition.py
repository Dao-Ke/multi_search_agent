from typing import Dict, List, Optional


def build_partition_filters(province: Optional[str]) -> List[Dict]:
    """
    构建动态划分知识库的过滤器定义。

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


__all__ = ["build_partition_filters"]