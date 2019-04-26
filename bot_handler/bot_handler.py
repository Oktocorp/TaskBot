import os
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

import logger
from . import response


class BotHandler:
    def __init__(self):
        # Fetch token from Heroku config var
        token = os.environ['BOT_TOKEN']
        self.updater = Updater(token, use_context=True)

        # Get the dispatcher to register handlers
        self.dp = self.updater.dispatcher

        # Answer on different commands
        self.dp.add_handler(CommandHandler('add', response.add))
        self.dp.add_handler(CommandHandler('close', response.close))
        self.dp.add_handler(CommandHandler('dl', response.update_deadline))
        self.dp.add_handler(CallbackQueryHandler(response.inline_calendar_handler, pass_user_data=True))
        self.dp.add_handler(CommandHandler('time', response.get_time))
        self.dp.add_handler(CommandHandler('help', response.help_msg))
        self.dp.add_handler(CommandHandler('list', response.get_list))
        self.dp.add_handler(CommandHandler('start', response.start))

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
