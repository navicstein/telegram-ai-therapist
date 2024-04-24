#!/usr/bin/env python
# pylint: disable=unused-argument

import asyncio
import os
import random
import time

from app.exceptions import UpgradeRequiredException
from app.gpt.chat import CompletionChat, MsgType
from app.logging import logger

from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.db import User, chat_crud, user_crud
from app.telegram_app.schedule_handler import greetings_job
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

start_message = """
🧠 Introducing the first AI health & mental coach, available 24/7.

🔄 Reframe negative thoughts
🚀 Take actionable steps to overcome challenges
💪 Emphasize physical fitness for mental well-being
🤝 Provide support throughout your day
🌟 Offer encouragement to uplift your mood

You can:
🎤 Send voice messages for responses in audio
💬 Send chat messages for text responses


💡 Feedback:
Have suggestions, ideas, or encountered bugs? Share them with me at https://linkedin.com/in/navicstein.
"""

upgrade_message = f"""You've reached your limit of messages. To continue our conversation, please select "Purchase" below.

{start_message}
"""


error_messages = [
    "Could you please resend your last message? I apologize for the inconvenience, but I seem to have had trouble processing it.",
    "My apologies, I'm having difficulty processing your previous message. Would you mind sending it again?",
    "Sorry about that. I'm unable to process your last message. Can you resend it, please?",
    "I apologize for the inconvenience. It seems I couldn't process your last message. Could you send it again?",
    "I'm sorry, but I couldn't quite understand your last message. Could you resend it for me, please?",
]


class TelegramAgentApp:
    def __init__(self) -> None:
        self.application = (
            Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN", "")).build()
        )

        self.application.add_handler(
            handler=CommandHandler(command="start", callback=self.start_command)
        )
        self.application.add_handler(
            handler=CommandHandler(command="reset", callback=self.reset)
        )
        self.application.add_handler(
            handler=CommandHandler(command="billing", callback=self.billing)
        )
        self.application.add_handler(
            handler=MessageHandler(filters=filters.ALL, callback=self.handle_message)
        )

        self.bot = self.application.bot

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Starts the conversation and asks you about your email to get started."""
        assert update.message is not None

        # TODO: ask the user about thier email address
        await update.message.reply_text(
            start_message,
        )

    async def reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Resets the conversation, deleting the previous user's messages."""
        assert update.message is not None

        # TODO: implement this
        await update.message.reply_text(
            "I've deleted your messages in my histoy, you may as well clear the history from telegram itself.",
        )

    async def billing(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    async def handle_cron(self):
        # jobstores = {
        #     "default": SQLAlchemyJobStore(url="sqlite:///jobs.sqlite"),
        # }
        scheduler = AsyncIOScheduler()
        # scheduler.configure(jobstores=jobstores)
        # scheduler.remove_all_jobs()

        scheduler.add_job(
            greetings_job,
            name="morning_greeting",
            id="morning_greeting",
            trigger="cron",
            hour=6,
        )

        scheduler.add_job(
            greetings_job,
            name="afternoon_greeting",
            id="afternoon_greeting",
            trigger="cron",
            hour=12,
        )

        scheduler.add_job(
            greetings_job,
            name="evening_greeting",
            id="evening_greeting",
            trigger="cron",
            hour=18,
        )

        scheduler.add_job(
            greetings_job,
            name="night_greeting",
            id="night_greeting",
            trigger="cron",
            hour=21,
        )

        scheduler.start()

    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
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
            await update.message.reply_text(
                text=upgrade_message, reply_markup=reply_markup
            )
        except Exception as e:
            logger.exception(e, exc_info=True)
            await update.message.reply_text(text=random.choice(error_messages))

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancels and ends the conversation."""
        assert update.message is not None, "update.message is None in cancel()"

        user = update.message.from_user
        logger.info("User %s canceled the conversation.", user.first_name)  # type: ignore
        await update.message.reply_text(
            "Bye! I hope we can talk again some day.",
            reply_markup=ReplyKeyboardRemove(),
        )

        return ConversationHandler.END

    def run_until_complete(self):
        asyncio.ensure_future(self.handle_cron())

        logger.info("Starting bot..")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
