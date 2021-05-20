import http.server
import base64
import json
from urllib.parse import urlparse


class AuthServerHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        base_path = urlparse(self.path).path
        if base_path == '/':
            message = self.server.on_get()
        else:
            message = "Done"

        self.wfile.write(bytes(message, 'utf-8'))


class AuthServer(http.server.HTTPServer):
    auth_key = ''
    on_get = lambda: None

    def __init__(self, address, logger):
        super().__init__(address, AuthServerHandler)
        self.logger = logger

    def set_on_get(self, on_get):
        self.on_get = on_get

    def serve_forever(self, poll_interval=0.5):
        self.logger.info(f'Starting server on {self.server_port}')
        super().serve_forever(poll_interval=poll_interval)
