import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import logger


class DataBaseConnector:
    def __init__(self):
        self._db_url = os.environ['DATABASE_URL']
        self._log = logger.get_logger(__name__)
        self._conn = None
        self._cur = None

    def _close_conn(self, err=None):
        """Ensure the connection is closed"""
        if self._cur is not None:
            self._cur.close()
        if self._conn is not None:
            self._conn.close()
        if err:
            self._log.warning('Unable to execute SQL', err)

    def _commit(self, *args):
        """
        Try to execute SQL query
        :raises ConnectionError: if couldn't connect to DB
        :raises ValueError: if couldn't execute SQL
        """
        self._conn = None
        try:
            self._conn = psycopg2.connect(self._db_url, sslmode='require')
        except (Exception, psycopg2.DatabaseError) as err:
            self._close_conn(err)
            raise ConnectionError('Unable to connect to the DataBase')

        self._cur = self._conn.cursor()
        try:
            self._cur.execute(*args)
            self._conn.commit()
        except (Exception, psycopg2.DatabaseError) as err:
            self._close_conn(err)
            raise ValueError('Unable to execute SQL')
        rows_num = self._cur.rowcount
        self._close_conn()
        return rows_num

    def _fetch_success(self, *args):
        """
        Executes SQL query and fetches result
        :returns DictRow of affected rows
        :raises ConnectionError: if couldn't connect to DB
        :raises ValueError: if couldn't execute SQL
        """
        self._conn = None
        try:
            self._conn = psycopg2.connect(self._db_url, sslmode='require',
                                          cursor_factory=RealDictCursor)
        except (Exception, psycopg2.DatabaseError) as err:
            self._close_conn(err)
            raise ConnectionError('Unable to connect to the DataBase')

        self._cur = self._conn.cursor()
        try:
            self._cur.execute(*args)
            rows = self._cur.fetchall()
        except (Exception, psycopg2.DatabaseError) as err:
            self._close_conn(err)
            raise ValueError('Unable to execute SQL')

        self._close_conn()
        return rows

    def add_task(self, chat_id, creator_id, task_text, marked=False,
                 deadline=None, workers=None):
        """
        Add new task to the database.
        :raises ConnectionError: if DB exception occurred
        :raises ValueError: if couldn't add task to DB
        """

        sql_str = '''
        INSERT INTO tasks (chat_id, creator_id, task_text,
        marked, deadline, workers) VALUES (%s, %s, %s, %s, %s, %s)
        '''
        sql_val = (chat_id, creator_id, task_text, marked, deadline, workers)
        self._commit(sql_str, sql_val)

    def close_task(self, task_id, chat_id, user_id):
        """
        Close task if possible
        :return Success indicator
        :raises ConnectionError: if DB exception occurred
        :raises ValueError: if couldn't update task in the DB
        """
        sql_str = '''
        UPDATE tasks
        SET closed = (%s)
        WHERE id = (%s)  AND chat_id = (%s)
        AND (workers IS NULL OR creator_id = (%s) OR (%s) = ANY(workers))
        AND closed = (%s)
        '''
        sql_val = (True, task_id, chat_id, user_id, user_id, False)
        update_res = self._commit(sql_str, sql_val)
        if update_res is None or update_res == -1 or update_res == 0:
            return False
        return True

    def set_deadline(self, task_id, chat_id, user_id, deadline: datetime):
        """
        Update task deadline if possible
        :param deadline: TIMEZONE AWARE!!! datetime object
        :return Success indicator
        :raises ConnectionError: if DB exception occurred
        :raises ValueError: if couldn't update task in the DB
        """
        sql_str = '''
        UPDATE tasks
        SET deadline = (%s)
        WHERE id = (%s)  AND chat_id = (%s)
        AND (creator_id = (%s) OR (%s) = ANY(workers))
        AND closed = (%s)
        '''
        sql_val = (deadline, task_id, chat_id, user_id, user_id, False)
        update_res = self._commit(sql_str, sql_val)
        if update_res is None or update_res == -1 or update_res == 0:
            return False
        return True

    def get_tasks(self, chat_id):
        """
        Get all tasks from the given chat
        :returns DictRow (list of tasks which belong to this chat)
        Each task is represented by dict
        dict keys: id, creator_id, task_text, marked, deadline, workers

        :raises ValueError: if unable to fetch tasks from the DataBase
        :raises ConnectionError: if DB exception occurred
        """
        sql_str = '''
        SELECT id, creator_id, task_text, marked, deadline, workers 
        FROM tasks WHERE chat_id = (%s)  AND closed = (%s)
        '''
        sql_val = (chat_id, False)

        select_res = self._fetch_success(sql_str, sql_val)
        return select_res

