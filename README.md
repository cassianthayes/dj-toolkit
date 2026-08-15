# dj-toolkit

A small CLI for downloading tracks from Yandex Music to keep your DJ library fresh.

You need to login with your Yandex Music token, obtain via [yandex-music-token](https://addons.mozilla.org/en-US/firefox/addon/yandex-music-token/).

This CLI downloads tracks without tags and album art.

This is AI generated, use at your own risk.

## Install

```sh
uv tool install https://github.com/cassianthayes/dj-toolkit.git
```

## Usage

```sh
# store your Yandex Music auth token
dj-toolkit login

# download a track by link into ~/Music/dj-toolkit as "Author - Track"
dj-toolkit get <track-link>

# optionally trim a part of the track (seconds or MM:SS)
dj-toolkit get <track-link> --from 0:30 --to 1:30
```

Already-downloaded tracks are skipped. Explicit tracks get a warning.

Requires `ffmpeg` for trimming.

## Credits

All code was written by opencode (Deepseek V4 Flash Free).
