# OpenClaw Integration

这个目录把 `PersonalKnowledgeAI` 的 OpenClaw skill 正式放回仓库，避免运行逻辑只存在于 `~/.openclaw/workspace/skills`。

## 目录

```text
integrations/openclaw/
  README.md
  skills/
    pkai-rag/
      SKILL.md
      scripts/
        pkai_rag.sh
        pkai_rag_query.py
```

## 安装到 OpenClaw Workspace

把 skill 复制到你的 OpenClaw workspace：

```bash
mkdir -p ~/.openclaw/workspace/skills
cp -R integrations/openclaw/skills/pkai-rag ~/.openclaw/workspace/skills/
```

## 运行前提

- `PersonalKnowledgeAI` 已完成 `python src/main.py build-all`
- `OpenClaw -> Skill -> 本地脚本` 的调用链保持不变
- 需要时可继续复用你已有的 Feishu、SiliconFlow、MiniMax 配置

## 可选环境变量

- `PKAI_ROOT`
  作用：覆盖默认的 `PersonalKnowledgeAI` 仓库路径
- `PKAI_PYTHON`
  作用：显式指定 skill 运行时使用的 Python

## 推荐共存方式

- RAG 检索默认走本地 `BM25 + FAISS`
- OpenClaw 主模型仍可继续使用你现有的 SiliconFlow / MiniMax
- 如果你为 `PersonalKnowledgeAI` 开启了云生成，skill 也会自动复用本地环境变量
