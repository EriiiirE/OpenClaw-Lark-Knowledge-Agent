# Privacy & Publish Checklist

Before pushing public:

1. Ensure `.env.local` is NOT tracked
2. Keep `.env.example` as placeholders only
3. Exclude runtime data (`logs/state/output/data/embeddings/vectorstore`)
4. Re-scan for accidental secrets

Recommended local scan:

```bash
rg -n --hidden --no-ignore-vcs -S "(sk-|AKIA|BEGIN PRIVATE KEY|api[_-]?key|token|secret|password)" .
```
