"""`browser_session import|status|clear --platform P`: kelola sesi operator pada profil browser.

Jalankan di worker-browser (satu-satunya yang melihat `browser-profiles/`):
  docker compose run --rm -T worker-browser python manage.py browser_session \
      import --platform x --file - < cookies.json
Nilai cookie tidak pernah dicetak. Hapus berkas sumber setelah impor (`--delete-source`)."""

import shutil
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from collection.browser.runtime import prepare_profile_dir
from collection.browser.session_import import (
    SessionImportError,
    import_session,
    load_cookie_file,
    parse_cookies,
    read_session_summary,
    summarize,
)
from investigations.enums import Platform


def _describe(summary: Any) -> str:
    expiry = (
        summary.earliest_expiry.date().isoformat()
        if summary.earliest_expiry
        else "tanpa kedaluwarsa"
    )
    names = ", ".join(summary.names) or "-"
    return f"{summary.accepted} cookie (kedaluwarsa paling awal: {expiry}); nama: {names}"


class Command(BaseCommand):
    help = "Impor, periksa, atau hapus sesi operator pada profil browser (tanpa mencetak nilai)."

    def add_arguments(self, parser: Any) -> None:
        sub = parser.add_subparsers(dest="action", required=True)
        imp = sub.add_parser("import")
        imp.add_argument("--platform", required=True, choices=[p.value for p in Platform])
        imp.add_argument("--file", required=True, help="berkas JSON cookie, atau - untuk stdin")
        imp.add_argument("--delete-source", action="store_true")
        imp.add_argument(
            "--session-days",
            type=int,
            default=7,
            help="umur cookie sesi (tanpa kedaluwarsa) agar bertahan di profil; 0 = biarkan sesi",
        )
        for name in ("status", "clear"):
            cmd = sub.add_parser(name)
            cmd.add_argument("--platform", required=True, choices=[p.value for p in Platform])

    def handle(self, *args: Any, **options: Any) -> None:
        platform = options["platform"]
        action = options["action"]
        if action == "import":
            self._import(
                platform, options["file"], options["delete_source"], options["session_days"]
            )
        elif action == "status":
            summary = read_session_summary(platform)
            self.stdout.write(
                f"{platform}: " + (_describe(summary) if summary.accepted else "belum ada sesi")
            )
        else:
            profile = prepare_profile_dir(platform)
            for child in profile.iterdir():
                shutil.rmtree(
                    child
                ) if child.is_dir() and not child.is_symlink() else child.unlink()
            self.stdout.write(f"sesi {platform} dihapus (isi profil dikosongkan)")

    def _import(self, platform: str, file: str, delete_source: bool, session_days: int) -> None:
        import sys

        source = None if file == "-" else Path(file)
        try:
            text = sys.stdin.read() if source is None else source.read_text(encoding="utf-8")
            cookies, foreign = parse_cookies(
                load_cookie_file(text), platform, session_days=max(session_days, 0)
            )
        except (SessionImportError, OSError) as exc:
            raise CommandError(str(exc)) from None
        import_session(platform, cookies)
        if delete_source and source is not None:
            source.unlink()
        self.stdout.write(
            f"diimpor ke profil {platform}: {_describe(summarize(cookies, foreign))}"
            + (f"; {foreign} cookie domain lain dibuang" if foreign else "")
        )
