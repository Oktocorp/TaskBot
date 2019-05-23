from datetime import datetime, timezone
from unittest import TestCase, main
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

    def test_task_close_invalid_id(self):
        chat_id = 1
        user_id = 1
        task_id = 0
        self.assertFalse(self.db.close_task(task_id, chat_id, user_id))


class TaskWorkerTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = db_connector.DataBaseConnector()
        cls.db._log = MagicMock()
        cls.chat_id = 1
        cls.user_id = 1
        cls.task_id = cls.db.add_task(cls.chat_id, cls.user_id, 'Test task')

    def test_task_assignment(self):
        self.assertTrue(self.db.assign_task(self.task_id, self.chat_id,
                                            self.user_id, [self.user_id]))
        info = self.db.task_info(self.task_id)
        self.assertIn(self.user_id, info['workers'])
        self.assertTrue(
            self.db.rem_worker(self.task_id, self.chat_id, self.user_id))

    def test_task_wrong_chat_assignment(self):
        wrong_chat = self.chat_id + 1
        self.assertFalse(self.db.assign_task(self.task_id, wrong_chat,
                                             self.user_id, [self.user_id]))

    def test_task_return(self):
        self.assertTrue(self.db.assign_task(self.task_id, self.chat_id,
                                            self.user_id, [self.user_id]))
        self.assertTrue(self.db.rem_worker(self.task_id, self.chat_id,
                                           self.user_id))
        info = self.db.task_info(self.task_id)
        self.assertNotIn(self.user_id, info['workers'])

    def test_task_return_invalid_id(self):
        wrong_id = self.user_id + 1
        self.assertFalse(
            self.db.rem_worker(self.task_id, self.chat_id, wrong_id))

    def test_tasks_from_two_chats(self):
        chat_id_1 = 1
        chat_id_2 = 2
        task_1 = self.db.add_task(chat_id_1, self.user_id, 'Test task')
        task_2 = self.db.add_task(chat_id_2, self.user_id, 'Test task')
        self.assertNotEqual(task_1, task_2)
        self.assertTrue(self.db.assign_task(task_1, chat_id_1,
                                            self.user_id, [self.user_id]))
        self.assertTrue(self.db.assign_task(task_2, chat_id_2,
                                            self.user_id, [self.user_id]))
        result = self.db.get_user_tasks(self.user_id)
        self.assertIn(task_1, [task['id'] for task in result])
        self.assertIn(task_2, [task['id'] for task in result])
        self.assertTrue(self.db.close_task(task_1, chat_id_1, self.user_id))
        self.assertTrue(self.db.close_task(task_2, chat_id_2, self.user_id))
        result = self.db.get_user_tasks(self.user_id)
        self.assertNotIn(task_1, [task['id'] for task in result])
        self.assertNotIn(task_2, [task['id'] for task in result])

    @classmethod
    def tearDownClass(cls):
        cls.db.close_task(cls.task_id, cls.chat_id, cls.user_id)


class TaskModifyTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = db_connector.DataBaseConnector()
        cls.db._log = MagicMock()
        cls.chat_id = 1
        cls.user_id = 1
        cls.task_id = cls.db.add_task(cls.chat_id, cls.user_id, 'Test task')

    def test_task_dl_setter(self):
        deadline = datetime.now(timezone.utc)
        self.assertTrue(self.db.set_deadline(self.task_id, self.chat_id,
                                             self.user_id, deadline))
        info = self.db.task_info(self.task_id)
        self.assertEqual(deadline, info['deadline'])

    def test_task_remove_dl(self):
        self.assertTrue(self.db.set_deadline(self.task_id, self.chat_id,
                                             self.user_id, deadline=None))
        info = self.db.task_info(self.task_id)
        self.assertIsNone(info['deadline'])

    def test_task_dl_update(self):
            deadline1 = datetime.now(timezone.utc)
            self.assertTrue(
                self.db.set_deadline(self.task_id, self.chat_id, self.user_id,
                                     deadline1))
            deadline2 = datetime.now(timezone.utc)
            self.assertTrue(
                self.db.set_deadline(self.task_id, self.chat_id, self.user_id,
                                     deadline2))
            info = self.db.task_info(self.task_id)
            self.assertEqual(deadline2, info['deadline'])

    def test_task_dl_assignment_to_closed(self):
        deadline = datetime.now(timezone.utc)
        new_task_id = self.db.add_task(self.chat_id, self.user_id, 'Test task')
        self.assertTrue(self.db.close_task(new_task_id, self.chat_id,
                                           self.user_id))
        self.assertFalse(self.db.set_deadline(new_task_id, self.chat_id,
                                              self.user_id, deadline))

    def test_task_marked_status(self):
        self.assertTrue(self.db.set_marked_status(self.task_id, self.chat_id,
                                                  self.user_id, marked=True))
        info = self.db.task_info(self.task_id)
        self.assertTrue(info['marked'])
        self.assertTrue(self.db.set_marked_status(self.task_id, self.chat_id,
                                                  self.user_id, marked=False))
        info = self.db.task_info(self.task_id)
        self.assertFalse(info['marked'])
    
    @classmethod
    def tearDownClass(cls):
        cls.db.close_task(cls.task_id, cls.chat_id, cls.user_id)
        

if __name__ == '__main__':
    main()
