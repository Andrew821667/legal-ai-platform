"""Internal HTTP channel for the website assistant."""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from typing import Annotated, Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, model_validator

import ai_brain
import assistant_tools
import intent_router
import platform_context


logger = logging.getLogger(__name__)

WEB_CONTEXT = """
Ты отвечаешь посетителю на публичном сайте AI Verdict, используя те же знания и правила, что Telegram-ассистент.
На сайте под диалогом есть кнопка «Передать задачу» с защищенной формой и согласием на обработку данных.
Для НОВОГО обращения не проси телефон, email, документы, паспортные или иные чувствительные данные прямо в
чат — предложи нажать «Передать задачу». Не утверждай, что контакт или заявка уже сохранены.
Исключение — если собеседник САМ говорит, что уже наш клиент: тогда можно спросить его контакт (телефон/email)
и номер договора прямо в чате и вызвать identify_returning_client, чтобы поднять его данные. Не предлагай эту
проверку первым и не спрашивай номер договора без повода — только в ответ на явное «я уже клиент» или похожее.
В AI Verdict работают юридическая и инженерная практики.
Если вопрос относится к обычным юридическим услугам, назови юридическую практику.
Если это самостоятельная программная разработка, назови инженерную практику.
Автоматизацию юридической функции объясняй как основное совместное направление двух практик, а не как третью практику.
""".strip()

# session_id (sessionStorage на клиенте) -> (telegram_id, unix-время истечения).
# Живёт только в памяти этого процесса — переживёт долгий диалог в одной
# вкладке, но не переживёт рестарт контейнера. Осознанный компромисс первой
# итерации: переспросить номер договора после редкого рестарта не страшно,
# полноценная сессионная БД для этого — избыточно.
_VERIFIED_SESSIONS: dict[str, tuple[int, float]] = {}
_VERIFIED_SESSION_TTL_SECONDS = 3600


def _get_verified_telegram_id(session_id: str) -> int | None:
    entry = _VERIFIED_SESSIONS.get(session_id)
    if entry is None:
        return None
    telegram_id, expires_at = entry
    if time.time() > expires_at:
        _VERIFIED_SESSIONS.pop(session_id, None)
        return None
    return telegram_id


def _remember_verified_session(session_id: str, telegram_id: int) -> None:
    now = time.time()
    _VERIFIED_SESSIONS[session_id] = (telegram_id, now + _VERIFIED_SESSION_TTL_SECONDS)
    expired = [key for key, (_, expires_at) in _VERIFIED_SESSIONS.items() if now > expires_at]
    for key in expired:
        _VERIFIED_SESSIONS.pop(key, None)


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

    verified_telegram_id = _get_verified_telegram_id(payload.session_id)
    core_context = platform_context.build_core_context_block(verified_telegram_id)
    state = assistant_tools.WebSessionState(telegram_id=verified_telegram_id)
    tools = [assistant_tools.IDENTIFY_RETURNING_CLIENT_TOOL, *assistant_tools.TOOLS_SCHEMA]

    try:
        async with asyncio.timeout(40):
            # has_core_context отражает состояние НА МОМЕНТ этого сообщения —
            # если человек подтвердится только внутри этого же ответа (через
            # identify_returning_client), continuing_own_matter всё равно не
            # включится сейчас, только со следующего сообщения. Это ожидаемо:
            # intent классифицируется до старта стриминга, до вызова инструмента.
            intent_result = await intent_router.classify(
                conversation_history=history,
                has_core_context=bool(core_context),
            )
            funnel_context = intent_result.context_override or WEB_CONTEXT
            if core_context:
                funnel_context = f"{core_context}\n\n{funnel_context}"
            async for part in web_brain.generate_response_stream(
                history,
                funnel_context=funnel_context,
                tools=tools,
                tool_executor=assistant_tools.executor_for_web(state),
            ):
                chunks.append(part)
    except TimeoutError as error:
        logger.warning("Website assistant timed out")
        raise HTTPException(status_code=504, detail="Assistant timeout") from error

    if state.telegram_id is not None:
        _remember_verified_session(payload.session_id, state.telegram_id)

    reply = "".join(chunks).strip()
    if not reply:
        raise HTTPException(status_code=502, detail="Assistant returned an empty response")
    return ChatResponse(reply=reply[:5000])
