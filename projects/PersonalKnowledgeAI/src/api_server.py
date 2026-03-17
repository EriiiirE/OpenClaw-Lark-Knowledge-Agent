from __future__ import annotations

from typing import Any

from agent_runtime import kb_ask, kb_search, kb_sources
from pipeline_ops import command_build_index, doctor, get_provider_summary
from settings import RUNTIME

try:
    from fastapi import Body, FastAPI, HTTPException
except Exception:  # pragma: no cover - optional dependency
    Body = None
    FastAPI = None
    HTTPException = RuntimeError


def _require_fastapi():
    if FastAPI is None or Body is None:
        raise RuntimeError("FastAPI is not installed. Run `pip install fastapi uvicorn` first.")


def create_app():
    _require_fastapi()
    app = FastAPI(title="PersonalKnowledgeAI API", version="0.2.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "status": doctor()}

    @app.get("/providers")
    def providers() -> dict[str, Any]:
        return {"ok": True, "providers": get_provider_summary()}

    @app.get("/sources")
    def sources() -> dict[str, Any]:
        return {"ok": True, "sources": kb_sources()}

    @app.post("/index/build")
    def build_index(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        try:
            result = command_build_index(payload)
            return {"ok": True, "result": result}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/search")
    def search(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        filters = dict(payload.get("filters") or {})
        try:
            result = kb_search(
                query=str(payload["query"]),
                filters=filters,
                top_k=int(payload.get("top_k", 6)),
                alpha=float(payload.get("alpha", 0.45)),
            )
            return {"ok": True, **result}
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"missing field: {exc}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/ask")
    def ask(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        filters = dict(payload.get("filters") or {})
        try:
            result = kb_ask(
                query=str(payload["query"]),
                filters=filters,
                top_k=int(payload.get("top_k", 6)),
                alpha=float(payload.get("alpha", 0.45)),
                prefer_llm=bool(payload.get("prefer_llm", True)),
            )
            return {"ok": True, **result}
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"missing field: {exc}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return app


def run() -> None:
    _require_fastapi()
    try:
        import uvicorn
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(f"Uvicorn is not installed: {exc}") from exc
    uvicorn.run(create_app(), host=RUNTIME.api.host, port=RUNTIME.api.port)
