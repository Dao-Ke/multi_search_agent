# 数据初始化使用说明

本文档介绍如何使用应用内方法与命令行入口对 Chroma 向量库进行初始化，并说明各参数、返回值与常见问题。

## 应用内方法

- 方法：`src.app.init_data`
- 签名：
  - `def init_data(reset: bool = False, verbose: bool = True, data_dir: Optional[str] = None, persist_dir: Optional[str] = None) -> Dict`

### 参数说明

- `reset`：默认 `False`。为 `True` 时先删除并重建集合，适合首次初始化或重新导入。
- `verbose`：默认 `True`。开启后会打印每个文档的插入明细（chunk 数量、元数据）以及统计信息。
- `data_dir`：可选，默认使用 `src.config.DATA_DIR`（通常为项目根目录下的 `data/`）。
- `persist_dir`：可选，默认使用 `src.config.CHROMA_PERSIST_DIR`（通常为 `.chroma`），也可由 `.env` 中的 `CHROMA_PERSIST_DIR` 覆盖。

### 返回值

返回 `Dict`，包含以下字段：

- `persist_dir`：实际使用的持久化目录。
- `collection`：集合名，当前为 `knowledge_base`。
- `total_chunks`：集合内总 chunk 数。
- `processed_files`：本次处理的文件名列表。
- `by_kb_type`：按 `kb_type`（`core`/`regional`）的计数统计。
- `file_chunk_counts`：每个文件对应的 chunk 数量统计。
- `skipped_empty_files`：被判定为空并跳过的文件名列表。

### 使用示例（Python）

```
from src.app import init_data
import json

summary = init_data(reset=True)  # 默认 verbose=True 会打印插入明细
print(json.dumps(summary, ensure_ascii=False, indent=2))
```

## 命令行使用

- 入口：`python -m src.data_init.cli`
- 常用示例：
  - `source .venv/bin/activate && python -m src.data_init.cli --reset --verbose`

### CLI 参数

- `--reset`：删除并重建集合。
- `--verbose`：打印插入明细与统计信息。
- `--data-dir <路径>`：指定数据目录，默认 `data/`。
- `--persist-dir <路径>`：指定 Chroma 持久化目录，默认 `.chroma`。

## 嵌入器（严格模式）

- 仅使用本地 Ollama 嵌入：`langchain_community.embeddings.OllamaEmbeddings`（默认模型 `nomic-embed-text:latest`）。
- 初始化与查询共享同一嵌入模型，失败直接报错，不做任何回退。
- 必须提前在本地 Ollama 中拉取嵌入模型（例如：`ollama pull nomic-embed-text:latest`）；脚本不会触发下载。

## 环境变量

- `CHROMA_PERSIST_DIR`：覆盖持久化目录（默认 `.chroma`）。
- `OLLAMA_BASE_URL`：本地 Ollama 服务地址（默认 `http://localhost:11434`）。
- `OLLAMA_EMBED_MODEL`：嵌入模型名称（默认 `nomic-embed-text:latest`）。

## 日志与输出示例

开启 `verbose` 后，会打印类似如下内容：

```
Chroma collection: knowledge_base | persist_dir: .chroma
Inserted: 【中央】国采中心：开创集采事业发展新局面 [kb_type=core, province=中央] chunks=2
Inserted: 【四川】出台稳外资行动实施方案 [kb_type=regional, province=四川] chunks=1
...
Total chunks added: 18 | collection count: 18
```

返回的 JSON 示例包含上述统计字段，便于程序化检查与验证。

## 数据要求与解析

- 文件需为 UTF-8 文本；空文件会被跳过，并记录在 `skipped_empty_files`。
- 文件名用于解析元数据：
  - `【中央】xxx` → `kb_type=core`，`province=中央`
  - `【省/市】xxx` → `kb_type=regional`，`province` 为括号内名称
  - 未匹配 → `kb_type=regional`，`province=未知`
- 切片策略：`RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)`（由 `langchain-text-splitters` 提供）。

## 常见问题

- 重新导入同一批数据建议使用 `reset=True`，避免重复写入或 ID 冲突（ID 为 `source_name::chunk_id`）。
- 自定义持久化目录请在 `.env` 中设置 `CHROMA_PERSIST_DIR`，或通过参数传入。
- 嵌入为严格模式：请确保本地已拉取 `OLLAMA_EMBED_MODEL` 指定的模型（例如：`ollama pull nomic-embed-text:latest`），否则初始化会直接报错。