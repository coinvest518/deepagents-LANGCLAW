"""Telegram integration for the Deep Agents CLI.

This module provides integrated Telegram support that runs within the same
process as the CLI, allowing users to interact with the agent via both the
chat interface and Telegram simultaneously.
"""

from __future__ import annotations

import asyncio
import html as _html_mod
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env so keys like TELEGRAM_BOT_TOKEN are available when running locally.
_repo_root = Path(__file__).resolve().parents[3]
load_dotenv(dotenv_path=_repo_root / ".env", override=False)

# Token detection: support multiple naming conventions.
BOT_TOKEN: str | None = (
    os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("TELEGRAM_YBOT_TOKEN")
)

# Owner chat ID (single authorised chat) and optional allow-list.
OWNER_CHAT_ID_STR: str | None = os.getenv("TELEGRAM_AI_OWNER_CHAT_ID")
ALWAYS_LISTEN: str | None = os.getenv("TELEGRAM_ALWAYS_LISTEN_CHAT_IDS")

_LOG_TRUNCATE = 50  # chars to show in log previews


def _parse_chat_id_list(val: str | None) -> list[int]:
    """Parse a comma-separated string of Telegram chat IDs.

    Args:
        val: Comma-separated integer string, e.g. ``"123,456"``.

    Returns:
        List of integer chat IDs; empty list when *val* is falsy or unparseable.
    """
    if not val:
        return []
    result: list[int] = []
    for part in val.split(","):
        part = part.strip()  # noqa: PLW2901
        if part:
            try:
                result.append(int(part))
            except ValueError:
                logger.warning("Invalid chat ID in allow-list: %r", part)
    return result


OWNER_CHAT_ID: int | None = None
if OWNER_CHAT_ID_STR:
    try:
        OWNER_CHAT_ID = int(OWNER_CHAT_ID_STR)
    except ValueError:
        logger.exception(
            "TELEGRAM_AI_OWNER_CHAT_ID must be an integer, got %r",
            OWNER_CHAT_ID_STR,
        )

ALLOWED_CHAT_IDS: list[int] = _parse_chat_id_list(ALWAYS_LISTEN)

POLL_INTERVAL: float = float(os.getenv("POLL_INTERVAL", "1.5"))
MAX_HISTORY: int = int(os.getenv("TELEGRAM_MAX_HISTORY", "12"))

BASE_URL: str = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

# Commands that route to specific subagents.
COMMAND_SUBAGENT_MAP: dict[str, str] = {
    "/research": "research",
    "/code": "coder",
    "/review": "reviewer",
    "/agent": "general",
}


class TelegramIntegration:
    """Integrated Telegram gateway that works with the CLI's agent and session state."""

    def __init__(self, app: Any) -> None:  # noqa: ANN401
        """Initialize Telegram integration with CLI app reference.

        Args:
            app: The running :class:`DeepAgentsApp` instance used to forward
                incoming Telegram messages into the agent loop.
        """
        self.app = app
        self.running = True
        self.offset: int | None = None
        self.chat_history: dict[int, list[dict[str, str]]] = {}
        # chat_id → placeholder message_id sent while the agent is thinking
        self._pending_placeholders: dict[int, int] = {}
        # chat_id → asyncio.Task keeping the typing indicator alive
        self._typing_tasks: dict[int, asyncio.Task] = {}

    def is_chat_allowed(self, chat_id: int) -> bool:  # noqa: PLR6301
        """Return ``True`` if *chat_id* is permitted to interact with the bot.

        Args:
            chat_id: Telegram chat ID to check.

        Returns:
            ``True`` when the chat is allowed.
        """
        if OWNER_CHAT_ID is not None and chat_id != OWNER_CHAT_ID:
            return chat_id in ALLOWED_CHAT_IDS
        return True

    def send_message(self, chat_id: int, text: str) -> None:  # noqa: PLR6301
        """Send *text* to *chat_id* via the Telegram Bot API.

        Args:
            chat_id: Destination Telegram chat ID.
            text: Message text to send.
        """
        if not BOT_TOKEN:
            return
        try:
            requests.post(
                f"{BASE_URL}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=10,
            )
        except Exception:
            logger.warning(
                "Failed to send Telegram message to chat_id=%d", chat_id, exc_info=True
            )

    # ------------------------------------------------------------------
    # Rich messaging helpers
    # ------------------------------------------------------------------

    def send_message_html(  # noqa: PLR6301
        self,
        chat_id: int,
        html: str,
    ) -> int | None:
        """Send an HTML-formatted message and return the Telegram message ID.

        Args:
            chat_id: Destination Telegram chat ID.
            html: Message body using Telegram HTML entities
                (``<b>``, ``<i>``, ``<code>``, ``<pre>``).

        Returns:
            The ``message_id`` of the sent message, or ``None`` on failure.
        """
        if not BOT_TOKEN:
            return None
        try:
            resp = requests.post(
                f"{BASE_URL}/sendMessage",
                json={"chat_id": chat_id, "text": html, "parse_mode": "HTML"},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception:
            logger.warning(
                "Failed to send HTML message to chat_id=%d", chat_id, exc_info=True
            )
            return None
        else:
            return resp.json().get("result", {}).get("message_id")

    def send_chat_action(  # noqa: PLR6301
        self,
        chat_id: int,
        action: str = "typing",
    ) -> None:
        """Send a chat action (e.g. ``typing``) to show a status indicator.

        The indicator is visible for up to 5 seconds or until the next message
        arrives from the bot. Call every ~4 seconds for long operations.

        Args:
            chat_id: Target Telegram chat ID.
            action: Action string — ``"typing"`` is the most common.
        """
        if not BOT_TOKEN:
            return
        try:
            requests.post(
                f"{BASE_URL}/sendChatAction",
                json={"chat_id": chat_id, "action": action},
                timeout=5,
            )
        except Exception:
            logger.debug("sendChatAction failed for chat_id=%d", chat_id, exc_info=True)

    def edit_message(  # noqa: PLR6301
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str | None = "HTML",
    ) -> bool:
        """Edit the text of a previously sent bot message.

        Args:
            chat_id: Chat containing the message.
            message_id: ID of the message to edit.
            text: New message text (max 4096 chars).
            parse_mode: ``"HTML"`` or ``"MarkdownV2"`` (default ``"HTML"``).

        Returns:
            ``True`` on success, ``False`` on failure.
        """
        if not BOT_TOKEN:
            return False
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            resp = requests.post(
                f"{BASE_URL}/editMessageText",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
        except Exception:
            logger.debug(
                "editMessageText failed for message_id=%d", message_id, exc_info=True
            )
            return False
        else:
            return True

    def send_question_with_keyboard(  # noqa: PLR6301
        self,
        chat_id: int,
        text: str,
        choices: list[str] | None = None,
    ) -> int | None:
        """Send a question message with optional inline keyboard buttons.

        Used for ask_user interrupts from the agent.  Each choice becomes its
        own button row.  Returns the Telegram message_id or ``None`` on failure.

        Args:
            chat_id: Destination chat ID.
            text: HTML-formatted question text.
            choices: Optional list of button labels (each is also the callback data).

        Returns:
            message_id of the sent message, or ``None`` on failure.
        """
        if not BOT_TOKEN:
            return None
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if choices:
            payload["reply_markup"] = {
                "inline_keyboard": [[{"text": c, "callback_data": c[:64]}] for c in choices]
            }
        try:
            resp = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json().get("result", {}).get("message_id")
        except Exception:
            logger.warning(
                "send_question_with_keyboard failed for chat_id=%d", chat_id, exc_info=True
            )
            return None

    def answer_callback_query(self, query_id: str, text: str = "") -> None:  # noqa: PLR6301
        """Answer a callback query to dismiss the loading indicator on an inline button.

        Must be called within 10 seconds of receiving the callback_query update.

        Args:
            query_id: The ``id`` field from the callback_query update.
            text: Optional short notification to show the user (up to 200 chars).
        """
        if not BOT_TOKEN:
            return
        try:
            requests.post(
                f"{BASE_URL}/answerCallbackQuery",
                json={"callback_query_id": query_id, "text": text},
                timeout=5,
            )
        except Exception:
            logger.debug("answerCallbackQuery failed for query_id=%s", query_id, exc_info=True)

    # ------------------------------------------------------------------
    # Markdown → Telegram HTML conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _md_to_telegram_html(text: str) -> str:
        """Convert agent markdown output to Telegram HTML.

        Handles fenced code blocks, inline code, bold, italic, and headers.
        All non-code text has HTML special characters escaped before formatting
        is applied, so the agent output can contain ``<``, ``>``, ``&`` safely.

        Args:
            text: Raw agent response (markdown).

        Returns:
            Telegram-safe HTML string.
        """
        result: list[str] = []
        # Split on fenced code blocks so they can be handled separately.
        segments = re.split(r"(```[\s\S]*?```)", text)

        for seg in segments:
            if seg.startswith("```"):
                # Strip the opening/closing fences and optional language id.
                body = re.sub(r"^```\w*\n?", "", seg)
                body = re.sub(r"```$", "", body)
                result.append(f"<pre><code>{_html_mod.escape(body)}</code></pre>")
            else:
                # Escape HTML, then apply inline markdown patterns.
                out = _html_mod.escape(seg)
                # Inline code: `code`
                out = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", out)
                # Bold: **text**
                out = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", out)
                # Italic: *text* (single asterisk only)
                italic_re = r"(?<!\*)\*(?!\*)([^*\n]+)(?<!\*)\*(?!\*)"
                out = re.sub(italic_re, r"<i>\1</i>", out)
                # Markdown headers → bold
                out = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", out, flags=re.MULTILINE)
                result.append(out)

        return "".join(result)

    @staticmethod
    def _split_message(text: str, max_len: int = 4000) -> list[str]:
        """Split *text* into chunks that fit within Telegram's message limit.

        Tries to split on paragraph breaks first, then falls back to hard cuts
        at *max_len* characters.

        Args:
            text: Text to split (may be HTML).
            max_len: Maximum characters per chunk (Telegram hard limit is 4096).

        Returns:
            List of non-empty string chunks.
        """
        if len(text) <= max_len:
            return [text]

        chunks: list[str] = []
        current = ""
        for paragraph in text.split("\n\n"):
            candidate = f"{current}\n\n{paragraph}" if current else paragraph
            if len(candidate) <= max_len:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(paragraph) > max_len:
                    # Hard-cut oversized paragraphs.
                    remaining = paragraph
                    while remaining:
                        chunks.append(remaining[:max_len])
                        remaining = remaining[max_len:]
                    current = ""
                else:
                    current = paragraph

        if current:
            chunks.append(current)

        return chunks or [text]

    # ------------------------------------------------------------------
    # Thinking indicator + reply delivery
    # ------------------------------------------------------------------

    async def _start_thinking(self, chat_id: int) -> None:
        """Show a ``⏳ Working on it…`` placeholder and keep typing alive.

        Sends ``sendChatAction`` + an initial placeholder message so the user
        gets immediate feedback, then schedules :meth:`_keep_typing` to refresh
        the typing indicator every 4 seconds until the reply arrives.

        Args:
            chat_id: Telegram chat waiting for the agent response.
        """
        await asyncio.to_thread(self.send_chat_action, chat_id)
        placeholder_id = await asyncio.to_thread(
            self.send_message_html,
            chat_id,
            "⏳ <i>Working on it…</i>",
        )
        if placeholder_id:
            self._pending_placeholders[chat_id] = placeholder_id
            self._typing_tasks[chat_id] = asyncio.create_task(
                self._keep_typing(chat_id)
            )

    async def _keep_typing(self, chat_id: int) -> None:
        """Refresh the typing indicator every 4 s while the agent is running.

        The Telegram typing indicator expires after 5 seconds, so we re-send
        it slightly before that to keep the UX uninterrupted.

        Args:
            chat_id: Chat to keep the indicator active in.
        """
        try:
            while chat_id in self._pending_placeholders:
                await asyncio.sleep(4)
                if chat_id in self._pending_placeholders:
                    await asyncio.to_thread(self.send_chat_action, chat_id)
        except asyncio.CancelledError:
            pass

    def deliver_reply(self, chat_id: int, content: str) -> None:
        """Deliver the agent response to Telegram.

        Cancels the typing keepalive, converts the markdown response to
        Telegram HTML, then either edits the ``⏳`` placeholder or sends a
        new message. Runs the network I/O in a daemon thread so this method
        is safe to call from a synchronous context on the asyncio event loop.

        Args:
            chat_id: Telegram chat to reply to.
            content: Raw agent response text (markdown).
        """
        task = self._typing_tasks.pop(chat_id, None)
        if task is not None:
            task.cancel()

        placeholder_id = self._pending_placeholders.pop(chat_id, None)

        t = threading.Thread(
            target=self._deliver_reply_sync,
            args=(chat_id, placeholder_id, content),
            daemon=True,
        )
        t.start()

    def _deliver_reply_sync(
        self,
        chat_id: int,
        placeholder_id: int | None,
        content: str,
    ) -> None:
        """Synchronous delivery of the formatted reply (runs in a thread).

        Converts markdown to HTML, splits long responses, then edits the
        placeholder for the first chunk and sends new messages for the rest.

        Args:
            chat_id: Telegram chat to reply to.
            placeholder_id: Message ID of the ``⏳`` placeholder, if any.
            content: Raw agent response text (markdown).
        """
        formatted = self._md_to_telegram_html(content)
        chunks = self._split_message(formatted)

        for i, chunk in enumerate(chunks):
            if i == 0 and placeholder_id:
                # Replace the placeholder in-place.
                ok = self.edit_message(
                    chat_id, placeholder_id, chunk, parse_mode="HTML"
                )
                if not ok:
                    logger.warning("edit_message failed for chat_id=%d, sending new message", chat_id)
                    self.send_message_html(chat_id, chunk)
            else:
                self.send_message_html(chat_id, chunk)
        logger.info("Reply delivered to chat_id=%d (%d chunk(s))", chat_id, len(chunks))

    def download_telegram_file(self, file_id: str, dest_dir: Path) -> Path | None:  # noqa: PLR6301
        """Download a Telegram file to *dest_dir* and return the local path.

        Args:
            file_id: Telegram file identifier.
            dest_dir: Local directory to save the file into.

        Returns:
            Path to the downloaded file, or ``None`` on failure.
        """
        if not BOT_TOKEN:
            return None
        try:
            resp = requests.get(
                f"{BASE_URL}/getFile",
                params={"file_id": file_id},
                timeout=10,
            )
            resp.raise_for_status()
            file_path: str = resp.json()["result"]["file_path"]

            download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            dest_dir.mkdir(parents=True, exist_ok=True)
            local_path = dest_dir / Path(file_path).name

            # Avoid collisions by appending a numeric suffix.
            counter = 1
            while local_path.exists():
                stem = local_path.stem
                local_path = dest_dir / f"{stem}-{counter}{local_path.suffix}"
                counter += 1

            file_resp = requests.get(download_url, timeout=60)
            file_resp.raise_for_status()
            local_path.write_bytes(file_resp.content)
        except Exception:
            logger.warning(
                "Failed to download Telegram file %r", file_id, exc_info=True
            )
            return None
        else:
            return local_path
        return None  # unreachable, satisfies type checker

    def extract_file_message(self, msg: dict, download_dir: Path) -> str | None:
        """Download any attached media and return a descriptive user message.

        Args:
            msg: Raw Telegram message dict.
            download_dir: Directory to save downloaded media into.

        Returns:
            A human-readable string describing the attachment, or ``None`` if
            there is no supported media in *msg*.
        """
        file_info: tuple[str, str] | None = None

        if "voice" in msg:
            file_info = ("voice", msg["voice"]["file_id"])
        elif "audio" in msg:
            file_info = ("audio", msg["audio"]["file_id"])
        elif "document" in msg:
            file_info = ("document", msg["document"]["file_id"])
        elif "photo" in msg:
            photo_sizes = msg["photo"]
            if photo_sizes:
                file_info = ("photo", photo_sizes[-1]["file_id"])

        if not file_info:
            return None

        file_type, file_id = file_info
        local_path = self.download_telegram_file(file_id, download_dir)
        if not local_path:
            return f"[Received {file_type} file, but download failed]"
        return f"[Received {file_type} file and saved to {local_path}]"

    def parse_command(self, text: str) -> tuple[str, str]:  # noqa: PLR6301
        """Split *text* into a command token and the remaining body.

        Args:
            text: Raw Telegram message text.

        Returns:
            ``(command, body)`` where *command* is the leading ``/cmd`` token
            (lower-cased) or an empty string when *text* is not a command.
        """
        stripped = text.strip()
        if not stripped.startswith("/"):
            return "", stripped
        parts = stripped.split(None, 1)
        cmd = parts[0].lower()
        body = parts[1].strip() if len(parts) > 1 else ""
        return cmd, body

    def handle_telegram_update(self, update: dict) -> None:
        """Dispatch a single Telegram update to the agent.

        Args:
            update: Raw Telegram Update object.
        """
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return

        chat_id: int = msg["chat"]["id"]

        if not self.is_chat_allowed(chat_id):
            logger.debug("Ignoring message from disallowed chat_id=%d", chat_id)
            return

        # Download any attached media and append a description to the text.
        download_dir = Path.home() / ".deepagents" / "telegram" / "downloads"
        attachment_text = self.extract_file_message(msg, download_dir)

        text: str = msg.get("text", "")
        if attachment_text:
            text = f"{text}\n\n{attachment_text}" if text else attachment_text

        if not text:
            return

        cmd, body = self.parse_command(text)

        # Built-in commands that don't reach the agent.
        if cmd in {"/start", "/help"}:
            self.send_message(
                chat_id,
                "🤖 FDWA AI Agent\n\n"
                "Commands:\n"
                "/start, /help — Show this help\n"
                "/reset — Clear conversation history\n"
                "/mode — List agent modes\n"
                "/mode content — Switch to content writer\n"
                "/mode researcher — Switch to deep research mode\n"
                "/mode social — Switch to social media manager\n"
                "/mode ralph — Switch to autonomous builder\n"
                "/mode coder — Switch to coding specialist\n"
                "/mode default — Reset to default FDWA agent\n\n"
                "After /mode <name>, reply /yes to confirm or /no to cancel.\n\n"
                "Send any text to interact with the agent.",
            )
            return

        if cmd == "/reset":
            self.chat_history.pop(chat_id, None)
            self.send_message(chat_id, "Conversation history cleared.")
            return

        message_input = body if cmd in COMMAND_SUBAGENT_MAP else text

        user = msg.get("from", {})
        username: str = user.get("username") or user.get("first_name") or "<unknown>"
        preview = message_input[:_LOG_TRUNCATE]
        ellipsis_ = "..." if len(message_input) > _LOG_TRUNCATE else ""
        logger.info("[telegram] %s (chat_id=%d): %s%s", username, chat_id, preview, ellipsis_)  # noqa: E501

        if self.app and hasattr(self.app, "_handle_external_message"):
            try:
                cid = chat_id
                text_to_send = message_input
                self.app.call_after_refresh(
                    lambda: asyncio.create_task(
                        self.app._handle_external_message(
                            text_to_send,
                            source="telegram",
                            telegram_chat_id=cid,
                        )
                    )
                )
            except Exception:
                logger.exception("Failed to forward message to CLI")
            else:
                return

        self._handle_local_message(chat_id, message_input, cmd)

    def _handle_local_message(self, chat_id: int, message_input: str, cmd: str) -> None:  # noqa: ARG002
        """Reply with a fallback when the CLI app is not reachable.

        Args:
            chat_id: Telegram chat to reply to.
            message_input: Original user message.
            cmd: Parsed command token (unused, reserved for future routing).
        """
        self.send_message(
            chat_id,
            "CLI integration is not available. "
            "Please use the CLI chat interface for full functionality.",
        )

    def _fetch_updates(self, params: dict) -> dict:  # noqa: PLR6301
        """Fetch pending Telegram updates (synchronous — runs in a thread).

        Args:
            params: Query parameters for ``getUpdates``.

        Returns:
            Parsed JSON response dict.
        """
        resp = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=70)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    async def poll_loop(self) -> None:
        """Main long-poll loop — runs as a background asyncio task."""
        if not BOT_TOKEN:
            logger.warning("No Telegram bot token found; integration disabled.")
            return

        logger.info(
            "Telegram integration started (owner_chat_id=%s, allowed=%s)",
            OWNER_CHAT_ID or "not set",
            ALLOWED_CHAT_IDS or "not set",
        )

        while self.running:
            try:
                params: dict = {"timeout": 60}
                if self.offset is not None:
                    params["offset"] = self.offset

                # Run the blocking HTTP long-poll in a thread so it doesn't
                # stall the asyncio event loop.
                data = await asyncio.to_thread(self._fetch_updates, params)

                for update in data.get("result", []):
                    self.offset = update["update_id"] + 1
                    try:
                        self.handle_telegram_update(update)
                    except Exception:
                        logger.exception("Error handling Telegram update")

            except requests.exceptions.ReadTimeout:
                continue  # Normal long-poll expiry — just restart.
            except Exception:
                logger.exception("Telegram polling error")
                await asyncio.sleep(2)

            await asyncio.sleep(POLL_INTERVAL)

    def start(self) -> None:
        """Schedule :meth:`poll_loop` as a background asyncio task."""
        if not BOT_TOKEN:
            logger.warning("No Telegram bot token found; integration disabled.")
            return
        # Store the task reference to prevent garbage collection.
        self._poll_task = asyncio.create_task(self.poll_loop())
        logger.info("Telegram integration started in background.")


def is_telegram_enabled() -> bool:
    """Return ``True`` when a Telegram bot token is configured.

    Returns:
        ``True`` if ``BOT_TOKEN`` is set.
    """
    return bool(BOT_TOKEN)


def get_telegram_status() -> str:
    """Return a human-readable status string for the Telegram integration.

    Returns:
        Multi-line status string.
    """
    if not BOT_TOKEN:
        return "Telegram integration: Disabled (no bot token)"

    parts = ["Telegram integration: Enabled"]
    if OWNER_CHAT_ID:
        parts.append(f"Owner chat ID: {OWNER_CHAT_ID}")
    if ALLOWED_CHAT_IDS:
        parts.append(f"Allowed chats: {', '.join(map(str, ALLOWED_CHAT_IDS))}")
    return "\n".join(parts)
