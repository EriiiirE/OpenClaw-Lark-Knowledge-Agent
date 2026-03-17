# PersonalKnowledgeAI

一个以 `PersonalKnowledgeAI` 为核心仓库的本地知识工程项目，负责把 Markdown 内容源沉淀为可检索、可问答、可通过 OpenClaw/Skill 调用、可通过 API/MCP 暴露的统一 RAG 内核。

## 定位

这个仓库现在承担 5 层职责：

1. 内容标准化：把 `Celueshi`、`Jingyingrike` 和 `knowledge/` 里的 Markdown 变成统一文档对象
2. 检索构建：section-aware chunk、embedding、BM25、FAISS、本地索引
3. Grounded RAG：混合检索、邻块扩展、证据优先回答
4. Agent runtime：单 Agent + `kb.search / kb.ask / kb.sources / kb.status / kb.rebuild`
5. 接入层：CLI、Streamlit、FastAPI、MCP、OpenClaw skill

## 目录结构

```text
src/
  main.py
  pipeline_ops.py
  chunking.py
  embedding_backends.py
  vector_stores.py
  retrieval_pipeline.py
  agent_runtime.py
  api_server.py
  mcp_server.py
  rag_pipeline.py
  streamlit_app.py
integrations/
  openclaw/
tests/
data/
state/
logs/
```

## 主要能力

- 默认本地优先：
  - section-aware chunk
  - `BM25 + dense + alpha` hybrid retrieval
  - 本地 `FAISS + numpy`
  - grounded answer
- 可选增强：
  - `sentence-transformers`
  - DashScope embedding
  - OpenAI-compatible embedding / generation
  - SiliconFlow-compatible endpoint
  - Milvus vector store
  - llm-assisted chunk
  - FastAPI
  - MCP server

## 安装

```bash
cd /Users/eri/Desktop/PersonalKnowledgeAI
python3 -m venv .venv-mac
source .venv-mac/bin/activate
pip install -r requirements.txt
```

## 基础构建命令

全量构建：

```bash
python src/main.py build-all
```

分阶段执行：

```bash
python src/main.py normalize
python src/main.py classify --mode rule
python src/main.py chunk
python src/main.py index
```

复核：

```bash
python src/main.py review --limit 20
python src/main.py review --doc-id doc_xxx
```

## 新增运行命令

查看运行健康度：

```bash
python src/main.py doctor
```

查看 provider 配置：

```bash
python src/main.py providers
```

启动 API：

```bash
python src/main.py serve
```

启动 MCP：

```bash
python src/main.py mcp-serve
```

CLI 问答：

```bash
python src/ask.py "拖延症的本质是什么？"
```

## FastAPI 接口

- `GET /health`
- `GET /providers`
- `GET /sources`
- `POST /index/build`
- `POST /search`
- `POST /ask`

## MCP 工具

- `kb_search`
- `kb_ask`
- `kb_status`
- `kb_sources`

## OpenClaw 集成

仓库已经自带正式 skill：

```text
integrations/openclaw/skills/pkai-rag/
```

复制到 OpenClaw workspace：

```bash
mkdir -p ~/.openclaw/workspace/skills
cp -R integrations/openclaw/skills/pkai-rag ~/.openclaw/workspace/skills/
```

保持你的原有接入链路不变：

`OpenClaw -> Skill -> 本地 PersonalKnowledgeAI`

详细说明见 [integrations/openclaw/README.md](integrations/openclaw/README.md)。

## 环境变量

生成模型：

- `PKAI_API_KEY`
- `PKAI_BASE_URL`
- `PKAI_MODEL`

Embedding：

- `PKAI_EMBED_BACKEND`
- `PKAI_EMBED_MODEL`
- `PKAI_EMBED_API_KEY`
- `PKAI_EMBED_BASE_URL`
- `DASHSCOPE_API_KEY`

Chunk：

- `PKAI_CHUNK_MODE`
- `PKAI_CHUNK_LLM_ENABLED`

Vector Store：

- `PKAI_VECTOR_STORE_BACKEND`
- `PKAI_MILVUS_URI`
- `PKAI_MILVUS_TOKEN`
- `PKAI_MILVUS_COLLECTION`

服务：

- `PKAI_API_HOST`
- `PKAI_API_PORT`
- `PKAI_MCP_TRANSPORT`
- `PKAI_MCP_HOST`
- `PKAI_MCP_PORT`

## 默认技术路线

- Chunk：Markdown section-aware chunk
- Retrieval：BM25 + dense hybrid retrieval
- Dense backend：hashing fallback
- Vector store：local FAISS
- Answering：grounded retrieval-first
- Agent：single agent + tool mindset
- Skill：OpenClaw local skill
- MCP：optional lightweight server

## 兼容性说明

- 旧入口如 `chunk_docs.py`、`embed_chunks.py`、`rag_pipeline.py` 仍保留
- `build-all`、`ask.py`、`streamlit_app.py` 仍可继续使用
- OpenClaw 接入流程不需要改成 API 模式，仍可继续走本地脚本 skill
