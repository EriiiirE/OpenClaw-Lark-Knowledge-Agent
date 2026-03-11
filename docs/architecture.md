# Architecture

## Pipeline

1. Content Ingestion
- Celueshi: WeChat public article directory parsing + article extraction
- Jingyingrike: Dedao course catalog extraction + article extraction

2. Knowledge Processing
- Normalize markdown to `documents`
- Rule/LLM-assisted taxonomy classification
- Chunk by section + overlap
- Build BM25 + vector indexes

3. Retrieval & Answering
- Hybrid retrieval + filter-aware rerank
- Evidence-grounded answer generation with fallback strategy

4. Agent Delivery
- Channel layer via OpenClaw
- Feishu/Lark as the primary interaction channel
