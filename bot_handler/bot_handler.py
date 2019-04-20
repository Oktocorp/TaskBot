import os
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

import logger
from . import answers


class BotHandler:
    def __init__(self):
        # Fetch token from Heroku config var
        token = os.environ['BOT_TOKEN']
        self.updater = Updater(token, use_context=True)

        # Get the dispatcher to register handlers
        self.dp = self.updater.dispatcher

        # Answer on different commands
        self.dp.add_handler(CommandHandler('start', answers.start))
        self.dp.add_handler(CommandHandler('help', answers.help_ans))
        self.dp.add_handler(CommandHandler('add', answers.add))
        self.dp.add_handler(CommandHandler('list', answers.get_list))
        self.dp.add_handler(CommandHandler('close', answers.close))

        # Generic message answer
        self.dp.add_handler(MessageHandler(Filters.text, answers.echo))

        # Log all errors
        self.log = logger.get_logger(__name__)
        self.dp.add_error_handler(self._error)

    def _error(self, update, context):
        """Log Errors caused by Updates."""
        self.log.warning(f'Update "{update}" caused error "{context.error}"')

    def start(self):
        """Start the bot."""
        self.updater.start_polling()

        self.updater.idle()
