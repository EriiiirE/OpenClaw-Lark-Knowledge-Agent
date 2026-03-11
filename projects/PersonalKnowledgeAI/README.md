# PersonalKnowledgeAI

基于现有 Markdown 知识库的本地标准化、分类、切块、检索与 RAG MVP 工程。

## 项目目标

本项目只读消费两套现有知识源：

- `d:\Desk\Jingyingrike\output_md`
- `d:\Desk\Celueshi\output_md`

不改动任何原始 `.md` 文件，只在当前工程内生成：

- `data/documents.jsonl`
- `data/review_queue.jsonl`
- `data/chunks.jsonl`
- `state/bm25_index.pkl`
- `state/vector_index.pkl`
- `data/embeddings.npy`
- `data/chunk_id_map.json`

## 输入来源说明

- `jingyingrike`：精英日课 Markdown 文档
- `yexiu_wechat`：叶修公众号 Markdown 文档

`documents.jsonl` 采用 `1 个 md 文件 = 1 个 document`。  
`chunks.jsonl` 采用 `##` 标题优先切块，再按长度继续拆分。

## 目录结构

```text
src/
  main.py
  taxonomy.yaml
  taxonomy.py
  settings.py
  models.py
  source_loader.py
  utils_markdown.py
  normalize_docs.py
  classify_docs.py
  review_docs.py
  chunk_docs.py
  embed_chunks.py
  build_indexes.py
  retrieve.py
  rag_answer.py
  streamlit_app.py
data/
state/
logs/
tests/
```

## 安装

```powershell
cd d:\Desk\PersonalKnowledgeAI
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## 全流程命令

```powershell
.\.venv\Scripts\python src/main.py build-all
```

如果你配置了 OpenAI 兼容 API，并希望分类阶段可选增强：

```powershell
$env:PKAI_API_KEY="your-key"
$env:PKAI_BASE_URL="https://your-openai-compatible-endpoint/v1"
$env:PKAI_MODEL="your-model"
.\.venv\Scripts\python src/main.py build-all --mode auto
```

## 分阶段命令

标准化：

```powershell
.\.venv\Scripts\python src/main.py normalize
```

分类：

```powershell
.\.venv\Scripts\python src/main.py classify --mode rule
.\.venv\Scripts\python src/main.py classify --mode auto
.\.venv\Scripts\python src/main.py classify --mode llm
```

切块：

```powershell
.\.venv\Scripts\python src/main.py chunk
```

构建索引：

```powershell
.\.venv\Scripts\python src/main.py index
```

## review_queue CLI 复核

查看并复核前 20 条：

```powershell
.\.venv\Scripts\python src/main.py review --limit 20
```

只复核某个文档：

```powershell
.\.venv\Scripts\python src/main.py review --doc-id doc_jingyingrike_xxx
```

复核结果会写回：

- `data/documents.jsonl`
- `data/review_queue.jsonl`
- `state/classification_cache.json`

## Streamlit RAG MVP

先完成全流程构建：

```powershell
.\.venv\Scripts\python src/main.py build-all
```

然后启动界面：

```powershell
streamlit run src/streamlit_app.py
```

界面支持：

- 来源过滤
- 一级标题过滤
- 主题标签过滤
- 属性标签过滤
- series 过滤
- BM25 + 向量混合检索
- 引用展开查看
- 可选 LLM 生成模式

## OpenAI 兼容增强模式

默认关闭。只有你显式配置以下环境变量时才会启用：

- `PKAI_API_KEY`
- `PKAI_BASE_URL`
- `PKAI_MODEL`

分类阶段和 RAG 生成阶段都只会在显式启用时调用它；非法标签输出会自动回退到规则模式。

## 向量模型说明

默认向量后端使用本地 `hashing-char-ngram`，不需要下载模型，适合普通笔记本直接跑通。  
如果你想显式切换到 `BAAI/bge-small-zh-v1.5`，可以先设置：

```powershell
$env:PKAI_VECTOR_BACKEND="sentence-transformers"
```

然后再执行 `index` 或 `build-all`。如果模型加载失败，系统会自动回退到本地哈希向量。

## taxonomy、documents、chunks 的关系

- `taxonomy.yaml`：固定标签池与规则约束
- `documents.jsonl`：文档级知识对象
- `chunks.jsonl`：检索级知识片段

分类在 `documents.jsonl` 上完成；检索与 RAG 在 `chunks.jsonl` 上完成。

## 后续可扩展点

1. 提升规则分类的关键词提示词与打分权重。
2. 增加更细的 review 工作流，例如批量导出人工复核任务。
3. 替换默认向量模型，或增加本地 reranker。
4. 增加 search CLI 和导出问答日志。
5. 把 Streamlit MVP 扩展成多轮对话与个人工作台。
