import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
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

    def _commit(self, *args, fetch_data=False):
        """
        Try to execute SQL query
        :returns number of rows affected
        If fetch_data flag is set, row content is also returned
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
        row = None
        try:
            self._cur.execute(*args)
            self._conn.commit()
            if fetch_data:
                row = self._cur.fetchone()
        except (Exception, psycopg2.DatabaseError) as err:
            self._close_conn(err)
            raise ValueError('Unable to execute SQL')
        rows_num = self._cur.rowcount
        self._close_conn()
        if fetch_data:
            return rows_num, row
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
            raise ConnectionError('Unable to connect to the DataBase', err)

        self._cur = self._conn.cursor()
        try:
            self._cur.execute(*args)
            rows = self._cur.fetchall()
        except (Exception, psycopg2.DatabaseError) as err:
            self._close_conn(err)
            raise ValueError('Unable to execute SQL', err)

        self._close_conn()
        return rows

    def add_task(self, chat_id, creator_id, task_text, marked=False,
                 deadline=None, workers: list = None):
        """
        Add new task to the database.
        :returns New task id
        :raises ConnectionError: if DB exception occurred
        :raises ValueError: if couldn't add task to DB
        """
        if workers is None:
            workers = []

        sql_str = '''
        INSERT INTO tasks (chat_id, creator_id, task_text,
        marked, deadline, workers) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
        '''
        sql_val = (chat_id, creator_id, task_text, marked, deadline, workers)

        try:
            count, info = self._commit(sql_str, sql_val, fetch_data=True)
            task_id = int(info[0])
        except (ValueError, ConnectionError):  # Pass the exception up
            raise
        return task_id

    def close_task(self, task_id, chat_id, user_id):
        """
        Close task if possible
        Also cancels all the connected reminders
        :return Success indicator
        :raises ConnectionError: if DB exception occurred
        :raises ValueError: if couldn't update task in the DB
        """
        sql_str = '''
        WITH src AS(
        UPDATE tasks
        SET closed = (%s)
        WHERE id = (%s)  AND chat_id = (%s)
        AND (workers = (%s) OR creator_id = (%s) OR (%s) = ANY(workers))
        AND closed = (%s)
        RETURNING *
        )
        UPDATE reminders
        SET canceled = (%s)
        WHERE task_id IN (SELECT id from src)
        '''
        sql_val = (True, task_id, chat_id, [], user_id, user_id, False, True)

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

    def get_tasks(self, chat_id, free_only=False):
        """
        Get all tasks from the given chat
        if free_only flag is set, only vacant tasks are returned
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
        if free_only:
            sql_str += 'AND workers = (%s)'
            sql_val += ([],)
        try:
            select_res = self._fetch_success(sql_str, sql_val)
        except (ValueError, ConnectionError):  # Pass the exception up
            raise
        return select_res

    def get_user_tasks(self, user_id):
        """
        Get all tasks assigned to the user
        :returns DictRow (list of tasks)
        Each task is represented by dict
        dict keys: id, creator_id, task_text, marked, deadline, workers

        :raises ValueError: if unable to fetch tasks from the DataBase
        :raises ConnectionError: if DB exception occurred
        """
        sql_str = '''
        SELECT id, creator_id, task_text, marked, deadline, workers 
        FROM tasks WHERE (%s) = ANY(workers) AND closed = (%s)
        '''
        sql_val = (user_id, False)
        try:
            select_res = self._fetch_success(sql_str, sql_val)
        except (ValueError, ConnectionError):  # Pass the exception up
            raise
        return select_res

    def task_info(self, task_id):
        """
        Get task data as dict
        :return: RealDictRow:(id, chat_id, creator_id, task_text,
                              marked, deadline, workers)
        :raises ValueError: if unable to fetch tasks from the DataBase
        :raises ConnectionError: if DB exception occurred
        """
        sql_str = '''
                SELECT id, chat_id, creator_id, task_text, marked, deadline, 
                workers 
                FROM tasks WHERE id = (%s) AND closed = (%s)
                '''
        sql_val = (task_id, False)

        try:
            task = self._fetch_success(sql_str, sql_val)[0]
        except IndexError:
            raise ValueError('Could not find task')
        except (ValueError, ConnectionError):
            raise  # Pass the exception up
        return task

    def set_marked_status(self, task_id, chat_id, user_id, marked):
        """
        Update marked status ([ ! ])
        :return Success indicator
        :raises ConnectionError: if DB exception occurred
        :raises ValueError: if couldn't update task in the DB
        """
        sql_str = '''
        UPDATE tasks
        SET marked = (%s)
        WHERE id = (%s)  AND chat_id = (%s)
        AND (workers = (%s) OR creator_id = (%s) OR (%s) = ANY(workers))
        AND closed = (%s)
        '''
        sql_val = (marked, task_id, chat_id, [], user_id, user_id, False)

        try:
            update_res = self._commit(sql_str, sql_val)
        except (ValueError, ConnectionError):  # Pass the exception up
            raise

        if update_res is None or update_res == -1 or update_res == 0:
            return False
        return True

    def create_reminder(self, task_id, user_id, date_time):
        """
        Add new reminder to the database.
        :returns Success indicator
        :raises ConnectionError: if DB exception occurred
        :raises ValueError: if couldn't add task to DB
        """

        sql_str = '''
                INSERT INTO reminders (task_id, user_id, datetime)
                VALUES (%s, %s, %s)
                RETURNING id;
                '''
        sql_val = (task_id, user_id, date_time)

        try:
            res = self._commit(sql_str, sql_val)
        except (ValueError, ConnectionError):  # Pass the exception up
            raise
        return res

    def get_reminders(self):
        """
        Get all reminders which are ready to be triggered
        :returns DictRow (list of reminders)
        Each task is represented by dict
        dict keys: id, user_id, task_id, task_text, deadline

        :raises ValueError: if unable to fetch tasks from the DataBase
        :raises ConnectionError: if DB exception occurred
        """
        sql_str = '''
                SELECT rem.id, rem.user_id, rem.task_id, t.task_text, t.deadline 
                FROM reminders AS rem, tasks as t
                WHERE rem.datetime <= (%s) AND rem.canceled = (%s)
                AND rem.task_id = t.id
                '''
        sql_val = (datetime.now(timezone.utc), False)
        try:
            select_res = self._fetch_success(sql_str, sql_val)
        except (ValueError, ConnectionError):  # Pass the exception up
            raise
        return select_res

    def close_reminders(self, rem_ids: list):
        """
        Mark the reminders as closed
        :raises ValueError: if unable to update tasks int the DataBase
        :raises ConnectionError: if DB exception occurred
        """
        sql_str = '''
                UPDATE reminders
                SET canceled = (%s)
                WHERE id = ANY (%s)
                '''
        sql_val = (True, rem_ids)
        try:
            update_res = self._commit(sql_str, sql_val)
        except (ValueError, ConnectionError):  # Pass the exception up
            raise
        if update_res is None or update_res == -1:
            raise ValueError('Unable to close tasks')
