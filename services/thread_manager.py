import discord
from datetime import datetime, timezone
from utils.logger import get_logger

logger = get_logger(__name__)


class ThreadManager:
    @staticmethod
    async def get_or_create_monthly_thread(guild: discord.Guild, channel_id: int, prefix: str) -> discord.Thread:
        """
        Get an existing monthly thread or create a new one.

        Thread name format: "{prefix} for {Month} {Year}"
        """
        channel = guild.get_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found in guild {guild.id}")

        now = datetime.now(timezone.utc)
        month_name = now.strftime("%B")
        year = now.year
        thread_name = f"{prefix} for {month_name} {year}"

        # Check existing threads
        for thread in channel.threads:
            if thread.name == thread_name:
                return thread

        # Create a new thread
        try:
            thread = await channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.public_thread,
                auto_archive_duration=10080  # 7 days
            )
            logger.info(f"Created new monthly thread '{thread_name}' in channel {channel.id}")
            return thread
        except discord.Forbidden:
            logger.error(f"Missing permissions to create threads in channel {channel.id}")
            raise PermissionError(f"Bot lacks 'Create Public Threads' permission in {channel.mention}")
        except Exception as e:
            logger.exception(f"Failed to create thread in channel {channel.id}: {e}")
            raise

    @staticmethod
    async def send_notification(guild: discord.Guild, channel_id: int, prefix: str, message: str):
        """Send a notification message to the monthly thread."""
        try:
            thread = await ThreadManager.get_or_create_monthly_thread(guild, channel_id, prefix)
            await thread.send(message)
            logger.debug(f"Notification sent to thread {thread.name}: {message[:100]}")
        except Exception as e:
            logger.error(f"Failed to send notification to thread: {e}")