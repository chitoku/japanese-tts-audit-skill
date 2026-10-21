"""Loopback-only listening UI with atomic, revisioned human-review storage."""
import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
from urllib.parse import urlsplit
import webbrowser

from .report import render
from .reviews import merge_notes


def now():
    return datetime.now(timezone.utc).isoformat()


class Conflict(ValueError):
    pass


class ReviewStore:
    """review-state.json is the authoritative, atomically replaced Agent interface."""
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.report_path = self.directory / 'report.json'
        raw = self.report_path.read_bytes()
        self.report = json.loads(raw)
        self.fingerprint = hashlib.sha256(raw).hexdigest()
        self.path = self.directory / 'review-state.json'
        self.mutex = threading.Lock()
        with self.locked():
            if self.path.exists():
                self._read()
            else:
                imported = self.directory / 'listening-notes.json'
                batch = json.loads(imported.read_text(encoding='utf-8')) if imported.exists() else {
                    'schema_version': 1, 'run_id': self.report['run_id'], 'exported_at': now(), 'notes': {}}
                notes = merge_notes(self.report, batch)['notes']
                self._write(self._state(notes, 0))

    @contextmanager
    def locked(self):
        # OS locks also serialize separate servers/importers using this store.
        with self.mutex, (self.directory / '.review-state.lock').open('a+b') as lock:
            if os.name == 'nt':
                import msvcrt
                lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == 'nt':
                    lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read(self):
        if hashlib.sha256(self.report_path.read_bytes()).hexdigest() != self.fingerprint:
            raise Conflict('Report changed; restart with the matching report')
        state = json.loads(self.path.read_text(encoding='utf-8'))
        if state['run_id'] != self.report['run_id'] or state['report_sha256'] != self.fingerprint:
            raise Conflict('Saved reviews belong to a different report')
        return state

    def _state(self, notes, revision, completed=False):
        counts = Counter(n['verdict'] for n in notes.values())
        decided = sum(v for k, v in counts.items() if k != 'unreviewed')
        return {'schema_version': 1, 'run_id': self.report['run_id'],
                'report_sha256': self.fingerprint, 'revision': revision,
                'status': 'completed' if completed else 'draft', 'updated_at': now(),
                'completed_at': now() if completed else None,
                'candidate_count': len(self.report['findings']), 'reviewed_count': decided,
                'unreviewed_count': len(self.report['findings']) - decided,
                'verdict_counts': dict(counts), 'notes': notes,
                'scope': 'Human review of flagged candidates only; completion does not certify full audio or resolve uncertain labels.'}

    def _write(self, state):
        fd, name = tempfile.mkstemp(prefix='.review-state-', dir=self.directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                json.dump(state, output, ensure_ascii=False, indent=2)
                output.write('\n'); output.flush(); os.fsync(output.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name): os.unlink(name)

    def read(self):
        with self.locked():
            return self._read()

    def update(self, payload, complete=False):
        if not isinstance(payload, dict): raise ValueError('Expected an object')
        with self.locked():
            state = self._read()
            if type(payload.get('revision')) is not int or payload['revision'] != state['revision']:
                raise Conflict('Review changed in another window; reload before editing')
            batch = {'schema_version': payload.get('schema_version'), 'run_id': payload.get('run_id'),
                     'exported_at': now(), 'notes': payload.get('notes')}
            old = dict(batch, notes=state['notes'])
            notes = merge_notes(self.report, batch, old)['notes']
            result = self._state(notes, state['revision'] + 1, complete)
            self._write(result)
            return result


def make_server(directory, port=0):
    store = ReviewStore(directory)
    token = secrets.token_urlsafe(24)
    prefix = '/' + token + '/'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Request paths contain the local session capability.

        def send(self, code, body, kind='application/json; charset=utf-8', extra=None):
            if isinstance(body, dict): body = json.dumps(body, ensure_ascii=False).encode()
            if isinstance(body, str): body = body.encode()
            self.send_response(code)
            for key, value in {'Content-Type': kind, 'Content-Length': str(len(body)),
                               'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                               'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY',
                               **(extra or {})}.items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != 'HEAD': self.wfile.write(body)

        def route(self):
            authority = '127.0.0.1:' + str(self.server.server_port)
            if self.headers.get('Host') != authority:
                self.send(403, {'error': 'Invalid host'}); return None
            if self.headers.get('Origin') not in (None, 'http://' + authority):
                self.send(403, {'error': 'Invalid origin'}); return None
            path = urlsplit(self.path).path
            if not path.startswith(prefix):
                self.send(404, {'error': 'Not found'}); return None
            return path[len(prefix):]

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            path = self.route()
            if path is None: return
            try:
                state = store.read()
                if path == 'api/reviews': return self.send(200, state)
                if path in ('', 'report.html'):
                    batch = {'notes': state['notes']}
                    config = {'revision': state['revision'], 'status': state['status']}
                    return self.send(200, render(store.report, batch, server=config), 'text/html; charset=utf-8')
                allowed = {'audio.wav': 'audio/wav', 'report.json': 'application/json',
                           'transcript.json': 'application/json', 'review-state.json': 'application/json'}
                if path not in allowed: return self.send(404, {'error': 'Not found'})
                target = store.directory / path
                if target.is_symlink() or not target.is_file(): return self.send(404, {'error': 'Not found'})
                content = target.read_bytes()
                if path == 'audio.wav':
                    headers = {'Accept-Ranges': 'bytes'}
                    value = self.headers.get('Range')
                    if value:
                        match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
                        if not match or not any(match.groups()):
                            return self.send(416, b'', extra={'Content-Range': 'bytes */' + str(len(content))})
                        a, b = match.groups()
                        start = int(a) if a else max(0, len(content) - int(b))
                        end = min(int(b), len(content)-1) if a and b else len(content)-1
                        if start > end or start >= len(content):
                            return self.send(416, b'', extra={'Content-Range': 'bytes */' + str(len(content))})
                        headers['Content-Range'] = f'bytes {start}-{end}/{len(content)}'
                        return self.send(206, content[start:end+1], 'audio/wav', headers)
                    return self.send(200, content, 'audio/wav', headers)
                return self.send(200, content, allowed[path])
            except Conflict as error:
                self.send(409, {'error': str(error)})
            except (OSError, ValueError, KeyError):
                self.send(500, {'error': 'Cannot read report or review state'})

        def do_POST(self):
            path = self.route()
            if path is None: return
            if path not in ('api/reviews', 'api/complete'):
                return self.send(404, {'error': 'Not found'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, {'error': 'Expected application/json'})
            try:
                size = int(self.headers.get('Content-Length', '-1'))
                if not 0 < size <= 1024 * 1024: return self.send(413, {'error': 'Invalid request size'})
                payload = json.loads(self.rfile.read(size))
                return self.send(200, store.update(payload, path == 'api/complete'))
            except Conflict as error:
                self.send(409, {'error': str(error)})
            except (ValueError, TypeError, KeyError, AttributeError):
                self.send(400, {'error': 'Invalid review data'})
            except OSError:
                self.send(500, {'error': 'Save failed; keep the page and export a backup'})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.review_url = f'http://127.0.0.1:{server.server_port}{prefix}'
    server.review_store = store
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(prog='tts-audit serve', description=__doc__)
    parser.add_argument('report_directory', type=Path)
    parser.add_argument('--port', type=int, default=0, help='Loopback port; 0 chooses an available port')
    parser.add_argument('--open', action='store_true', help='Open the listening page in the default browser')
    args = parser.parse_args(argv)
    try:
        server = make_server(args.report_directory, args.port)
        print(json.dumps({'url': server.review_url, 'review_state': str(server.review_store.path)}, ensure_ascii=False), flush=True)
        if args.open: webbrowser.open(server.review_url)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
        return 0
    except (OSError, ValueError, KeyError) as error:
        print('tts-audit serve: ' + str(error), file=__import__('sys').stderr)
        return 1
