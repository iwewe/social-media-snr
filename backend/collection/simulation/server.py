"""Simulasi platform sosial untuk PoC browser (WP-1.8; AT-18). Hanya pustaka standar Python.

Server kecil yang meniru struktur percakapan: balasan bertingkat, pagination "Muat lebih banyak"
(JavaScript, bukan tautan), konten yang berubah antar kunjungan, halaman 403/404/500, tantangan
CAPTCHA, tembok login, struktur halaman yang berubah, dan halaman lambat. Semua data sintetis.

Skenario dipilih lewat awalan `/s/<skenario>/...` atau, tanpa awalan, lewat tabel `ID_SCENARIOS`
berdasarkan ID postingan (URL `/<pengguna>/status/<id>`). Tidak ada cara melewati tantangan: halaman
tantangan memang hanya halaman tantangan.
"""

import json
import threading
import time
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from urllib.parse import parse_qs, urlsplit

PAGE_SIZE = 3
SLOW_DELAY_SECONDS = 3.0
SCENARIOS = (
    "complete",
    "empty_post",
    "partial",
    "login_wall",
    "forbidden",
    "challenge",
    "not_found",
    "server_error",
    "parse_failure",
    "identity_missing",
    "changing",
    "external",
    "slow",
)
# Tanpa awalan /s/<skenario>/, ID postingan menentukan skenario (untuk target di aplikasi).
ID_SCENARIOS = {
    "1001": "complete",
    "1002": "partial",
    "1003": "forbidden",
    "1004": "challenge",
    "1005": "not_found",
    "1006": "changing",
    "1007": "login_wall",
    "1008": "parse_failure",
    "1009": "empty_post",
}
TOTAL_REPLIES = 7
SESSION_COOKIE_VALUE = "SESI-SIMULASI-RAHASIA-123"


def _reply(post: str, i: int, *, text: str | None = None, author: bool = True) -> dict:
    return {
        "id": f"{post}{i:03d}",
        "author": f"u{i % 4}" if author else "",
        "handle": f"akun_u{i % 4}",
        "parent": post if i % 3 != 0 else f"{post}{i - 1:03d}",
        "published": f"2026-10-15T08:{i:02d}:00Z",
        "text": text if text is not None else f"Balasan sintetis {i}",
    }


def replies_for(scenario: str, post: str, visit: int) -> list[dict]:
    if scenario == "empty_post":
        return []
    if scenario == "changing":
        base = {i: _reply(post, i) for i in range(1, 6)}
        if visit <= 1:
            return [base[i] for i in (1, 2, 3)]
        base[1] = _reply(post, 1, text="Balasan sintetis 1 (diedit)")
        if visit == 2:
            return [base[i] for i in (1, 2, 3, 4, 5)]
        return [base[i] for i in (1, 3, 4, 5)]  # kunjungan 3: balasan 2 tidak tampil
    items = [_reply(post, i) for i in range(1, TOTAL_REPLIES + 1)]
    if scenario == "identity_missing":
        items[1] = _reply(post, 2, author=False)
    return items


def _li(r: dict) -> str:
    author = f' data-author-id="{escape(r["author"])}"' if r["author"] else ""
    return (
        f'<li class="reply" data-reply-id="{escape(r["id"])}"{author}'
        f' data-handle="{escape(r["handle"])}" data-parent-id="{escape(r["parent"])}">'
        f'<time datetime="{r["published"]}">{r["published"]}</time>'
        f'<p class="text">{escape(r["text"])}</p></li>'
    )


JS = """
const btn = document.getElementById('load-more');
if (btn) btn.addEventListener('click', async () => {
  btn.disabled = true;
  try {
    const r = await fetch('/api/replies?post=' + encodeURIComponent(document.body.dataset.post)
      + '&page=' + btn.dataset.next + '&s=' + encodeURIComponent(document.body.dataset.scenario));
    if (r.status === 401) {
      document.getElementById('login-wall').hidden = false; btn.hidden = true; return;
    }
    if (!r.ok) throw new Error('gagal');
    const j = await r.json();
    document.getElementById('replies').insertAdjacentHTML('beforeend', j.html);
    if (j.next) { btn.dataset.next = String(j.next); btn.disabled = false; }
    else { btn.hidden = true; }
  } catch (e) {
    document.getElementById('load-error').hidden = false; btn.disabled = false;
  }
});
"""


class _State:
    def __init__(self) -> None:
        self.visits: dict[str, int] = {}
        self.lock = threading.Lock()

    def visit(self, post: str) -> int:
        with self.lock:
            self.visits[post] = self.visits.get(post, 0) + 1
            return self.visits[post]

    def current(self, post: str) -> int:
        with self.lock:
            return self.visits.get(post, 1)

    def reset(self) -> None:
        with self.lock:
            self.visits.clear()


def _page(scenario: str, post: str, visit: int) -> str:
    replies = replies_for(scenario, post, visit)
    first = "".join(_li(r) for r in replies[:PAGE_SIZE])
    more = (
        '<button id="load-more" type="button" data-next="2">Muat lebih banyak</button>'
        if len(replies) > PAGE_SIZE
        else ""
    )
    tracker = '<img src="http://tracker.invalid/p.gif" alt="">' if scenario == "external" else ""
    return (
        '<!doctype html><html lang="id"><head><meta charset="utf-8"><title>SimSosial</title></head>'
        f'<body data-post="{escape(post)}" data-scenario="{escape(scenario)}">{tracker}'
        f'<main id="conversation" data-displayed-count="{len(replies)}">'
        f'<article id="focal" data-post-id="{escape(post)}" data-author-id="u0"'
        ' data-handle="contoh_redaksi"><time datetime="2026-10-15T08:00:00Z">2026-10-15</time>'
        f'<p class="text">Pos sintetis {escape(post)}</p></article>'
        f'<ol id="replies">{first}</ol>'
        '<p id="load-error" hidden>Gagal memuat balasan.</p>'
        '<div id="login-wall" hidden>Masuk untuk melihat balasan lain.</div>'
        f"{more}</main><script>{JS}</script></body></html>"
    )


class _Handler(BaseHTTPRequestHandler):
    server: "SimulationHTTPServer"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - senyap
        return

    def _send(self, status: int, body: str, ctype: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        # Cookie sesi palsu: uji memastikan nilai ini tidak pernah masuk bukti/hasil.
        self.send_header("Set-Cookie", f"snr_sim_session={SESSION_COOKIE_VALUE}; HttpOnly; Path=/")
        self.end_headers()
        self.wfile.write(data)

    def _route(self) -> tuple[str | None, list[str], dict[str, list[str]]]:
        parts = urlsplit(self.path)
        segs = [s for s in parts.path.split("/") if s]
        scenario = None
        if len(segs) >= 2 and segs[0] == "s":
            scenario, segs = segs[1], segs[2:]
        return scenario, segs, parse_qs(parts.query)

    def do_POST(self) -> None:  # noqa: N802
        if urlsplit(self.path).path == "/__reset":
            self.server.state.reset()
            self._send(204, "")
        else:
            self._send(404, "tidak ada")

    def do_GET(self) -> None:  # noqa: N802
        scenario, segs, query = self._route()
        if segs[:2] == ["api", "replies"]:
            return self._api(query)
        if len(segs) == 3 and segs[1] == "status" and segs[2].isdigit():
            return self._conversation(scenario, segs[2])
        self._send(404, "<h1>Tidak ditemukan</h1>")

    def _conversation(self, scenario: str | None, post: str) -> None:
        scenario = scenario or ID_SCENARIOS.get(post, "not_found")
        if scenario not in SCENARIOS:
            return self._send(404, "<h1>Skenario tidak dikenal</h1>")
        if scenario == "slow":
            time.sleep(SLOW_DELAY_SECONDS)
        if scenario == "not_found":
            return self._send(404, "<h1>Postingan tidak ditemukan</h1>")
        if scenario == "forbidden":
            return self._send(403, "<h1>Akses ditolak</h1>")
        if scenario == "server_error":
            return self._send(500, "<h1>Galat server</h1>")
        if scenario == "challenge":
            return self._send(
                200,
                '<!doctype html><html><body><div id="captcha-challenge" data-snr-challenge>'
                "Verifikasi bahwa Anda manusia untuk melanjutkan.</div></body></html>",
            )
        if scenario == "parse_failure":
            return self._send(
                200,
                '<!doctype html><html><body><main id="konten-baru"><div class="x">'
                "Tata letak baru</div></main></body></html>",
            )
        self._send(200, _page(scenario, post, self.server.state.visit(post)))

    def _api(self, query: dict[str, list[str]]) -> None:
        post = (query.get("post") or [""])[0]
        scenario = (query.get("s") or ["complete"])[0]
        try:
            page = int((query.get("page") or ["1"])[0])
        except ValueError:
            return self._send(400, "{}", "application/json")
        if scenario == "partial" and page >= 2:
            return self._send(500, "{}", "application/json")
        if scenario == "login_wall" and page >= 2:
            return self._send(401, "{}", "application/json")
        replies = replies_for(scenario, post, self.server.state.current(post))
        chunk = replies[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        has_next = len(replies) > page * PAGE_SIZE
        html = "".join(_li(r) for r in chunk)
        body = json.dumps({"html": html, "next": page + 1 if has_next else None})
        self._send(200, body, "application/json")


class SimulationHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int]) -> None:
        super().__init__(address, _Handler)
        self.state = _State()


class SimulationServer:
    """Jalankan simulasi pada thread terpisah. `with SimulationServer() as sim: sim.base_url`."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self._server = SimulationHTTPServer((host, port))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self.host = host

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self._server.server_address[1]}"

    def start(self) -> "SimulationServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def reset(self) -> None:
        self._server.state.reset()

    def __enter__(self) -> "SimulationServer":
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()
