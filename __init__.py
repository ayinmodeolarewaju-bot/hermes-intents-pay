"""Intents Pay — NEAR Intents invoices and cross-chain quotes for Hermes Agent."""

from __future__ import annotations

import logging
from pathlib import Path

from .cli import handle_cli, setup_cli, slash_command
from .schemas import TOOL_SCHEMAS
from .tools import HANDLERS, bind_context

PLUGIN_ID = "intents-pay"
logger = logging.getLogger(__name__)


def register(ctx) -> None:
    """Register tools, the /intents slash command, the CLI, and the bundled skill."""
    bind_context(ctx)
    for name, schema in TOOL_SCHEMAS.items():
        ctx.register_tool(
            name=name,
            toolset="intents-pay",
            schema=schema,
            handler=HANDLERS[name],
        )

    skills_dir = Path(__file__).resolve().parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.is_file():
                ctx.register_skill(child.name, skill_md)

    ctx.register_command(
        "intents",
        slash_command,
        description="Dry-run NEAR Intents quotes and invoices (never moves funds)",
        args_hint="[quote|invoice|tokens|status] ...",
    )
    ctx.register_cli_command(
        name="intents-pay",
        help="Quote a cross-chain payment or inspect an Intents Pay invoice",
        description="NEAR Intents 1-Click quotes and invoices. Dry-run unless a confirmation token is repeated.",
        setup_fn=setup_cli,
        handler_fn=handle_cli,
    )
    logger.debug("intents-pay registered %d tools", len(TOOL_SCHEMAS))
