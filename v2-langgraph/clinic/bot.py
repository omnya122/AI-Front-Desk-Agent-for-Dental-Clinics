"""Telegram transport: long polling, update_id dedup, typing indicator, outbox delivery, error handling."""
import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from . import db
from .config import get_settings
from .graph import build_graph
from .i18n import detect_lang, t

log = logging.getLogger(__name__)


async def _post_init(app: Application) -> None:
    pool = await db.init_pool()
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()  # creates the LangGraph checkpoint tables on first run
    await db.housekeeping()
    app.bot_data["graph"] = build_graph(checkpointer)
    log.info("Graph ready")


async def _post_shutdown(app: Application) -> None:
    await db.close_pool()


async def _send(bot, outbox: list[dict]) -> None:
    for msg in outbox:
        markup = None
        if msg.get("buttons"):
            markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton(b["text"], callback_data=b["data"]) for b in row] for row in msg["buttons"]]
            )
        try:
            await bot.send_message(chat_id=msg["chat_id"], text=msg["text"], reply_markup=markup)
        except Exception:
            log.exception("Failed to send message to %s", msg["chat_id"])


async def _run_turn(context: ContextTypes.DEFAULT_TYPE, update: Update, payload: dict) -> None:
    chat_id = update.effective_chat.id
    user = update.effective_user
    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
    try:
        result = await context.application.bot_data["graph"].ainvoke(
            {"chat_id": chat_id, "update_id": update.update_id, "username": user.username if user else None,
             "text": "", "callback_data": "", **payload},
            {"configurable": {"thread_id": str(chat_id)}},
        )
    except Exception as exc:
        # Equivalent of the n8n "Error Workflow": graceful message to the patient + alert to staff.
        log.exception("Graph run failed for chat %s", chat_id)
        lang = detect_lang(payload.get("text", ""))
        await _send(context.bot, [{"chat_id": chat_id, "text": t("error", lang)}])
        staff = get_settings().staff_chat_id
        if staff:
            await _send(context.bot, [{
                "chat_id": staff,
                "text": f"⚠️ Bot error for chat_id {chat_id}: {type(exc).__name__}: {str(exc)[:300]}",
            }])
        return
    await _send(context.bot, result["outbox"])


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await db.mark_update_seen(update.update_id):
        return
    text = update.message.text
    await _run_turn(context, update, {"kind": "text" if text else "non_text", "text": text or ""})


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # stop the button spinner
    if not await db.mark_update_seen(update.update_id):
        return
    try:
        await query.edit_message_reply_markup(reply_markup=None)  # one tap per button set
    except Exception:
        log.debug("Could not clear keyboard", exc_info=True)
    await _run_turn(context, update, {"kind": "callback", "callback_data": query.data or ""})


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    s = get_settings()
    if not s.telegram_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set (see .env.example)")
    app = Application.builder().token(s.telegram_token).post_init(_post_init).post_shutdown(_post_shutdown).build()
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE, on_message))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.run_polling(allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY])
