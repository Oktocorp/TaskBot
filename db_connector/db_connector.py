import os
import psycopg2

import logger


class DataBaseConnector:
    def __init__(self):
        self._db_url = os.environ['DATABASE_URL']
        self._log = logger.get_logger(__name__)

    @staticmethod
    def _close_conn(conn, cur=None):
        """Ensures the connection is closed"""
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

    def _exec_success(self, *args):
        """
        Tries to execute SQL query
        """
        conn = None
        try:
            conn = psycopg2.connect(self._db_url, sslmode='require')
        except (Exception, psycopg2.DatabaseError) as err:
            self._log.warning('Unable to connect to the DataBase', err)
            self._close_conn(conn)
            return False

        cur = conn.cursor()
        try:
            cur.execute(*args)
            conn.commit()
        except (Exception, psycopg2.DatabaseError) as err:
            self._log.warning('Error while executing SQL query', err)
            self._close_conn(conn, cur)
            return False

        self._close_conn(conn, cur)
        return True

    def _select(self, *args):
        """
        Executes SQL query and fetches result
        """
        conn = None
        try:
            conn = psycopg2.connect(self._db_url, sslmode='require')
        except (Exception, psycopg2.DatabaseError) as err:
            self._log.warning('Unable to connect to the DataBase', err)
            self._close_conn(conn)
            return None

        cur = conn.cursor()
        try:
            cur.execute(*args)
            rows = cur.fetchall()
        except (Exception, psycopg2.DatabaseError) as err:
            self._log.warning('Error while executing SQL query', err)
            self._close_conn(conn)
            return None

        self._close_conn(conn)
        return rows

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

    def get_tasks(self, chat_id):
        """
        Returns list of tasks which belong to this chat
        """
        sql_str = '''
        SELECT task_text, marked, deadline, workers 
        FROM tasks WHERE chat_id = (%s)
        '''
        sql_vals = (chat_id, )

        select_res = self._select(sql_str, sql_vals)
        if select_res is None:
            raise RuntimeError('Unable to fetch tasks from the DataBase')
        return select_res

