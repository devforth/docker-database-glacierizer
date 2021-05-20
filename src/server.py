import http.server
import base64
import json


class AuthServerHandler(http.server.BaseHTTPRequestHandler):

    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header(
            'WWW-Authenticate', 'Basic realm="Basic Realm"')
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        key = self.server.auth_key

        ''' Present frontpage with user authentication. '''
        if self.headers.get('Authorization') == None:
            self.do_AUTHHEAD()

            response = {
                'success': False,
                'error': 'No auth header received'
            }

            self.wfile.write(bytes(json.dumps(response), 'utf-8'))

        elif self.headers.get('Authorization') == 'Basic ' + str(key):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            self.server.on_get()

            self.wfile.write(b'Hello')
        else:
            self.do_AUTHHEAD()

            response = {
                'success': False,
                'error': 'Invalid credentials'
            }

            self.wfile.write(bytes(json.dumps(response), 'utf-8'))


class AuthServer(http.server.HTTPServer):
    auth_key = ''
    on_get = lambda: None

    def __init__(self, address):
        super().__init__(address, AuthServerHandler)

    def set_auth(self, username, password):
        self.auth_key = base64.b64encode(
            bytes('%s:%s' % (username, password), 'utf-8')).decode('ascii')

    def set_on_get(self, on_get):
        self.on_get = on_get

    def serve_forever(self, poll_interval=0.5):
        print(f'Starting server on {self.server_port}')
        super().serve_forever(poll_interval=poll_interval)
