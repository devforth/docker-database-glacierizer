import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import dump

PASSWORD = 's3cr3t-Pa55'
run_command = getattr(dump, '__run_command')


class RunCommandLogTest(unittest.TestCase):

    def test_password_is_masked_in_log(self):
        with self.assertLogs('ddgscheduler', level='INFO') as logs:
            exit_status = run_command(f'PGPASSWORD="{PASSWORD}" true', PASSWORD)

        self.assertEqual(exit_status, 0)
        self.assertNotIn(PASSWORD, '\n'.join(logs.output))
        self.assertIn('PGPASSWORD="***"', '\n'.join(logs.output))

    def test_command_without_password_is_logged_as_is(self):
        with self.assertLogs('ddgscheduler', level='INFO') as logs:
            run_command('true', '')

        self.assertIn('Running dm command: true', '\n'.join(logs.output))


if __name__ == '__main__':
    unittest.main()
