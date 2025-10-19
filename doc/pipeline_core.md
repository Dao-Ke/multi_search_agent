# 核心管线（Region → Filters → Multi-Query → LLM Summary）

本文档说明项目的主流程：从用户问题解析地域、省份，动态构建分组过滤器，按组触发多次检索，并由 LLM 汇总输出。

## 模块与入口
- 模块：`src/pipeline/chain.py`
- 方法：`build_app_chain() -> Runnable`
- 命令行：`python src/app.py --q "你的问题" -k 3 [--province 省份]`


## 主流程
1. 地域解析：`src.geo.region.extract_province(question)`，得到省份或 `None`。
2. 构建过滤器：`src.rag.partition.build_partition_filters_precise(province)`。
   - 有省份 → 三组：`core`、`target_region`、`other_regions`（第三组结果排除该省份）。
   - 无省份 → 两组：`core`、`others`。
3. 分组检索：分别调用 `src.rag.simple.simple_query(question, top_k, where)` 获取每组 top-k 切片。
4. LLM 汇总：使用本地 Ollama 的 Qwen（默认 `qwen3:0.6b`，`format="json"`，`temperature=0`）对多组检索结果进行汇总；无法解析为结构化 JSON 时自动降级为规则型摘要并补齐分组要点。

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
  "summary": "LLM 汇总文本或降级摘要",
  "references": [
    {"name": "core", "items": ["【中央】xxx-0", "【中央】xxx-1"]},
    {"name": "target_region", "items": ["【四川】深化政采制度-0"]},
    {"name": "other_regions", "items": ["【云南】优化采购流程-2"]}
  ]
}
```

## 使用示例
```
source .venv/bin/activate && \
python src/app.py --q "政府采购支持教育高质量发展的举措在四川有哪些？" --out output/sichuan_edu.md -k 3
```
- 若需覆盖省份：`--province 四川`
- `.env` 可选设置：`OLLAMA_BASE_URL`（如 `http://localhost:11434`）。本地未启动或未拉取模型时自动降级为规则型摘要。

## 环境配置
- `.env` 中可配置 `CHROMA_PERSIST_DIR`（默认 `.chroma`）。
- `.env` 可选配置：`OLLAMA_BASE_URL`（如 `http://localhost:11434`），并确保已本地拉取所需模型（例如：`ollama pull qwen3:0.6b`）。

## 设计说明
- 过滤器第三组不直接做“取反”是因为 Chroma where 不支持逻辑取反；采用结果后置排除实现“其他地域”。
- 汇总提示中包含分组与编号，便于在回答中加入引用标记（如 `[1-2]` 表示第1组第2条切片）。

## 进一步工作
- 引入更多领域指令与模板，使汇总更结构化。
- 增加每组的 top-k 自适应策略，按分组权重调整检索数量。