---
name: pkai-rag
description: Retrieve grounded evidence from PersonalKnowledgeAI and answer with concise citations for OpenClaw.
metadata: { "openclaw": { "emoji": "📚", "always": true } }
---

# PKAI RAG

Use this skill when the user asks a conceptual, explanatory, reflective, or evidence-sensitive question that should first consult the PersonalKnowledgeAI corpus.

## Best-fit scenarios

- “什么是……”
- “本质是什么……”
- “为什么会这样……”
- “怎么理解……”
- 需要引用知识库证据的成长、认知、策略、行为类问题

## Skip this skill when

- 只是闲聊
- 纯工程排错，且和知识库内容无关
- 用户明确不需要引用或检索

## Run

```bash
bash {baseDir}/scripts/pkai_rag.sh --query "<user question>" --max-citations 2
```

Optional tuning:

```bash
bash {baseDir}/scripts/pkai_rag.sh --query "<user question>" --top-k 6 --alpha 0.45 --max-citations 2
```

## Output contract

The script returns JSON with:

- `answer_hint`
- `citations`
- `retrieval_mode`
- `confidence`
- `standalone_query`

Each citation includes title, section, source, score, snippet, and a compact quote.

## Response policy

1. Treat RAG as grounding, not as a replacement for the assistant's reasoning.
2. Prefer 1-2 strong citations over many weak ones.
3. Keep quotes short and evidence-like, not long copy-paste blocks.
4. If no strong hit exists, answer normally and say no direct KB evidence was found.
5. Never fabricate citations.
