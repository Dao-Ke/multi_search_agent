# 动态划分知识库的过滤器（Partition Filters）

本文档介绍如何根据问题中识别出的省份信息，动态生成知识库的分组过滤器，用于分级检索。

## 模块与方法
- 模块：`src/rag/partition.py`
- 方法：`build_partition_filters(province: Optional[str]) -> List[Dict]`

## 分组规则
- 若识别到省份（如“四川”）：分为三组
  1. 核心文档：`{"kb_type": "core"}`
  2. 目标地域文档：`{"province": "四川"}`
  3. 余下地域文档：`{"kb_type": "regional"}`，并在查询结果阶段排除同省份（字段：`exclude_province`）
- 若省份为 `None`：分为两组
  1. 核心文档：`{"kb_type": "core"}`
  2. 余下文档：`{"kb_type": "regional"}`

说明：当前 Chroma 的 where 过滤主要支持简单相等匹配，不支持直接“取反”；因此第三组通过结果后置排除目标省份来达成“其余地域”的效果。

## 使用示例（Python）
```
from src.geo.region import extract_province
from src.rag.partition import build_partition_filters

question = "政府采购支持教育高质量发展的举措在四川有哪些？"
prov = extract_province(question)  # "四川"
filters = build_partition_filters(prov)
print(filters)
# [
#   {"name": "core", "where": {"kb_type": "core"}},
#   {"name": "target_region", "where": {"province": "四川"}},
#   {"name": "other_regions", "where": {"kb_type": "regional"}, "exclude_province": "四川"}
# ]
```

## 与查询管线的衔接建议
- 每组使用 `src.rag.simple.simple_query` 执行一次检索：
  - 第一组：`where={"kb_type": "core"}`
  - 第二组：`where={"province": prov}`
  - 第三组：`where={"kb_type": "regional"}` 并在返回结果中排除 `province == prov` 的条目。
- 最终将三组结果合并，交由 LLM 进行汇总，或直接返回分组结果用于工程化拼装。

## 后续扩展建议
- 若后续引入更复杂的过滤（如多省份、逻辑组合），可在过滤器中增加表达式描述，并实现统一的后置过滤器。