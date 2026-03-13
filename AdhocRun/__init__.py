import json
import logging
import traceback

import azure.functions as func


def _read_force_full(req: func.HttpRequest) -> bool:
    force_from_query = req.params.get("force_full")
    if force_from_query is not None:
        return force_from_query.strip().lower() in ("1", "true", "yes", "y")
    try:
        payload = req.get_json()
    except ValueError:
        payload = {}
    return bool(payload.get("force_full", False))


def main(req: func.HttpRequest) -> func.HttpResponse:
    force_full = _read_force_full(req)
    try:
        from src.sync_job import run_sync_job

        result = run_sync_job(trigger="adhoc", force_full=force_full)
    except Exception as exc:
        logging.exception("Adhoc sync failed.")
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
