import json
import logging
import traceback

import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = req.get_json()
    except ValueError:
        payload = {}

    force_full = bool(payload.get("force_full", False))
    try:
        from src.sync_job import run_sync_job

        result = run_sync_job(trigger="http", force_full=force_full)
    except Exception as exc:
        logging.exception("Manual sync failed.")
        return func.HttpResponse(
            json.dumps(
                {
                    "status": "error",
                    "message": str(exc),
                    "exception_type": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                }
            ),
            status_code=500,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps(result),
        status_code=200,
        mimetype="application/json",
    )
