"""Commit + push index.html i calibration.json po dziennej kalibracji.

Token czytany z workspace-root .env (GITHUB_TOKEN), nigdy nie zapisywany w repo.
"""
import subprocess
from datetime import date
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ENV = PROJECT.parents[1] / ".env"


def token() -> str:
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("GITHUB_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("Brak GITHUB_TOKEN w .env")


def main() -> None:
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=PROJECT, capture_output=True, text=True)

    status = git("status", "--porcelain").stdout.strip()
    if not status:
        print("push_pages: brak zmian")
        return
    git("add", "index.html", "outputs/calibration.json")
    git("commit", "-m", f"daily calibration {date.today().isoformat()}")
    url = f"https://{token()}@github.com/vente-europe/btc-grid-engine.git"
    r = git("push", url, "master:main")
    print("push_pages:", "OK" if r.returncode == 0 else f"BLAD {r.stderr[-200:]}")


if __name__ == "__main__":
    main()
