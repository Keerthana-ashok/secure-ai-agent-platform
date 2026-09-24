from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

from .llm.client import LLMClient, LLMError
from .config import get_settings
from .rag.vector_store import VectorStore
from .rag.rag_service import RAGService

app = FastAPI()


def get_llm_client() -> LLMClient:
    return LLMClient()


def get_rag_service() -> RAGService:
    # Create RAG service with an in-memory/chroma-backed vector store
    vs = VectorStore()
    llm = get_llm_client()
    return RAGService(vector_store=vs, llm_client=llm)


class ChatRequest(BaseModel):
    message: str
    conversation: List[Dict[str, Any]] = []


class ChatResponse(BaseModel):
    response: str


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, llm: LLMClient = Depends(get_llm_client)):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message is empty")

    # Build conversation to send to the model
    messages = list(req.conversation) if req.conversation else []
    messages.append({"role": "user", "content": req.message})

    try:
        resp_text = await llm.send_prompt(messages)
    except LLMError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=503, detail="LLM service error")

    return {"response": resp_text}


class AskRequest(BaseModel):
    question: str


@app.post("/ask")
async def ask_endpoint(req: AskRequest):
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is empty")

    rag = get_rag_service()
    try:
        result = await rag.ask(req.question)
    except LLMError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        # Do not expose internal exception details to API clients; log for diagnostics.
        import logging

        logging.getLogger("app").exception("RAG ask failed")
        raise HTTPException(status_code=500, detail="Internal server error")

    return {"answer": result.get("answer"), "sources": result.get("sources")}
