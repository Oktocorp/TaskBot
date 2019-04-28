from telegram.ext import ConversationHandler, MessageHandler, Filters
from bot_handler import response

_CHOOSING, _TYPING_REPLY, _TYPING_CHOICE = range(3)

act_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^(/act_[\d]+)$'),
                                 response.act_task)],

    states=
    {
        _CHOOSING: [MessageHandler(Filters.regex('^Закрыть$'),
                                   response.close_task,
                                   pass_user_data=True),
                    MessageHandler(Filters.regex('^Взять$'),
                                   response.take_task,
                                   pass_user_data=True),
                    MessageHandler(Filters.regex('^Установить/изменить срок$'),
                                   response.update_deadline,
                                   pass_user_data=True),
                    MessageHandler(Filters.regex('^Удалить срок$'),
                                   response.rem_deadline,
                                   pass_user_data=True),
                    MessageHandler(Filters.regex('^Отказаться$'),
                                   response.ret_task,
                                   pass_user_data=True)
                    ],

        # _TYPING_CHOICE: [MessageHandler(Filters.text,
        #                                response.regular_choice,
        #                                pass_user_data=True),
        #             ],
        #
        # _TYPING_REPLY: [MessageHandler(Filters.text,
        #                               response.received_information,
        #                               pass_user_data=True),
        #            ],
    },
    fallbacks=[MessageHandler(Filters.regex('^Отмена$'), response.done,
                              pass_user_data=True)]
)
