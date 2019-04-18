import os
import psycopg2

import logger


class DataBaseConnector:
    def __init__(self):
        self._db_url = os.environ['DATABASE_URL']
        self._log = logger.get_logger(__name__)

    @staticmethod
    def _close_conn(conn):
        """Ensures the connection is closed"""
        if conn:
            conn.cursor.close()
            conn.close()

    def _exec_success(self, *args):
        """Tries to execute SQL query"""
        conn = None
        try:
            conn = psycopg2.connect(self._db_url, sslmode='require')
        except (Exception, psycopg2.DatabaseError) as err:
            self._log.warning('Unable to connect to the DataBase', err)
            self._close_conn(conn)
            return 0

        cursor = conn.cursor()
        try:
            cursor.execute(*args)
            conn.commit()
        except (Exception, psycopg2.DatabaseError) as err:
            self._log.warning('Error while executing SQL query', err)
            self._close_conn(conn)
            return 0

        return 1

    def add_task(self, chat_id, creator_id, task_text, marked=False,
                 deadline=None, workers=None):
        """
        Adds new task to the database.
        In case of error raises RuntimeError
        """

        sql_str = '''
        INSERT INTO tasks (chat_id, creator_id, task_text,
        marked, deadline, workers) VALUES (%s, %s, %s, %s, %s, %s)
        '''
        sql_vals = (chat_id, creator_id, task_text, marked, deadline, workers)

        if not self._exec_success(sql_str, sql_vals):
            raise RuntimeError('Unable to add task to the DataBase')

