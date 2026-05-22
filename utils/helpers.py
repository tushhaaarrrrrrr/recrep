import discord
from datetime import datetime, timezone
from typing import List, Tuple, Union


def format_timestamp(dt: datetime) -> str:
    """
    Convert a datetime to a human-readable UTC string.

    Args:
        dt: The datetime object (should be timezone-aware).

    Returns:
        String like '2025-04-05 22:30:15 UTC'.
    """
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def create_embed(
    title: str,
    fields: List[Tuple[str, str, bool]],
    color: Union[discord.Color, int] = discord.Color.blue()
) -> discord.Embed:
    """
    Create a Discord embed with a title, fields, and a UTC timestamp.

    Args:
        title: Embed title.
        fields: List of (name, value, inline) tuples.
        color: Embed color (default blue).

    Returns:
        A ready-to-send discord.Embed.
    """
    embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
    for name, value, inline in fields:
        embed.add_field(name=name, value=value, inline=inline)
    return embed


def user_mention(discord_id: int) -> str:
    """
    Return a string that mentions a Discord user by ID.

    Args:
        discord_id: The user's numeric ID.

    Returns:
        A mention string like '<@123456789012345678>'.
    """
    return f"<@{discord_id}>"


def channel_mention(channel_id: int) -> str:
    """
    Return a string that mentions a Discord channel by ID.

    Args:
        channel_id: The channel's numeric ID.

    Returns:
        A mention string like '<#123456789012345678>'.
    """
    return f"<#{channel_id}>"