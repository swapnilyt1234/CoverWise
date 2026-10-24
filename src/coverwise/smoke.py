"""Fail closed: the pinned SDK has no network-free Agent constructor option."""


def main() -> int:
    print(
        "BLOCKED local-only transport: uagents 0.25.5 Agent.__init__ calls "
        "get_almanac_contract(), which probes ledger contracts regardless of "
        "mailbox/endpoints/registration policy. No supported constructor flag "
        "disables it. No agents or listeners were started by this command. "
        "SDK delivery is not mocked and no network fallback is attempted. "
        "See docs/communication.md."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
