import argparse
import getpass
import os
import pathlib
import re
import shutil
import subprocess
import sys

from yandex_music import Client
from yandex_music.exceptions import YandexMusicError


def _colorize(text: str, code: int) -> str:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def _token_path() -> pathlib.Path:
    data_home = (
        os.environ.get("XDG_DATA_HOME") or pathlib.Path.home() / ".local" / "share"
    )
    return pathlib.Path(data_home) / "dj-toolkit" / "token.txt"


def _music_dir() -> pathlib.Path:
    return pathlib.Path.home() / "Music" / "dj-toolkit"


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def _is_explicit(track) -> bool:
    return (
        bool(track.explicit)
        or track.content_warning == "explicit"
        or track.is_suitable_for_children is False
    )


def _parse_track_id(url: str) -> str | None:
    match = re.search(r"/album/(\d+)/track/(\d+)", url)
    if match:
        return f"{match.group(2)}:{match.group(1)}"
    match = re.search(r"/track/(\d+)", url)
    return match.group(1) if match else None


def _parse_time(value: str) -> float | None:
    value = value.strip()
    match = re.fullmatch(r"(\d+):([0-5]?\d)", value)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    match = re.fullmatch(r"\d+(?:\.\d+)?", value)
    return float(value) if match else None


def _trim(path: pathlib.Path, start: float | None, end: float | None) -> None:
    tmp = path.with_suffix(".tmp.mp3")
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(path)]
    if start is not None and end is not None:
        cmd += ["-t", str(end - start)]
    elif end is not None:
        cmd += ["-to", str(end)]
    cmd += ["-c", "copy", str(tmp)]
    subprocess.run(cmd, check=True, capture_output=True)
    tmp.replace(path)


def cmd_login(_args: argparse.Namespace) -> int:
    token = getpass.getpass("Auth token: ").strip()
    if not token:
        print(_colorize("Error: token cannot be empty", 31), file=sys.stderr)
        return 1
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    print(_colorize(f"Token stored at {path}", 32))
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    token_path = _token_path()
    if not token_path.exists():
        print(
            _colorize("Error: no token found, run 'dj-toolkit login' first", 31),
            file=sys.stderr,
        )
        return 1
    token = token_path.read_text(encoding="utf-8").strip()
    if not token:
        print(
            _colorize("Error: token is empty, run 'dj-toolkit login' again", 31),
            file=sys.stderr,
        )
        return 1

    track_id = _parse_track_id(args.url)
    if not track_id:
        print(
            _colorize(f"Error: not a Yandex Music track link: {args.url}", 31),
            file=sys.stderr,
        )
        return 1

    if args.start is not None and args.end is not None and args.start >= args.end:
        print(_colorize("Error: --from must be earlier than --to", 31), file=sys.stderr)
        return 1
    if (args.start is not None or args.end is not None) and shutil.which(
        "ffmpeg"
    ) is None:
        print(_colorize("Error: ffmpeg is required for trimming", 31), file=sys.stderr)
        return 1

    try:
        client = Client(token).init()
    except YandexMusicError as exc:
        print(_colorize(f"Error: failed to authorize: {exc}", 31), file=sys.stderr)
        return 1

    try:
        track = client.tracks(track_id)[0]
    except (YandexMusicError, IndexError) as exc:
        print(_colorize(f"Error: failed to fetch track: {exc}", 31), file=sys.stderr)
        return 1

    if not track.available or track.error:
        print(
            _colorize(
                f"Error: track is not available: {track.error or 'unknown reason'}", 31
            ),
            file=sys.stderr,
        )
        return 1

    name = f"{', '.join(track.artists_name())} - {track.title}"
    out_dir = _music_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_safe_name(name)}.mp3"

    if out_path.exists():
        print(_colorize(f"Skipped, already downloaded: {name}", 33))
        return 0

    if _is_explicit(track):
        print(_colorize(f"Warning: track may contain explicit content: {name}", 33))

    print(_colorize(f"Downloading: {name}", 36))
    try:
        track.download(str(out_path), bitrate_in_kbps=320)
    except YandexMusicError as exc:
        print(_colorize(f"Error: download failed: {exc}", 31), file=sys.stderr)
        return 1

    if args.start is not None or args.end is not None:
        try:
            _trim(out_path, args.start, args.end)
        except (subprocess.CalledProcessError, OSError) as exc:
            print(_colorize(f"Error: trimming failed: {exc}", 31), file=sys.stderr)
            return 1
        print(_colorize(f"Trimmed to {args.start or 0}:{args.end or 'end'}", 33))

    print(_colorize(f"Downloaded: {out_path}", 32))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="dj-toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("login", help="Prompt for an auth token and store it")
    get = subparsers.add_parser(
        "get", help="Download a track from Yandex Music by link"
    )
    get.add_argument(
        "url",
        help="Track link, e.g. https://music.yandex.ru/album/1193829/track/10994777",
    )
    get.add_argument(
        "--from",
        dest="start",
        metavar="TIME",
        type=_parse_time,
        default=None,
        help="Trim start time, e.g. 30 or 0:30",
    )
    get.add_argument(
        "--to",
        dest="end",
        metavar="TIME",
        type=_parse_time,
        default=None,
        help="Trim end time, e.g. 90 or 1:30",
    )
    args = parser.parse_args()

    if args.command == "login":
        sys.exit(cmd_login(args))
    elif args.command == "get":
        sys.exit(cmd_get(args))
