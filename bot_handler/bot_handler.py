import os
import locale
from telegram.ext import (Updater, CommandHandler, RegexHandler,
    CallbackQueryHandler, ConversationHandler, MessageHandler, Filters)
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
        self.dp.add_handler(CommandHandler('add', response.add_task))
        self.dp.add_handler(CommandHandler('close', response.close_task))
        self.dp.add_handler(CommandHandler('dl', response.update_deadline))
        self.dp.add_handler(CallbackQueryHandler(response.inline_calendar_handler, pass_user_data=True))
        self.dp.add_handler(CommandHandler('time', response.get_time))
        self.dp.add_handler(CommandHandler('help', response.help_msg))
        self.dp.add_handler(CommandHandler('list', response.get_list))
        self.dp.add_handler(CommandHandler('return', response.ret_task))
        self.dp.add_handler(CommandHandler('start', response.start))
        self.dp.add_handler(CommandHandler('take', response.take_task))
        self.dp.add_handler(CommandHandler('no_dl', response.rem_deadline))
        # self.dp.add_handler(CommandHandler('act', response.act_task))

        CHOOSING, TYPING_REPLY, TYPING_CHOICE = range(3)

        self.dp.add_handler(ConversationHandler(
            entry_points=[CommandHandler('act', response.act_task)],

            states=
            {
                CHOOSING: [RegexHandler('^Закрыть$',
                                        response.close_task,
                                        pass_user_data=True),
                           RegexHandler('^Взять$',
                                        response.take_task,
                                        pass_user_data=True),
                           RegexHandler('^Установить/изменить срок$',
                                        response.update_deadline,
                                        pass_user_data=True),
                           RegexHandler('^Удалить срок$',
                                        response.rem_deadline,
                                        pass_user_data=True)
                       ],

                # TYPING_CHOICE: [MessageHandler(Filters.text,
                #                                response.regular_choice,
                #                                pass_user_data=True),
                #             ],
                #
                # TYPING_REPLY: [MessageHandler(Filters.text,
                #                               response.received_information,
                #                               pass_user_data=True),
                #            ],
            },
            fallbacks=[RegexHandler('^Отмена$', response.done, pass_user_data=True)]
        ))

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
        self.updater.idle()

    def _localize(self):
        try:
            locale.setlocale(locale.LC_ALL, 'ru_RU.utf8')
        except locale.Error as err:
            self.log.warning('Unable to set locale', err)

