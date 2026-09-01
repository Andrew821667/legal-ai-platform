"""Internal HTTP channel for the website assistant."""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
from typing import Annotated, Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, model_validator

import ai_brain


logger = logging.getLogger(__name__)

WEB_CONTEXT = """
Ты отвечаешь посетителю на публичном сайте AI Verdict, используя те же знания и правила, что Telegram-ассистент.
На сайте под диалогом есть кнопка «Передать задачу» с защищенной формой и согласием на обработку данных.
Не проси отправлять телефон, email, документы, паспортные или иные чувствительные данные прямо в чат.
Когда нужен контакт с командой, предложи нажать «Передать задачу». Не утверждай, что контакт или заявка уже сохранены.
В AI Verdict работают юридическая и инженерная практики.
Если вопрос относится к обычным юридическим услугам, назови юридическую практику.
Если это самостоятельная программная разработка, назови инженерную практику.
Автоматизацию юридической функции объясняй как основное совместное направление двух практик, а не как третью практику.
""".strip()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    message: str = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def validate_user_message(self) -> "ChatMessage":
        if self.role == "user" and len(self.message) > 1600:
            raise ValueError("User message is too long")
        return self


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    messages: list[ChatMessage] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_dialog(self) -> "ChatRequest":
        if self.messages[-1].role != "user":
            raise ValueError("Last message must be from the user")
        if sum(len(item.message) for item in self.messages) > 9000:
            raise ValueError("Conversation is too long")
        return self


class ChatResponse(BaseModel):
    reply: str


app = FastAPI(
    title="AI Verdict Website Assistant",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
web_brain = ai_brain.AIBrain()


def _require_key(value: str | None) -> None:
    expected = os.getenv("WEB_ASSISTANT_INTERNAL_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Assistant API is not configured")
    if not value or not secrets.compare_digest(value, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
async def health() -> dict[str, object]:
    return {"ok": True, "service": "website-assistant"}


@app.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    assistant_key: Annotated[str | None, Header(alias="X-Assistant-Key")] = None,
) -> ChatResponse:
    _require_key(assistant_key)
    history = [item.model_dump() for item in payload.messages]
    chunks: list[str] = []

    try:
        async with asyncio.timeout(40):
            async for part in web_brain.generate_response_stream(history, funnel_context=WEB_CONTEXT):
                chunks.append(part)
    except TimeoutError as error:
        logger.warning("Website assistant timed out")
        raise HTTPException(status_code=504, detail="Assistant timeout") from error

    reply = "".join(chunks).strip()
    if not reply:
        raise HTTPException(status_code=502, detail="Assistant returned an empty response")
    return ChatResponse(reply=reply[:5000])
