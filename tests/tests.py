from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock

import db_connector


class TaskCreateDestroyTest(TestCase):
    def setUp(self):
        self.db = db_connector.DataBaseConnector()
        self.db._log = MagicMock()

    def test_task_add_all_fields(self):
        chat_id = 1
        user_id = 1
        task_text = 'Test task'
        marked = True
        deadline = datetime.now(timezone.utc)
        workers = [1]
        task_id = self.db.add_task(chat_id, user_id, task_text, marked,
                                   deadline, workers)
        self.assertIsInstance(task_id, int)
        self.assertGreater(task_id, 0)
        info = self.db.task_info(task_id)
        self.assertEqual(task_id, info['id'])
        self.assertEqual(user_id, info['creator_id'])
        self.assertEqual(task_text, info['task_text'])
        self.assertEqual(marked, info['marked'])
        self.assertEqual(deadline, info['deadline'])
        self.assertEqual(workers, info['workers'])

    def test_task_add_invalid_text(self):
        chat_id = 1
        user_id = 1
        task_text = None
        with self.assertRaises(ValueError):
            self.db.add_task(chat_id, user_id, task_text)

    def test_task_close_base(self):
        chat_id = 1
        user_id = 1
        task_id = self.db.add_task(chat_id, user_id, 'Test task')
        self.assertTrue(self.db.close_task(task_id, chat_id, user_id))

