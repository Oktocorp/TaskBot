import os
import psycopg2
from psycopg2.extras import RealDictCursor
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
        self._close_conn()
        return True

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
        Adds new task to the database.
        :raises ConnectionError: if DB exception occurred
        :raises ValueError: if couldn't add task to DB
        """

        sql_str = '''
        INSERT INTO tasks (chat_id, creator_id, task_text,
        marked, deadline, workers) VALUES (%s, %s, %s, %s, %s, %s)
        '''
        sql_vals = (chat_id, creator_id, task_text, marked, deadline, workers)
        return self._commit(sql_str, sql_vals)

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
        FROM tasks WHERE chat_id = (%s)  AND closed = FALSE
        '''
        sql_vals = (chat_id, )

        select_res = self._fetch_success(sql_str, sql_vals)
        return select_res

