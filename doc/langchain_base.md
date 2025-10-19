# 以langchain为底座的修改方案
工程修改以langchain为底座，方便扩展，需要替换的内容有：
- llm、embedding均使用本地 Ollama 加载。LLM 使用 `langchain-ollama` 的 `OllamaLLM`（默认 `qwen3:0.6b`，`format="json"`，`temperature=0`），嵌入使用 `langchain_ollama.OllamaEmbeddings`（默认 `bge-m3:latest`）。
- 向量数据库使用VectorStore包装
- 检索器使用Retriever包装

## 目标与原则
- 保持现有功能不变：多知识库分组检索、LLM汇总、Markdown导出。
- 引入 LangChain 仅作“可组合的外层”，把检索、提示、总结等抽象为可复用链。
- 渐进式迁移：先包裹（adapter/wrapper），后替换（核心实现）。

## 组件替换与封装建议（按模块）
- 数据加载与切片：
  - 使用 `langchain_community.document_loaders.DirectoryLoader/TextLoader` 读取 `data/`。
  - 统一 `Document`（`page_content` + `metadata`），替换当前自定义结构，便于后续复用。
  - 切片使用 `langchain_text_splitters.RecursiveCharacterTextSplitter`（保留现有参数），输出 `Document` 列表。
- 向量库（VectorStore）：
  - 用 `langchain_chroma.Chroma` 作为底层包装，设置 `persist_directory` 与集合名。
  - 写入阶段使用 `Chroma.from_documents(docs, embeddings, ...)` 直接持久化；自带 `metadata` 与 `id` 管理。
  - 统一嵌入器接口为 LangChain `Embeddings`（仅 Ollama，严格模式）。
- 检索器（Retriever）：
  - 用 `vectorstore.as_retriever(search_kwargs={"k": top_k, "filter": where})` 替换 `simple_query`。
  - 多组检索用 `EnsembleRetriever` 或并发 `RunnableParallel` 组合多个 `Retriever`，在返回阶段做去重与标注。
  - 可选：引入 `ContextualCompressionRetriever` + `EmbeddingsRedundantFilter` 做去重压缩，减少相似切片。
- 流程编排（LCEL）：
  - 以 `RunnableSequence`/`RunnableParallel` 编排：`提取省份 → 构建过滤器 → 多组检索 → LLM汇总 → 输出解析`。
  - 提取省份可用 `RunnableLambda` 包裹现有规则函数；后续可替换为 LLM 判别链。
  - 多组并发：`RunnableParallel` fan-out 三路检索后在 `map` 阶段统一归性与编号标记。
- 提示与输出解析：
  - 使用 `PromptTemplate/ChatPromptTemplate` 管理汇总提示，参数化组名、编号与内容。
  - 输出解析器用 `StructuredOutputParser/JsonOutputParser` 或 `PydanticOutputParser`，确保稳定产出含 `summary/references` 的结构化结果。
  - 继续在落盘前执行“提取 content 字段”的清洗，避免 Markdown 出现整段 JSON。
- LLM/Embedding 抽象：
  - LLM：使用 `langchain-ollama` 的 `OllamaLLM`（固定本地模型），暴露 `invoke/ainvoke`。
  - Embeddings：仅使用 `langchain_ollama.OllamaEmbeddings`，保持与初始化一致的本地模型，严格模式不做回退。
- 观测与回调：
  - 接入 `Callbacks` 与 LangSmith（可选），在 CLI 参数中开启/关闭；支持链级、步骤级事件追踪。
- 缓存与复用：
  - 结合 `langchain.cache`（如 SQLiteCache 或 InMemoryCache）对相同问题的汇总调用做缓存，减少 LLM 成本。
- 异步与并发：
  - 使用 `ainvoke` + `RunnableParallel` 实现组间并发检索；在 CLI 增加 `--concurrency` 控制并行度。
- 测试与替身：
  - 用 `FakeChatModel`（或自定义 dummy ChatModel）稳定单元测试，不依赖外部 LLM。
  - 对检索链使用固定语料 + 伪嵌入，保障可重复性与覆盖率。
- CLI/入口统一：
  - `app.py` 暴露一个 `chain = build_app_chain()`；CLI 仅负责解析参数与 `chain.invoke(params)`。
  - 未来可通过 `pyproject.toml` 增加 console_scripts，命令行更友好。

## 与现有代码的映射关系（迁移点位）
- `src/data_init/initializer.py`
  - 替换自定义切片与写入逻辑 → `Document` + `Chroma.from_documents`；
  - `select_embedder()` → 返回 LangChain `Embeddings` 实例；
  - 维持 `metadata` 字段（`kb_type/province/source_name/chunk_id`）一致。
- `src/rag/simple.py`
  - `simple_query()` → 用 `VectorStoreRetriever`，支持 `filter` 与 `k`；
  - 输出改为 `Document` 或统一的 `dict`（含 `page_content/metadata`），减少自定义转换。
- `src/pipeline/core.py`
  - `partition_query()` → 构建三路 `Retriever`，并用 `RunnableParallel` 并发检索；
  - 汇总阶段改为 `prompt | llm | output_parser` 的标准链；
  - 返回结构维持 `summary/references/groups` 字段，便于与现有 Markdown 写入兼容。
- `src/app.py`
  - 提供 `build_app_chain()`，暴露“问题 → Markdown文本”的完整链；
  - 写盘仍在 Python 侧完成，但上游产物来自 `StrOutputParser` 或结构化解析器。

## 增量迁移路线（建议）
1. 抽象嵌入器：统一为 LangChain `Embeddings` 接口（仅 Ollama，本地严格模式）。
2. 替换向量库调用：`chromadb` 直接调用改为 `Chroma` VectorStore（读写路径不变）。
3. 检索器统一：`simple_query` 迁移为 `as_retriever`，组内 `k/filter` 通过 `search_kwargs` 管理。
4. 汇总链标准化：`PromptTemplate → LLM → OutputParser`，固化 `summary/references` 的结构化输出。
5. 编排与并发：引入 `RunnableSequence/Parallel`，实现三路并发与归并，保留现有编号/分组语义。
6. 观测与缓存（可选）：加入 LangSmith 回调与 LLM 缓存，降低成本并提升可观测性。

## 风险与取舍
- 依赖体积与版本：引入 `langchain`/`langchain_community`/`langchain_text_splitters`/`langchain_ollama`/`langchain_chroma`，需固定版本并关注 API 变更（建议 `>=0.3.x`）。
- 过滤语义：`Chroma` 的 `filter` 不支持逻辑取反；“其他地域”仍需后置排除（与现方案一致）。
- 轻度性能开销：链式编排与回调会带来少量开销，需评估并发度与缓存策略。

## 可选增强点
- 结果重排：通过 `LLMReRanker` 或 `ContextualCompressionRetriever` 提升相关性与多样性。
- Top-k 自适应：按分组权重和召回质量动态调整 `k`，在链中注入策略节点。
- 多路问题改写：`MultiQueryRetriever` 或并行改写提升召回覆盖面（谨慎控制成本）。
- 更强输出结构：用 `PydanticOutputParser` 把 `summary`、`references` 映射到强类型，减少后处理出错。

## 结论
- 以上改动均为“壳层迁移 + 标准化编排”，不改变现有业务语义。
- 建议从嵌入器与 VectorStore 两处入手，2～3步即可完成首轮迁移；随后把检索与汇总链统一到 LCEL。
