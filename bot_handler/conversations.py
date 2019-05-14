from telegram.ext import (ConversationHandler, CallbackQueryHandler,
                          MessageHandler, Filters)
from bot_handler import response, reminders

act_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^(/act_[\d]+)'),
                                 response.act_task),
                  CallbackQueryHandler(reminders.reset_reminder,
                                       pattern='^(pr:[\d]+)$')],

    states=
    {
       response.CHOOSING_COMMAND: [
                           MessageHandler(
                                  Filters.regex('^Закрыть$'),
                                  response.close_task,
                                  pass_user_data=True),
                           MessageHandler(
                                  Filters.regex('^Взять$'),
                                  response.take_task,
                                  pass_user_data=True),
                           MessageHandler(Filters.regex(
                                  '^Установить срок|Изменить срок$'),
                                  response.update_deadline,
                                  pass_user_data=True),
                           MessageHandler(
                                  Filters.regex('^Удалить срок$'),
                                  response.rem_deadline,
                                  pass_user_data=True),
                           MessageHandler(
                                  Filters.regex('^Отказаться$'),
                                  response.ret_task,
                                  pass_user_data=True),
                           MessageHandler(Filters.regex(
                                  '^Отметить|Снять отметку$'),
                                  response.set_marked_status,
                                  pass_user_data=True),
                           MessageHandler(
                                  Filters.regex('^Создать напоминание$'),
                                  reminders.add_reminder,
                                  pass_user_data=True)
                           ],

       response.CHOOSING_DL_DATE: [
                           CallbackQueryHandler(
                                   response.deadline_cal_handler,
                                   pass_user_data=True)
                             ],

       response.CHOOSING_REMIND_DATE: [
                           CallbackQueryHandler(
                                   reminders.reminder_cal_handler,
                                   pass_user_data=True)
                             ],

       response.TYPING_DL_TIME: [
                            MessageHandler(Filters.regex(r'\d{1,2}:\d{2}'),
                                           response.get_dl_time,
                                           pass_user_data=True)
                             ],
       response.TYPING_REMIND_TIME: [
                            MessageHandler(Filters.text, reminders.get_rem_time,
                                           pass_user_data=True)
                             ]
    },
    fallbacks=[MessageHandler(Filters.regex('^Покинуть меню$'), response.done,
                              pass_user_data=True)],
    allow_reentry=True,
)
