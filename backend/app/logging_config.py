import logging


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Keep third-party libraries quieter than our own app logs.
    for noisy in ("httpx", "httpcore", "google", "googleapiclient", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
