"""Explicit live entry point. Imports do not construct agents or load secrets."""

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from uagents import Agent

from coverwise.agents import LOGGER, Coordinator, install_investigator
from coverwise.asi import ASIExplainer
from coverwise.runtime import internal_agent, receivers

COORDINATOR_NAME = "CoverWise Diagnostic"


@dataclass(repr=False)
class LiveSettings:
    api_key: str
    coordinator_seed: str
    investigator_seed: str
    request_timeout: float
    provider_seed: str

    @classmethod
    def from_environment(cls):
        names = (
            "ASI1_API_KEY",
            "COVERWISE_PERSONAL_AGENT_SEED",
            "COVERWISE_INVESTIGATOR_AGENT_SEED",
            "COVERWISE_PROVIDER_AGENT_SEED",
        )
        missing = [name for name in names if not os.environ.get(name, "").strip()]
        if missing:
            raise ValueError("Missing required settings: " + ", ".join(missing))
        values = [os.environ[name] for name in names]
        if len(set(values[1:])) != 3:
            raise ValueError(
                "Coordinator, investigator and provider seeds must be distinct"
            )
        try:
            timeout = float(os.environ.get("COVERWISE_REQUEST_TIMEOUT_SECONDS", "15"))
        except ValueError:
            raise ValueError("Request timeout must be numeric") from None
        if not 0.05 <= timeout <= 30:
            raise ValueError("Request timeout must be between 0.05 and 30 seconds")
        return cls(values[0], values[1], values[2], timeout, values[3])


async def run(settings: LiveSettings):
    from coverwise.provider import install_provider

    investigator = internal_agent("investigator", settings.investigator_seed)
    provider = internal_agent("provider", settings.provider_seed)
    coordinator = Agent(
        name=COORDINATOR_NAME,
        seed=settings.coordinator_seed,
        port=8001,
        mailbox=True,
        publish_agent_details=True,
        store_message_history=False,
        handle_messages_concurrently=True,
        description="Connectivity diagnostic only. Send /diagnose <text>.",
    )
    configure_logging(settings.request_timeout)
    service = Coordinator(
        investigator.address,
        timeout=settings.request_timeout,
        explainer=ASIExplainer(settings.api_key),
        provider=provider.address,
    )
    install_investigator(investigator, coordinator.address)
    install_provider(provider, coordinator.address)
    service.install(coordinator, live=True)
    async with receivers(investigator, provider):
        await coordinator.run_async()


def configure_logging(request_timeout: float | None = None):
    # SDK construction can lower all existing loggers to WARNING; restore ours after it.
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    if not LOGGER.handlers:
        LOGGER.addHandler(logging.StreamHandler())
    for handler in LOGGER.handlers:
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    LOGGER.info("role=coordinator event=logging_ready level=INFO")
    if request_timeout is not None:
        LOGGER.info(
            "role=coordinator event=configuration request_timeout_seconds=%.3f "
            "timeout_source=LiveSettings dotenv_override=False",
            request_timeout,
        )


def main() -> int:
    load_dotenv(Path.cwd() / ".env", override=False)
    try:
        settings = LiveSettings.from_environment()
    except ValueError as exc:
        print(f"Live startup refused: {exc}")
        return 1
    logging.basicConfig(level=logging.INFO)
    for name in ("httpx", "httpcore", "openai"):
        logging.getLogger(name).setLevel(logging.WARNING)
    asyncio.run(run(settings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
