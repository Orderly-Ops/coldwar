#!/usr/bin/env python3
"""Cold War entrypoint — starts Flask AND the background worker together.

The #1 self-hosting confusion is a UI that runs while the worker silently
doesn't. So there is one command: `python run.py`. It boots the worker scheduler
in-process, then serves the Flask UI. Stop both with Ctrl-C.

Optional .env support: if python-dotenv is installed it's loaded; otherwise set
environment variables yourself.
"""

import logging

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001 — dotenv is optional
    pass

from coldwar.app import create_app
from coldwar.config import load_config
from coldwar.storage import Storage
from coldwar.worker import start_worker


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config()
    store = Storage(config.db_path)

    # Start the worker first so it's already cycling when the UI comes up.
    start_worker(config, store)

    app = create_app(config, store)
    # use_reloader=False: the reloader would spawn a second process and a second
    # worker. One process, one worker — that's the whole point of run.py.
    app.run(host=config.host, port=config.port, use_reloader=False)


if __name__ == "__main__":
    main()
