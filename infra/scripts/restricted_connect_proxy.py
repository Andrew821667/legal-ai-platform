#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import contextlib
import logging
import os

LISTEN_HOST = os.getenv("CONNECT_PROXY_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.getenv("CONNECT_PROXY_LISTEN_PORT", "18081"))
UPSTREAM_HOST = os.getenv("CONNECT_PROXY_UPSTREAM_HOST", "127.0.0.1")
UPSTREAM_PORT = int(os.getenv("CONNECT_PROXY_UPSTREAM_PORT", "14809"))
ALLOWED_TARGETS = {
    item.strip().lower()
    for item in os.getenv("CONNECT_PROXY_ALLOWED_TARGETS", "").split(",")
    if item.strip()
}
HEADER_LIMIT = 16 * 1024
IDLE_TIMEOUT_SECONDS = int(os.getenv("CONNECT_PROXY_IDLE_TIMEOUT_SECONDS", "90"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("restricted-connect-proxy")


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    while chunk := await reader.read(64 * 1024):
        writer.write(chunk)
        await writer.drain()


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    upstream_writer: asyncio.StreamWriter | None = None
    try:
        request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
        if len(request) > HEADER_LIMIT:
            raise ValueError("request headers are too large")

        first_line = request.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        parts = first_line.split()
        if len(parts) != 3 or parts[0].upper() != "CONNECT" or parts[1].lower() not in ALLOWED_TARGETS:
            writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            await writer.drain()
            return

        upstream_reader, upstream_writer = await asyncio.open_connection(UPSTREAM_HOST, UPSTREAM_PORT)
        upstream_writer.write(request)
        await upstream_writer.drain()
        response = await asyncio.wait_for(upstream_reader.readuntil(b"\r\n\r\n"), timeout=15)
        if len(response) > HEADER_LIMIT or b" 200 " not in response.split(b"\r\n", 1)[0]:
            raise ConnectionError("upstream proxy rejected CONNECT")
        writer.write(response)
        await writer.drain()

        tasks = {
            asyncio.create_task(_pipe(reader, upstream_writer)),
            asyncio.create_task(_pipe(upstream_reader, writer)),
        }
        done, pending = await asyncio.wait(
            tasks,
            timeout=max(10, IDLE_TIMEOUT_SECONDS),
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            if error := task.exception():
                raise error
    except (TimeoutError, asyncio.IncompleteReadError, ConnectionError, OSError, ValueError) as exc:
        logger.warning("connection_failed error=%s", exc)
        if not writer.is_closing():
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            await writer.drain()
    finally:
        if upstream_writer is not None:
            upstream_writer.close()
            with contextlib.suppress(OSError):
                await upstream_writer.wait_closed()
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()


async def main() -> None:
    if not ALLOWED_TARGETS:
        raise RuntimeError("CONNECT_PROXY_ALLOWED_TARGETS is required")
    server = await asyncio.start_server(_handle, LISTEN_HOST, LISTEN_PORT)
    logger.info("listening address=%s:%s upstream=%s:%s", LISTEN_HOST, LISTEN_PORT, UPSTREAM_HOST, UPSTREAM_PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
