#!/usr/bin/env python3
"""Tiny reverse proxy that rewrites qBittorrent v5's 204 login response
to 200 with 'Ok.' body, restoring compatibility with Readarr's auth check.
Readarr points to this proxy instead of qBittorrent directly.
Remove once Readarr merges the qBittorrent v5 auth fix upstream."""
import http.server
import http.client
import socketserver

QBITTORRENT_HOST = "homelab-qbittorrent"
QBITTORRENT_PORT = 8080
LISTEN_PORT = 8081

HOP_BY_HOP = {
    'transfer-encoding', 'content-length', 'connection',
    'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailers', 'upgrade',
}


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _forward(self):
        length = int(self.headers.get('Content-Length', 0) or 0)
        body = self.rfile.read(length) if length > 0 else None

        conn = http.client.HTTPConnection(QBITTORRENT_HOST, QBITTORRENT_PORT, timeout=60)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP and k.lower() != 'host'}
        conn.request(self.command, self.path, body=body, headers=headers)
        resp = conn.getresponse()
        resp_body = resp.read()

        if self.path == '/api/v2/auth/login' and resp.status == 204:
            resp.status = 200
            resp_body = b"Ok."

        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in HOP_BY_HOP:
                self.send_header(k, v)
        self.send_header('Content-Length', str(len(resp_body)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(resp_body)
        conn.close()

    def do_GET(self): self._forward()
    def do_POST(self): self._forward()
    def do_PUT(self): self._forward()
    def do_DELETE(self): self._forward()
    def do_HEAD(self): self._forward()

    def log_message(self, *args):
        pass


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == '__main__':
    ThreadingServer(('0.0.0.0', LISTEN_PORT), ProxyHandler).serve_forever()
