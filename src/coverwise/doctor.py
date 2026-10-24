"""Offline SDK compatibility check. Never instantiate agents or clients."""

import sys
from importlib.metadata import version

DEPENDENCIES = (
    "coverwise",
    "uagents",
    "uagents-core",
    "pydantic",
    "openai",
    "python-dotenv",
    "pytest",
    "ruff",
)


def main() -> int:
    print(f"Python {sys.version.split()[0]} ({sys.executable})")
    try:
        versions = {name: version(name) for name in DEPENDENCIES}
        for name, installed in versions.items():
            print(f"{name}=={installed}")
        if sys.version_info[:2] != (3, 12):
            raise RuntimeError("Python 3.12 is required")
        if versions["uagents"] != "0.25.5":
            raise RuntimeError("expected uagents==0.25.5")

        from uagents_core.contrib.protocols.chat import (
            ChatAcknowledgement,
            ChatMessage,
            MetadataContent,
            TextContent,
            chat_protocol_spec,
        )

        for symbol in (ChatMessage, ChatAcknowledgement, TextContent, MetadataContent):
            if not isinstance(symbol, type):
                raise RuntimeError("required chat model is not a class")
            print(f"SDK symbol: {symbol.__name__}")
        actual = (chat_protocol_spec.name, chat_protocol_spec.version)
        print(f"Protocol: {actual[0]} {actual[1]}")
        if actual != ("AgentChatProtocol", "0.3.0"):
            raise RuntimeError("expected AgentChatProtocol 0.3.0")
    except Exception as exc:
        print(f"INCOMPATIBLE: {exc}", file=sys.stderr)
        print(
            "Use .venv Python 3.12 and run uv sync --locked --dev; "
            "if it persists, compare SDK metadata with docs/architecture.md.",
            file=sys.stderr,
        )
        return 1
    print("PASS: local SDK compatibility only; no live integration verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
