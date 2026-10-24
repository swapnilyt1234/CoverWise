"""Predefined ASI:One v1 fields from the official Interactive Cards reference."""

import json
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    MetadataContent,
    TextContent,
)

from coverwise.contracts import Contract
from coverwise.policies import MAX_REPLY

Label = Annotated[str, StringConstraints(min_length=1, max_length=240)]
Value = Annotated[str, StringConstraints(max_length=12000)]


class CTA(Contract):
    label: Label
    selection: dict[str, str]
    primary: bool | None = None


class Option(Contract):
    value: Label
    label: Label


class FormField(Contract):
    name: Label
    kind: Literal["text", "select"]
    label: Label
    required: bool = False
    options: list[Option] | None = None

    @model_validator(mode="after")
    def choices(self):
        if (self.kind == "select") != bool(self.options):
            raise ValueError("select requires options; text must not have options")
        return self


class Form(Contract):
    title: Label
    fields: list[FormField] = Field(min_length=1, max_length=20)
    submit_cta: CTA


class Row(Contract):
    label: Label
    value: Value


class Detail(Contract):
    title: Label
    summary_rows: list[Row] = Field(min_length=1, max_length=40)
    ctas: list[CTA] = Field(max_length=8)


class Review(Contract):
    title: Label
    summary_rows: list[Row] = Field(min_length=1, max_length=40)
    approve_cta: CTA
    reject_cta: CTA


class Badge(Contract):
    label: Label
    variant: Literal["info", "success", "warning"]


class Item(Contract):
    id: Label
    title: Label
    subtitle: Value
    badges: list[Badge]
    secondary_text: Value
    primary_cta: CTA


class Carousel(Contract):
    title: Label
    subtitle: Value
    items: list[Item] = Field(min_length=1, max_length=3)


KINDS = {Form: "form", Detail: "detail", Review: "review", Carousel: "carousel"}


def message(text, payload):
    # The wire allows 64KB; retain CoverWise's stricter combined reply bound.
    kind = KINDS[type(payload)]
    payload = type(payload).model_validate(payload.model_dump())
    encoded = json.dumps(payload.model_dump(exclude_none=True), ensure_ascii=False)
    metadata = dict(
        card_protocol_version="1",
        requires_card_interaction="true",
        card_kind=kind,
        card_payload=encoded,
    )
    if isinstance(payload, Detail) and not payload.ctas:
        metadata["is_terminal"] = "true"
    if (
        len(encoded.encode("utf-8")) > 65536
        or len((text + json.dumps(metadata, ensure_ascii=False)).encode("utf-8"))
        > MAX_REPLY
    ):
        raise ValueError("Card exceeds the reply size bound. Use exact commands.")
    return ChatMessage(
        content=[
            TextContent(text=text),
            MetadataContent(type="metadata", metadata=metadata),
        ]
    )
