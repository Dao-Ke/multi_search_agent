# 核心管线（Region → Filters → Multi-Query → LLM Summary）

本文档说明项目的主流程：从用户问题解析地域、省份，动态构建分组过滤器，按组触发多次检索，并由 LLM 汇总输出。

## 模块与入口
- 模块：`src/pipeline/core.py`
- 方法：`partition_query(question: str, top_k_per_group: int = 3, province_override: Optional[str] = None, llm_model: str = "qwen3-1.7b") -> Dict`
- 命令行：`python -m src.pipeline.core --q "你的问题" -k 3 [--province 省份] [--model qwen3-1.7b]`

## 主流程
1. 地域解析：`src.geo.region.extract_province(question)`，得到省份或 `None`。
2. 构建过滤器：`src.rag.partition.build_partition_filters(province)`。
   - 有省份 → 三组：`core`、`target_region`、`other_regions`（第三组结果排除该省份）。
   - 无省份 → 两组：`core`、`others`。
3. 分组检索：分别调用 `src.rag.simple.simple_query(question, top_k, where)` 获取每组 top-k 切片。
4. LLM 汇总：使用 DashScope 的 Qwen（默认 `qwen3-1.7b`）对多组检索结果进行汇总。
   - 无 `DASHSCOPE_API_KEY/TONGYI_API_KEY` 时降级为规则型摘要，返回检索要点拼接。
   - 非流式调用默认关闭思维链参数（`enable_thinking=False`）。

## 输出格式要求
- 总结：1–2段概括关键结论，避免凭空信息。
- 分级内容：严格按组序输出“核心组 → 地域组 → 其他地域组”（无省份时为“核心组 → 其他组”）。
  - 每组用小标题并分点列出举措/政策要点；
  - 每条结尾保留来源标记，格式为 `[组序号-切片序号]`（如 `[1-2]`）。
  - 不同组的相同要点不重复，后者注明“与前述一致”。
- 信息不足：某组无内容时写“该组未检索到相关内容”。
- 风险与建议：末尾可补充一段建议。

## 返回结构
```
{
  "question": "...",
  "province": "四川" | null,
  "groups": [
    {"name": "core", "where": {"kb_type": "core"}, "results": [...]},
    {"name": "target_region", "where": {"province": "四川"}, "results": [...]},
    {"name": "other_regions", "where": {"kb_type": "regional"}, "results": [...]}  // 若有省份
  ],
  "summary": "LLM 汇总文本或降级摘要",
  "references": [
    {"name": "core", "items": ["【中央】xxx-0", "【中央】xxx-1"]},
    {"name": "target_region", "items": ["【四川】深化政采制度改革-0"]},
    {"name": "other_regions", "items": ["【云南】优化采购流程-2"]}
  ]
}
```

## 使用示例
```
source .venv/bin/activate && \
python -m src.pipeline.core --q "政府采购支持教育高质量发展的举措在四川有哪些？" -k 3
```
- 若需覆盖省份：`--province 四川`
- 若环境已有 `DASHSCOPE_API_KEY`：将调用 Qwen 进行总结；否则使用降级摘要。

## App 集成：导出 Markdown

入口：`src/app.py`，可将问题、清洗后的总结与分组引用写入 Markdown。

示例：
```
source .venv/bin/activate && \
python src/app.py --q "四川在教育高质量发展方面的政府采购举措有哪些？" --out output/sichuan_edu.md --top-k 3
```

说明：
- `.env` 推荐设置 `DASHSCOPE_API_KEY`（或 `TONGYI_API_KEY`）以启用 LLM；未设置时自动降级为规则型摘要。
- 写入时会自动提取摘要的 JSON `content` 字段，避免在 Markdown 中出现整段 JSON。

## 环境配置
- `.env` 中可配置 `DASHSCOPE_API_KEY` 或 `TONGYI_API_KEY`。
- 模型名可通过 `--model` 指定，默认 `qwen3-1.7b`。

## 设计说明
- 过滤器第三组不直接做“取反”是因为 Chroma where 不支持逻辑取反；采用结果后置排除实现“其他地域”。
- 汇总提示中包含分组与编号，便于在回答中加入引用标记（如 `[1-2]` 表示第1组第2条切片）。

## 进一步工作
- 引入更多领域指令与模板，使汇总更结构化。
- 增加每组的 top-k 自适应策略，按分组权重调整检索数量。