import logging
import os
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

from . import answers


class BotHandler:
    def __init__(self):
        # Fetch token from Heroku config var
        token = os.environ['BOT_TOKEN']
        self.updater = Updater(token, use_context=True)

        # Get the dispatcher to register handlers
        self.dp = self.updater.dispatcher

        # Answer on different commands
        self.dp.add_handler(CommandHandler("start", answers.start))
        self.dp.add_handler(CommandHandler("help", answers.help_ans))

        # Generic message answer
        self.dp.add_handler(MessageHandler(Filters.text, answers.echo))

        # Log all errors
        self.logger = self._get_logger()
        self.dp.add_error_handler(self._error)

    @staticmethod
    def _get_logger():
        """Set stderr StreamHandler logger"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(format=log_format, level=logging.INFO)
        logger = logging.getLogger(__name__)
        return logger

    def _error(self, update, context):
        """Log Errors caused by Updates."""
        self.logger.warning(f'Update "{update}" caused error "{context.error}"')

    def start(self):
        """Start the bot."""
        self.updater.start_polling()

        self.updater.idle()
