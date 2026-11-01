import hmac
import http.server
from urllib.parse import urlparse


class AuthServerHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_error(405)

    def do_POST(self):
        if urlparse(self.path).path != '/':
            self.send_error(404)
        elif not self.server.is_authorized(self.headers.get('Authorization', '')):
            self.send_error(401)
        else:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            message = self.server.on_post()
            self.wfile.write(bytes(message, 'utf-8'))


class AuthServer(http.server.HTTPServer):
    on_post = lambda: None

    def __init__(self, address, token, logger):
        super().__init__(address, AuthServerHandler)
        self.token = token
        self.logger = logger

    def set_on_post(self, on_post):
        self.on_post = on_post

    def is_authorized(self, authorization):
        return hmac.compare_digest(authorization.encode(), f'Bearer {self.token}'.encode())

    def serve_forever(self, poll_interval=0.5):
        self.logger.info(f'Starting server on {self.server_address}')
        super().serve_forever(poll_interval=poll_interval)
