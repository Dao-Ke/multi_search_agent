# 最简单查询（RAG Pipeline）使用说明

本文档介绍如何使用最小的 RAG 查询管线：输入问题，从本地 Chroma 知识库检索最相关切片，并返回文本与元数据。

## 功能概览

- 模块：`src/rag/simple.py`
- 方法：`simple_query(question: str, top_k: int = 4, where: Optional[Dict] = None) -> List[Dict]`
- 返回字段：`text`、`source_name`、`kb_type`、`province`、`chunk_id`、`distance`、`id`
- 嵌入器选择：自动根据环境变量选择通义或本地哈希嵌入（与数据初始化一致）

## 前置条件

- 请先完成数据初始化，参考 `doc/data_init.md`，确保 `knowledge_base` 集合已建立并有数据。
- `.env` 中可配置：
  - `CHROMA_PERSIST_DIR`（默认 `.chroma`）
  - `TEST_MODE`（`true/1` 时使用本地哈希嵌入）
  - `TONGYI_API_KEY` 或 `DASHSCOPE_API_KEY`（启用通义嵌入）

## 命令行使用

```
source .venv/bin/activate && python -m src.rag.simple --q "你的问题" -k 4
```

- 可选筛选：
  - `--kb-type core|regional`
  - `--province 省份名`

示例：
```
python -m src.rag.simple --q "集中采购中心成立五周年有什么成效" -k 3
```

输出为 JSON 列表，包括文本与元数据，例如：
```
[
  {
    "id": "【河南】三门峡市政府集中采购中心成立五周年 成效斐然::0",
    "distance": 0.12,
    "text": "……",
    "kb_type": "regional",
    "province": "河南",
    "source_name": "【河南】三门峡市政府集中采购中心成立五周年 成效斐然",
    "chunk_id": 0
  }
]
```

## Python 使用

```
from src.rag.simple import simple_query

results = simple_query("你的问题", top_k=4)
for r in results:
    print(r["source_name"], r["distance"])  # 访问元数据
```

## 注意事项

- 若无筛选条件，请不要传空字典到 `where`；内部已处理为空时传 `None`。
- `id` 为 `source_name::chunk_id` 的组合，用于简单标识；如需更稳定的主键，可扩展写入阶段的 ID 策略。
- 运行前保证数据已初始化，否则查询结果为空。