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
                 deadline=None, workers: list = None):
        """
        Add new task to the database.
        :raises ConnectionError: if DB exception occurred
        :raises ValueError: if couldn't add task to DB
        """
        if workers is None:
            workers = []

        sql_str = '''
        INSERT INTO tasks (chat_id, creator_id, task_text,
        marked, deadline, workers) VALUES (%s, %s, %s, %s, %s, %s)
        '''
        sql_val = (chat_id, creator_id, task_text, marked, deadline, workers)

        try:
            self._commit(sql_str, sql_val)
        except (ValueError, ConnectionError):  # Pass the exception up
            raise

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

        try:
            update_res = self._commit(sql_str, sql_val)
        except (ValueError, ConnectionError):  # Pass the exception up
            raise

        if update_res is None or update_res == -1 or update_res == 0:
            return False
        return True

    def assign_task(self, task_id, chat_id, user_id, workers: list, admin=False):
        """
        Assign worker to the task
        Anyone can take empty task for himself
        Assignment to other workers is available for admin
        :return: bool: Success indicator
        :raises ConnectionError: if DB exception occurred
        :raises ValueError: if couldn't update task in the DB
        """
        take_flag = len(workers) == 1 and workers[0] == user_id
        if not take_flag and not admin:
            return False

        sql_str = '''
                UPDATE tasks
                SET workers = (%s), assigned = (%s)
                WHERE id = (%s)  AND chat_id = (%s)
                AND closed = (%s)
                '''
        sql_val = (workers, admin, task_id, chat_id, False)

        if take_flag:
            # Assert total number of workers equals zero
            sql_str += 'AND cardinality(workers) = (%s)'
            sql_val += (0, )

        try:
            update_res = self._commit(sql_str, sql_val)
        except (ValueError, ConnectionError):  # Pass the exception up
            raise

        if update_res is None or update_res == -1 or update_res == 0:
            return False
        return True

    def rem_worker(self, task_id, chat_id, user_id):
        """
        Remove user from workers list
        :return: bool: Success indicator
        :raises ConnectionError: if DB exception occurred
        :raises ValueError: if couldn't update task in the DB
        """
        sql_str = '''
                UPDATE tasks
                SET workers = array_remove(workers, CAST((%s) AS BigInt))
                WHERE id = (%s) AND chat_id = (%s) AND (%s) = ANY(workers) 
                AND assigned = (%s) AND closed = (%s)
                '''
        sql_val = (user_id, task_id, chat_id, user_id, False, False)

        try:
            update_res = self._commit(sql_str, sql_val)
        except (ValueError, ConnectionError):  # Pass the exception up
            raise

        if update_res is None or update_res == -1 or update_res == 0:
            return False
        return True

    def set_deadline(self, task_id, chat_id, user_id, deadline: datetime = None):
        """
        Update task deadline if possible
        To remove deadline leave deadline param empty
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

        try:
            update_res = self._commit(sql_str, sql_val)
        except (ValueError, ConnectionError):  # Pass the exception up
            raise

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

        try:
            select_res = self._fetch_success(sql_str, sql_val)
        except (ValueError, ConnectionError):  # Pass the exception up
            raise
        return select_res

