"""Worker entry point.

The durable job schema and source adapters are intentionally added in later
phases. Keeping this process separate from FastAPI prevents long-running
ingestion from delaying public API requests.
"""

import logging

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info(
        "Tokyo Event Map worker is configured (environment=%s, ollama_enabled=%s)",
        settings.app_env,
        settings.ollama_enabled,
    )
    logger.info("No jobs are registered in architecture setup phase; worker exits cleanly.")


if __name__ == "__main__":
    main()
