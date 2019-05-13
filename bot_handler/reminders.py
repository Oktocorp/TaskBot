import html

import db_connector
import logger
from bot_handler.response import DEF_TZ, ParseMode


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

            context.bot.send_message(chat_id=rem['user_id'], text=resp_text,
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
