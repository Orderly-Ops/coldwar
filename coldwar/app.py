"""Flask factory, routes, and the minimal UI.

Two screens:
  - /connect   : run the device-code flow (show user_code + URL, poll to finish)
  - /           : the dashboard — quarantined mail with the reasons that fired,
                  plus a "not cold" action that feeds the feedback loop.

The app holds a per-account provider instance in memory so the device-flow's
begin/poll pair share the same _pending_device_code across requests.
"""

import logging

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from coldwar.config import Config, build_provider, load_config
from coldwar.storage import Storage

log = logging.getLogger("coldwar.app")


def create_app(config: Config | None = None, store: Storage | None = None) -> Flask:
    config = config or load_config()
    store = store or Storage(config.db_path)

    app = Flask(__name__)
    app.secret_key = config.secret_key
    app.config["coldwar"] = config
    app.config["store"] = store

    # Cache of configured provider instances, keyed by account id, so the
    # device-flow begin/poll pair shares state within a connect session.
    providers: dict[str, object] = {}

    def provider_for(account_id: str):
        if account_id not in providers:
            acct = next((a for a in config.accounts if a.id == account_id), None)
            if acct is None:
                return None
            providers[account_id] = build_provider(acct.provider).configure(account_id, store)
        return providers[account_id]

    # --- Dashboard --------------------------------------------------------

    @app.route("/")
    def dashboard():
        quarantined = store.quarantined()
        accounts = [
            {
                "id": a.id,
                "provider": a.provider,
                "connected": store.load_tokens(a.id) is not None,
            }
            for a in config.accounts
        ]
        return render_template(
            "dashboard.html", quarantined=quarantined, accounts=accounts
        )

    # --- Connect (device-code flow) --------------------------------------

    @app.route("/connect/<account_id>")
    def connect(account_id):
        provider = provider_for(account_id)
        if provider is None:
            flash(f"Unknown account: {account_id}", "error")
            return redirect(url_for("dashboard"))
        info = provider.begin_device_auth()
        return render_template("connect.html", account_id=account_id, info=info)

    @app.route("/connect/<account_id>/poll", methods=["POST"])
    def connect_poll(account_id):
        """Browser polls this; returns {"done": true} once the user consents."""
        provider = provider_for(account_id)
        if provider is None:
            return jsonify({"error": "unknown account"}), 404
        try:
            done = provider.poll_device_auth()
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": str(exc)}), 400
        return jsonify({"done": bool(done)})

    # --- Feedback: "not cold" --------------------------------------------

    @app.route("/feedback/not-cold", methods=["POST"])
    def not_cold():
        """User says a quarantined message was a false positive.

        Record the feedback now; the worker's classifier.train() also runs when
        it next sees the message moved back. We just persist the explicit signal.
        """
        from coldwar.models import Message

        account = request.form["account"]
        message_id = request.form["message_id"]
        store.record_feedback(account, Message(id=message_id, sender="", sender_domain="", subject="", body_text=""), is_cold=False)
        flash("Marked as not cold. Future similar mail is less likely to be quarantined.", "ok")
        return redirect(url_for("dashboard"))

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    return app
