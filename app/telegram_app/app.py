#!/usr/bin/env python
# pylint: disable=unused-argument

import os
from app.exceptions import UpgradeRequiredException
from app.gpt.chat import CompletionChat, MsgType
from app.logging import logger

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.db import User, user_crud


start_message = """
🧠 Introducing the first AI health & mental coach, available 24/7.

✅ Reframe negative thoughts
✅ Take actionable steps to overcome challenges
✅ Emphasize physical fitness for mental well-being
✅ Provide support throughout your day
✅ Offer encouragement to uplift your mood

You can:
🎤 Send voice messages for responses in audio
💬 Send chat messages for text responses


💡 Feedback:
Have suggestions, ideas, or encountered bugs? Share them with us at https://linkedin.com/in/navicstein.
"""

upgrade_message = f"""You've reached your limit of messages. To continue our conversation, please select "Purchase" below.

{start_message}
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Starts the conversation and asks you about your email to get started."""
    assert update.message is not None

    # TODO: ask the user about thier email address
    await update.message.reply_text(
        start_message,
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resets the conversation, deleting the previous user's messages."""
    assert update.message is not None

    # TODO: implement this
    await update.message.reply_text(
        "I've deleted your messages in my histoy, you may as well clear the history from telegram itself.",
    )


async def billing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download all your invoices."""
    assert update.message is not None

    # TODO: implement this

    keyboard = [
        [
            InlineKeyboardButton(
                "⏬ Download invoices",
                url="https://linkedin.com/in/navicstein",
            ),
            InlineKeyboardButton(
                "🚫 Cancel Subscription",
                url="https://linkedin.com/in/navicstein",
            ),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Choose an option:", reply_markup=reply_markup)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the user message"""
    if not update.message:
        return

    assert update.effective_user is not None

    if update.message.audio:
        await update.message.reply_text(
            text="You need to send me a voice note and not an audio file."
        )
        return

    data = update.message.text
    msg_type: MsgType = "text"

    try:
        user = user_crud.get(update.effective_user.id)
        if not user:
            user = user_crud.create(
                User(
                    id=update.effective_user.id,
                    full_name=update.effective_user.full_name,
                    telegram_id=update.effective_user.id,
                )
            )

        chat = CompletionChat(user=user)

        if update.message.voice:
            msg_type = "voice"
            data = await update.message.voice.get_file()

        if not data:
            return

        response = await chat.forward(data, msg_type=msg_type)

        if isinstance(response, bytes):
            await update.message.reply_voice(voice=response)
        elif isinstance(response, str):
            await update.message.reply_text(text=response)
        else:
            raise Exception(f"Unexpected AI response type: {type(response)}")

    except UpgradeRequiredException:
        keyboard = [
            [
                InlineKeyboardButton(
                    # TODO: add payment link
                    "🔥Purchase",
                    url="https://paystack.com/pay/gvasuwrv-l",
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text=upgrade_message, reply_markup=reply_markup)
    except Exception as e:
        logger.exception(e, exc_info=True)
        await update.message.reply_text(
            text="I'm sorry, I could'nt process your last message, can you resend it?"
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    assert update.message is not None, "update.message is None in cancel()"

    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)  # type: ignore
    await update.message.reply_text(
        "Bye! I hope we can talk again some day.", reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


def telegram_app() -> None:
    """Run the bot."""
    application = (
        Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN", "")).build()
    )

    application.add_handler(handler=CommandHandler(command="start", callback=start))
    application.add_handler(handler=CommandHandler(command="reset", callback=reset))
    application.add_handler(handler=CommandHandler(command="billing", callback=billing))
    application.add_handler(
        handler=MessageHandler(filters=filters.ALL, callback=handle_message)
    )

    application.run_polling(allowed_updates=Update.ALL_TYPES)
