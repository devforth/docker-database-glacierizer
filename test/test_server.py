import os
import sys
import logging
import threading
import unittest
from http.client import HTTPConnection

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from server import AuthServer

TOKEN = 'test-token'


class AuthServerTest(unittest.TestCase):

    def setUp(self):
        self.calls = 0
        self.server = AuthServer(('127.0.0.1', 0), TOKEN, logging.getLogger('test'))
        self.server.set_on_post(self.on_post)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def on_post(self):
        self.calls += 1
        return 'Backup Done'

    def request(self, method, path='/', token=None):
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        connection = HTTPConnection('127.0.0.1', self.server.server_port)
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        body = response.read()
        connection.close()
        return response.status, body

    def test_get_is_not_allowed(self):
        self.assertEqual(self.request('GET')[0], 405)
        self.assertEqual(self.calls, 0)

    def test_post_without_token(self):
        self.assertEqual(self.request('POST')[0], 401)
        self.assertEqual(self.calls, 0)

    def test_post_with_wrong_token(self):
        self.assertEqual(self.request('POST', token='wrong')[0], 401)
        self.assertEqual(self.calls, 0)

    def test_post_to_other_path(self):
        self.assertEqual(self.request('POST', path='/other', token=TOKEN)[0], 404)
        self.assertEqual(self.calls, 0)

    def test_post_with_token(self):
        self.assertEqual(self.request('POST', token=TOKEN), (200, b'Backup Done'))
        self.assertEqual(self.calls, 1)
