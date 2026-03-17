# AI Knowledge Agent Showcase

端到端个人知识库 Agent 项目（采集 -> 清洗 -> RAG -> Agent -> Skill/MCP/API -> 渠道接入）的源码展示仓库。

## What Is Included

- `projects/Celueshi`: 微信公众号目录页内容抓取与 Markdown 归档（Playwright）
- `projects/Jingyingrike`: 得到课程内容抓取与专题化归档（Playwright）
- `projects/PersonalKnowledgeAI`: 本地知识库标准化、分类、切块、混合检索、Grounded RAG、Agent Runtime、FastAPI、MCP 与 OpenClaw Skill

## OpenClaw / Feishu Integration

本仓库不内置 OpenClaw 源码（避免体积过大、便于独立维护），但已内置可直接复制到 OpenClaw workspace 的 skill 集成目录。

接入方式：

1. 安装 OpenClaw（官方）
2. 安装 Feishu 插件 `@openclaw/feishu`
3. 将本仓库 `PersonalKnowledgeAI` 作为本地知识服务（CLI / Streamlit / FastAPI / MCP）
4. 复制 `projects/PersonalKnowledgeAI/integrations/openclaw/skills/pkai-rag` 到 OpenClaw workspace
5. 通过 OpenClaw 路由把飞书消息接入你的个人 Agent 流程

## Security Note

本仓库已移除运行时密钥与本地数据产物：

- no real API keys
- no `.env.local`
- no runtime logs/state/output cache

请使用 `.env.example` 填写你自己的配置。

## Quick Start

### 1) Celueshi / Jingyingrike

```bash
cd projects/Celueshi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

### 2) PersonalKnowledgeAI

```bash
cd projects/PersonalKnowledgeAI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local
```

构建索引：

```bash
python src/main.py build-all
```

启动 UI：

```bash
streamlit run src/streamlit_app.py
```

运行健康检查：

```bash
python src/main.py doctor
python src/main.py providers
```

启动 API / MCP：

```bash
python src/main.py serve
python src/main.py mcp-serve
```
