以langchain为底座的多知识库搜索工具

# 技术栈
底座：langchain / langchain-ollama / langchain-text-splitters / langchain-chroma
向量数据库：chroma
llm：Ollama（本地，qwen3:0.6b，JSON输出，temperature=0）
embedding模型：Ollama（bge-m3:latest）

# 核心逻辑
查询多个知识库，有一个核心知识库，其他为地域所属知识库，地域知识库的元数据中有省份信息。
用户的问题可能包含地域信息，部分知识库的元数据中也有地域信息。
分为3级同时查询并汇总。
查询遵循以下步骤：
1. 提取用户问题中的地域信息。
2. 根据用户的地域信息，知识库分为3级，1级为核心知识库，2级为对应省份的知识库，3级为其他知识库。
3. 分别查询知识库。
4. LLM汇总3级查询结果并输出。

# 技术要求
1. 使用uv管理工程，使用uv venv创建虚拟环境。
2. dotenv管理环境。
3. 所有的Prompt汇总在prompts.py文件中。

# 快速开始

- 环境准备：
  - 使用 uv：`uv venv && source .venv/bin/activate && uv pip install -e .`（或 `uv sync`）。
  - 使用 pip：`python -m venv .venv && source .venv/bin/activate && pip install chromadb python-dotenv langchain langchain-community langchain-text-splitters langchain-ollama langchain-chroma ollama`。
- 初始化数据：
  - `python -m src.data_init.cli --reset --verbose`（可选 `--data-dir`、`--persist-dir`）。
- 运行查询并导出 Markdown：
  - `python src/app.py --q "四川在提高政府采购效率有哪些措施？" --out output/result.md --top-k 3`。
  - 可选：`--province 省份名`。
- 环境变量：
  - `.env` 可选配置：`OLLAMA_BASE_URL`（如 `http://localhost:11434`）、`OLLAMA_EMBED_MODEL`（默认 `bge-m3:latest`）。
  - `CHROMA_PERSIST_DIR`（默认 `.chroma`）。
  - 请确保已在本地 Ollama 中拉取嵌入与 LLM 模型（例如：`ollama pull bge-m3:latest`、`ollama pull qwen3:0.6b`），脚本不会触发下载。
- 输出说明：
  - 生成的 Markdown 包含：问题、清洗后的总结（使用 JSON 的 `summary` 字段）与分组引用；引用项按组展示并采用“文件名-切片id”格式（如 `【四川】深化政采制度-0`）。


# 案例材料
案例来自[中国政府采购网](https://www.ccgp.gov.cn/index.shtml)
原始案例材料放在data目录下。文件命名会以中括号【】开头，【中央】为核心知识库，余下的按照省份划分为不同知识库。

# 主要功能
1. 初始化数据
仅项目初始化时需要运行一次，后续运行时无需重复初始化。
从data目录下的文件初始化向量数据库。根据文件名中的省份信息，划分不同的知识库标识并添加进元数据。
2. 查询知识库
用户输入问题后，根据问题中的地域信息，动态划分为3级知识库并同时查询，最后由LLM汇总结果并输出，汇总结果包含原始文档名称和地域元数据。

# 实现步骤
每个小步骤源码都要在src中，测试代码要在test中。
1. 初始化数据
完成对data目录下文件的初始化，包括读取文件内容、生成embedding、添加到向量数据库中。
在test文件夹下生成测试工具，来测试初始化是否成功、已经处理的文件、元数据。
2. 最简单的一个查询
最简单的一个RAG pipline，可以实现用户输入问题，查询知识库，返回切片。
3. 前置地域信息处理
4. 动态划分知识库
5. 前置workflow实现
串联地域信息解析、动态划分filter、触发3次查询，最后由LLM汇总结果并输出。
6. 完善整理项目