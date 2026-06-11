"""The boring core — fetch -> classify -> quarantine -> learn.

This file ties providers, classifiers, and storage together and must NEVER need
editing to add detection or a new mailbox. New smarts go in classifiers/; new
mailboxes go in providers/. The cycle below is the whole engine.
"""

import logging

from coldwar.config import Config, build_classifier, build_provider
from coldwar.signals.fingerprint import fingerprint
from coldwar.storage import Storage

log = logging.getLogger("coldwar.worker")


def run_cycle(account, provider, classifier, store):
    """One pass for one account. This is the contract from the brief, verbatim
    in spirit: classify new mail, quarantine the cold, then learn from drag-backs.
    """
    for msg in provider.fetch_new(since=store.checkpoint(account)):
        verdict = classifier.classify(msg)
        if verdict.is_cold:
            provider.quarantine(msg)
            store.record(account, msg, verdict, fingerprint=fingerprint(msg))
        else:
            # Record the (non-cold) decision too, so the dashboard/fingerprint
            # store reflect everything we have seen.
            store.record(account, msg, verdict, fingerprint=fingerprint(msg))

    for msg in provider.list_unquarantined():        # feedback loop
        classifier.train(msg, is_cold=False)
        store.record_feedback(account, msg, is_cold=False)

    store.advance_checkpoint(account)


def run_all(config: Config, store: Storage) -> None:
    """Run one cycle for every configured account. Errors on one account are
    logged and never stop the others — a wedged mailbox shouldn't halt the worker.
    """
    classifier = build_classifier(config.classifier_names)
    for acct in config.accounts:
        try:
            provider = build_provider(acct.provider).configure(acct.id, store)
            # Skip accounts that haven't completed device auth yet.
            if store.load_tokens(acct.id) is None:
                log.info("account %s not connected yet; skipping", acct.id)
                continue
            run_cycle(acct.id, provider, classifier, store)
            log.info("cycle complete for %s", acct.id)
        except Exception:  # noqa: BLE001 — isolate per-account failures
            log.exception("cycle failed for account %s", acct.id)


def start_worker(config: Config, store: Storage):
    """Start the background scheduler that runs run_all() on an interval.

    Uses APScheduler's BackgroundScheduler so it lives in-process beside Flask —
    no Celery, no Redis. Returns the scheduler so run.py can keep a handle.
    """
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        run_all,
        "interval",
        seconds=config.poll_seconds,
        args=[config, store],
        id="coldwar-cycle",
        next_run_time=None,  # don't fire instantly on boot; first tick after interval
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("worker started: cycle every %ss", config.poll_seconds)
    return scheduler
