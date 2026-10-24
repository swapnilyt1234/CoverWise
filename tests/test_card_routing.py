import asyncio
import json
import logging
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_cards import click, harness, payload
from test_sandbox import insurer as insurer

from coverwise.transport import CandidateAssessmentRequest, CatalogueRequest


@pytest.mark.parametrize("mention", [False, True])
@pytest.mark.parametrize("ending", ["", "\n", "\r\n", "   "])
def test_existing_cover_form_callback_preserves_selection_and_reaches_review(
    insurer, monkeypatch, caplog, mention, ending
):
    caplog.set_level(logging.INFO, logger="coverwise")

    async def run():
        h = harness(insurer, monkeypatch)
        await h.ask("/cards")
        _, home = payload(h)
        choice = next(i for i in home["items"] if i["id"] == "example")
        prefix = f"@{h.address} " if mention else ""

        async def send(selection, **values):
            await h.ask(prefix + json.dumps({**selection, **values}) + ending)

        await send(choice["primary_cta"]["selection"])
        kind, form = payload(h)
        assert kind == "form" and form["title"] == "Try an example"
        selection = form["submit_cta"]["selection"]
        assert set(selection) == {"action", "card_token"}
        assert selection != choice["primary_cta"]["selection"]
        assert h.service.cards.actions[selection["card_token"]].kind == "example"
        await send(selection, sample_cover="existing-personal", approved=True)
        kind, review = payload(h)
        assert kind == "review" and review["title"] == "Review details"
        record = h.service.cards.actions[
            review["approve_cta"]["selection"]["card_token"]
        ]
        assert record.data.inputs.path == "existing-personal"
        assert "Existing personal cover retained" in str(review)
        await send(review["approve_cta"]["selection"], approved=True)
        kind, result = payload(h)
        assert kind == "carousel" and result["title"] == "Your plan comparison"
        assert isinstance(h.requests[-2], CatalogueRequest)
        assert isinstance(h.requests[-1], CandidateAssessmentRequest)
        assert json.loads(h.requests[-1].input_json)["path"] == "existing-personal"
        assert insurer.store.counts()["payments"] == 0
        assert not h.model_calls
        messages = [
            r.getMessage()
            for r in caplog.records
            if "event=card_transition" in r.getMessage()
        ]
        assert any("source=entry_command action=entry_command" in m for m in messages)
        assert any(
            "action=entry prior_stage=entry next_stage=example" in m for m in messages
        )
        assert any(
            "action=example prior_stage=example next_stage=input_review "
            "validation=accepted fallback_reason=none" in m
            for m in messages
        )
        assert any(
            "action=confirm prior_stage=input_review next_stage=results" in m
            for m in messages
        )
        assert selection["card_token"] not in caplog.text
        assert review["approve_cta"]["selection"]["card_token"] not in caplog.text
        assert "1992-04-10" not in caplog.text
        await h.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "case",
    [
        "invalid",
        "missing_selection",
        "unknown",
        "wrong_session",
        "expired",
        "used",
        "exception",
    ],
)
def test_bad_callbacks_offer_explicit_restart_without_home_or_payment(
    insurer, monkeypatch, caplog, case
):
    caplog.set_level(logging.INFO, logger="coverwise")

    async def run():
        h = harness(insurer, monkeypatch)
        await h.ask("/cards")
        _, home = payload(h)
        await click(h, home["items"][2]["primary_cta"])
        _, form = payload(h)
        selection = form["submit_cta"]["selection"]
        body = dict(**selection, sample_cover="existing-personal", approved=True)
        kwargs = {}
        if case == "missing_selection":
            body.pop("card_token")
        elif case == "unknown":
            body["card_token"] = "x" * 32
        elif case == "wrong_session":
            kwargs["session"] = uuid4()
        elif case == "expired":
            h.service.cards.actions[selection["card_token"]].expires = 0
        elif case == "used":
            await h.ask(json.dumps(body))
            assert payload(h)[0] == "review"
        elif case == "exception":
            monkeypatch.setattr(
                h.service.cards,
                "dispatch",
                AsyncMock(side_effect=RuntimeError("private-profile-marker")),
            )
        text = "{invalid" if case == "invalid" else json.dumps(body)
        await h.ask(text, **kwargs)
        kind, recovery = payload(h)
        assert kind == "detail" and recovery["title"] != "Let's check your insurance"
        assert [c["label"] for c in recovery["ctas"]] == ["Restart cards"]
        assert insurer.store.counts()["payments"] == 0
        assert "private-profile-marker" not in h.messages[-1].text()
        assert "private-profile-marker" not in caplog.text
        assert selection["card_token"] not in caplog.text
        assert "1992-04-10" not in caplog.text
        expected = {
            "invalid": "malformed_callback",
            "missing_selection": "missing_selection",
            "unknown": "unknown_or_wrong_scope",
            "wrong_session": "missing_session",
            "expired": "unknown_or_wrong_scope",
            "used": "already_used",
            "exception": "internal_error",
        }[case]
        assert "fallback_reason=" + expected in caplog.text
        if case != "exception":
            await click(h, recovery["ctas"][0], **kwargs)
            assert payload(h)[1]["title"] == "Let's check your insurance"
        await h.close()

    asyncio.run(run())


def test_replayed_entry_command_does_not_reset_pending_form(insurer, monkeypatch):
    async def run():
        h = harness(insurer, monkeypatch)
        await h.ask("/cards")
        _, home = payload(h)
        await click(h, home["items"][2]["primary_cta"])
        _, form = payload(h)
        session = h.service.cards.sessions[("client", insurer.session)]
        epoch = session.epoch
        await h.ask("/cards")
        kind, recovery = payload(h)
        assert kind == "detail", "Repeated entry must not silently return the home menu"
        assert session.epoch == epoch
        assert any(c["label"] == "Restart cards" for c in recovery["ctas"])
        await click(
            h, form["submit_cta"], dict(sample_cover="existing-personal", approved=True)
        )
        assert payload(h)[0] == "review"
        await h.close()

    asyncio.run(run())
