import logging

import azure.functions as func


def main(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("Timer trigger is running late.")

    from src.sync_job import run_sync_job

    run_sync_job(trigger="timer")
