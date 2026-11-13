"""Offline HTTP(S), CONNECT/forward proxy, TS/fMP4 and AES-128 HLS checks.

Requires only Python's standard library, an openssl command for temporary test
certificates, and the capability executable linked against the candidate libs.
"""

import contextlib
import functools
import http.server
import os
import re
import select
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit


class QuietFiles(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


@contextlib.contextmanager
def serve(handler, tls=None):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    if tls:
        server.socket = tls.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class Proxy(http.server.BaseHTTPRequestHandler):
    allowed_ports = set()
    counts = {"GET": 0, "CONNECT": 0}

    def log_message(self, *_):
        pass

    def do_CONNECT(self):
        self.forward(True)

    def do_GET(self):
        self.forward(False)

    def forward(self, tunnel):
        target = urlsplit("//" + self.path if tunnel else self.path)
        port = target.port or 80
        # This local test proxy must never forward requests outside its fixtures.
        if target.hostname not in {"127.0.0.1", "localhost"} or port not in self.allowed_ports:
            self.send_error(403)
            return
        self.counts[self.command] += 1
        self.close_connection = True
        with socket.create_connection((target.hostname, port), timeout=10) as upstream:
            if tunnel:
                self.send_response(200, "Connection established")
                self.end_headers()
            else:
                path = target.path or "/"
                if target.query:
                    path += "?" + target.query
                upstream.sendall((f"GET {path} HTTP/1.0\r\nHost: {target.netloc}\r\nConnection: close\r\n\r\n").encode("ascii"))
            try:
                while True:
                    ready, _, _ = select.select([self.connection, upstream], [], [], 10)
                    if not ready:
                        raise TimeoutError("proxy stalled")
                    for source in ready:
                        chunk = source.recv(65536)
                        if not chunk:
                            return
                        (upstream if source is self.connection else self.connection).sendall(chunk)
            except (ConnectionError, ssl.SSLError):
                # Expected for the negative certificate check.
                return


def main():
    executable = str(Path(sys.argv[1]).resolve())
    if os.name == "nt" and not executable.endswith(".exe"):
        executable += ".exe"
    fixture = Path(__file__).resolve().parent / "data"
    env = {key: value for key, value in os.environ.items()
           if key.lower() not in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}}

    def probe(label, url, proxy="", ca="", success=True):
        result = subprocess.run([executable, url, proxy, str(ca)], env=env,
                                capture_output=True, text=True, timeout=25)
        if (result.returncode == 0) != success:
            raise AssertionError(f"{label}: exit={result.returncode}\n{result.stdout}\n{result.stderr}")
        if success:
            match = re.search(r"media streams=(\d+) packets=(\d+)", result.stdout)
            if not match or int(match[1]) != 2 or int(match[2]) < 2:
                raise AssertionError(f"{label}: no H.264/AAC packets: {result.stdout}")
        elif "certificate verify failed" not in result.stderr.lower():
            raise AssertionError(f"{label}: did not fail certificate verification: {result.stderr}")
        print(f"PASS {label}", flush=True)

    with tempfile.TemporaryDirectory(prefix="ddbot-ffmpeg-tls-") as temp:
        cert = Path(temp) / "cert.pem"
        key = Path(temp) / "key.pem"
        wrong_ca = Path(temp) / "wrong-ca.pem"
        for cert_path, key_path in ((cert, key), (wrong_ca, Path(temp) / "wrong-key.pem")):
            subprocess.run([os.environ.get("OPENSSL", "openssl"), "req", "-x509", "-newkey", "rsa:2048",
                            "-nodes", "-days", "2", "-subj", "/CN=localhost", "-addext",
                            "subjectAltName=DNS:localhost,IP:127.0.0.1", "-keyout", str(key_path),
                            "-out", str(cert_path)], check=True, capture_output=True)
        files = functools.partial(QuietFiles, directory=str(fixture))
        with serve(files) as http_port, serve(Proxy) as proxy_port:
            Proxy.allowed_ports.add(http_port)
            proxy = f"http://127.0.0.1:{proxy_port}"
            for sample in ("ts", "fmp4", "encrypted"):
                url = f"http://127.0.0.1:{http_port}/{sample}/index.m3u8"
                probe(f"HTTP {sample} HLS", url)
                before = Proxy.counts["GET"]
                probe(f"HTTP proxy {sample} HLS", url, proxy)
                if Proxy.counts["GET"] <= before:
                    raise AssertionError("HTTP request bypassed proxy")
            for version in (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3):
                tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                tls.minimum_version = tls.maximum_version = version
                tls.load_cert_chain(cert, key)
                with serve(files, tls) as https_port:
                    Proxy.allowed_ports.add(https_port)
                    for sample in ("ts", "fmp4", "encrypted"):
                        url = f"https://localhost:{https_port}/{sample}/index.m3u8"
                        probe(f"{version.name} {sample} HLS", url, ca=cert)
                        before = Proxy.counts["CONNECT"]
                        probe(f"{version.name} CONNECT {sample} HLS", url, proxy, cert)
                        if Proxy.counts["CONNECT"] <= before:
                            raise AssertionError("HTTPS request bypassed CONNECT proxy")
                    probe(f"{version.name} rejects wrong CA", url, ca=wrong_ca, success=False)
                    probe(f"{version.name} CONNECT rejects wrong CA", url, proxy, wrong_ca, success=False)
                    Proxy.allowed_ports.remove(https_port)
    print("All 22 local media/TLS/proxy checks passed.")


if __name__ == "__main__":
    main()
