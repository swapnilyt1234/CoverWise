"""Internal live-process investigator runtime; not a safe offline constructor."""

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager

from uagents import Agent
from uagents.dispatch import dispatcher
from uagents.resolver import Resolver


class NoExternalResolver(Resolver):
    async def resolve(self, destination: str):
        return None, []


def internal_agent(role: str, seed: str | None = None) -> Agent:
    # SDK construction itself probes ledger contracts; call only in explicit live mode.
    return Agent(
        name=f"coverwise-{role}",
        seed=seed or secrets.token_hex(32),
        resolve=NoExternalResolver(),
        mailbox=False,
        endpoint=[],
        enable_agent_inspector=False,
        publish_agent_details=False,
        store_message_history=False,
        handle_messages_concurrently=True,
        mark_inactive_on_shutdown=False,
        log_level=logging.WARNING,
    )


@asynccontextmanager
async def receivers(*agents: Agent):
    before = asyncio.all_tasks()
    workers = set()
    try:
        for agent in agents:
            agent.start_message_receivers()
        workers = asyncio.all_tasks() - before
        yield
    finally:
        # SDK 0.25.5 has no public receiver-stop API; pin these task attributes.
        try:
            for task in workers:
                task.cancel()
            await asyncio.wait_for(
                asyncio.gather(*workers, return_exceptions=True), timeout=2
            )
        finally:
            try:
                handlers = set().union(*(agent._message_tasks for agent in agents))
                for task in handlers:
                    task.cancel()
                await asyncio.wait_for(
                    asyncio.gather(*handlers, return_exceptions=True), timeout=2
                )
            finally:
                for agent in agents:
                    dispatcher.unregister(agent.address, agent)
