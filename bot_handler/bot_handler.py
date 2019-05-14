import os
import locale
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

import logger
from bot_handler import conversations, response, reminders


class BotHandler:
    def __init__(self):
        # Fetch token from Heroku config var
        token = os.environ['BOT_TOKEN']
        self.updater = Updater(token, use_context=True)

        # Get the dispatcher to register handlers
        self.dp = self.updater.dispatcher

        # Answer on different commands
        self.dp.add_handler(conversations.act_handler)
        self.dp.add_handler(CommandHandler('add', response.add_task))
        self.dp.add_handler(CommandHandler('close', response.close_task))
        self.dp.add_handler(CommandHandler('dl', response.update_deadline))
        self.dp.add_handler(CommandHandler(
            'free', lambda update, context: response.get_list(
                update, context, free_only=True)))
        self.dp.add_handler(CommandHandler('help', response.help_msg))
        self.dp.add_handler(CommandHandler('list', response.get_list))
        self.dp.add_handler(CommandHandler(
            'my', lambda update, context: response.get_list(
                update, context, for_user=True)))
        self.dp.add_handler(CommandHandler('return', response.ret_task))
        self.dp.add_handler(CommandHandler('start', response.start))
        self.dp.add_handler(CommandHandler('take', response.take_task))
        self.dp.add_handler(CommandHandler('no_dl', response.rem_deadline))
        self.dp.add_handler(CommandHandler('mark', response.set_marked_status))

        self.dp.add_handler(CallbackQueryHandler(
            reminders.close_btn, pattern=f'^({reminders.CLOSE_MSG})$'))

        # Log all errors
        self.log = logger.get_logger(__name__)
        self.dp.add_error_handler(self._error)

        # Set russian language
        self._localize()

    def _error(self, update, context):
        """Log Errors caused by Updates."""
        self.log.warning(f'Update "{update}" caused error "{context.error}"')

    def start(self):
        """Start the bot."""
        self.updater.start_polling()
        self.updater.job_queue.run_repeating(reminders.send_reminders,
                                             interval=60, first=0)
        self.updater.idle()

    def _localize(self):
        try:
            locale.setlocale(locale.LC_ALL, 'ru_RU.utf8')
        except locale.Error as err:
            self.log.warning('Unable to set locale', err)

