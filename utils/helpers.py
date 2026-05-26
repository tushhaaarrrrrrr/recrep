from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple, Union

import discord

from services.s3_service import upload_image


def format_timestamp(dt: datetime) -> str:
    """
    Convert a datetime to a human-readable UTC string.
    """
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def create_embed(
    title: str,
    fields: List[Tuple[str, str, bool]],
    color: Union[discord.Color, int] = discord.Color.blue()
) -> discord.Embed:
    """
    Create a Discord embed with a title, fields, and a UTC timestamp.
    """
    embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
    for name, value, inline in fields:
        embed.add_field(name=name, value=value, inline=inline)
    return embed


async def upload_attachments(
    interaction: discord.Interaction,
    *attachments: discord.Attachment | None,
    required: bool = True,
) -> list[str] | None:
    """
    Upload non-empty image attachments to S3 and return their URLs.
    """
    files = [attachment for attachment in attachments if attachment is not None]
    if required and not files:
        await interaction.followup.send(
            "❌ **At least one screenshot is required.**",
            ephemeral=True,
        )
        return None

    urls: list[str] = []
    for attachment in files:
        content_type = (attachment.content_type or "").lower()
        if content_type and not content_type.startswith("image/"):
            await interaction.followup.send(
                f"❌ **{attachment.filename}** is not a valid image file.",
                ephemeral=True,
            )
            return None
        data = await attachment.read()
        urls.append(await upload_image(data, attachment.filename))
    return urls


def validate_text_field(value: str | None, field_name: str, max_len: int = 100) -> str | None:
    """Return an error message when a text field is invalid, otherwise None."""
    if value is None or not str(value).strip():
        return f"**{field_name}** cannot be empty."
    if len(str(value).strip()) > max_len:
        return f"**{field_name}** is too long (max {max_len} characters)."
    return None


def validate_numeric_field(
    value: int | float | None,
    field_name: str,
    *,
    minimum: int | float = 1,
    maximum: int | float | None = None,
) -> str | None:
    """Return an error message when a numeric field is outside bounds, otherwise None."""
    if value is None:
        return f"**{field_name}** is required."
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return f"**{field_name}** must be a number."
    if numeric < minimum:
        return f"**{field_name}** must be at least {minimum}."
    if maximum is not None and numeric > maximum:
        return f"**{field_name}** must be at most {maximum}."
    return None


def user_mention(discord_id: int) -> str:
    return f"<@{discord_id}>"


def channel_mention(channel_id: int) -> str:
    return f"<#{channel_id}>"
