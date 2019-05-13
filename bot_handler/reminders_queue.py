import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler

import db_connector
import logger
from bot_handler.response import DEF_TZ, ParseMode, add_reminder

#  callback data on close message button
CLOSE_MSG = 'rem_msg'


def send_reminders(context):
    """ Sends messages with task reminders """
    try:
        handler = db_connector.DataBaseConnector()
        reminders = handler.get_reminders()
    except (ValueError, ConnectionError) as err:
        logger.get_logger(__name__).warning(
            'Unable to fetch reminders', err)
        return

    rems_to_close = list()
    for rem in reminders:
        try:
            task_mark = u'[\U0001F514]'
            resp_text = f'{task_mark} {html.escape(rem["task_text"])}\n'
            if rem['deadline']:
                dl_format = ' %a %d.%m'
                if rem['deadline'].second == 0:  # if time is not default
                    dl_format += ' %H:%M'
                dl = rem['deadline'].astimezone(DEF_TZ).strftime(dl_format)
                resp_text += f'<b>Срок:</b> <code>{dl}</code>'

            ret_data = f'pr:{rem["task_id"]}'
            keyboard = [[InlineKeyboardButton("Отложить",
                                              callback_data=ret_data),
                         InlineKeyboardButton("Закрыть",
                                              callback_data=CLOSE_MSG)]]
            markup = InlineKeyboardMarkup(keyboard)

            context.message = context.bot.send_message(
                 chat_id=rem['user_id'], text=resp_text,
                 reply_markup=markup,
                 parse_mode=ParseMode.HTML,
                 disable_web_page_preview=True)
            rems_to_close.append(rem['id'])
        except (ValueError, ConnectionError, KeyError) as err:
            logger.get_logger(__name__).warning(
                'Unable to process reminder', err)
    try:
        handler.close_reminders(rems_to_close)
    except (ValueError, ConnectionError) as err:
        logger.get_logger(__name__).warning('Unable to close reminders', err)


def reset_btn(update, context):
    try:
        data = update.callback_query.data
        task_id = int(data[data.find(':') + 1:])
        context.user_data['task id'] = task_id
        context.bot.answer_callback_query(update.callback_query.id)
        update.message = update.callback_query.message
        update.message.bot.delete_message(update.message.chat.id,
                                          update.message.message_id)
        return add_reminder(update, context)
    except (ValueError, KeyError, AttributeError) as err:
        logger.get_logger(__name__).warning('Unable to reset reminder', err)
        return ConversationHandler.END


def close_btn(update, context):
    try:
        update.message = update.callback_query.message
        update.message.bot.delete_message(update.message.chat.id,
                                          update.message.message_id)
    except (ValueError, AttributeError) as err:
        logger.get_logger(__name__).warning('Unable to remove message', err)
