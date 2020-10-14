"""
Created by Epic at 10/14/20
"""
from main import Bot
from .api import Api
from utils import get_matchmaking_type_by_id

from discord.ext.commands import Cog
from discord import VoiceState, Member
from asyncio import Lock
from typing import Dict
from logging import getLogger


class Queue(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = getLogger("AQue.cogs.queue")
        self.locks: Dict[int, Dict[str, Lock]] = {}
        self.lobby_channels: Dict[int, Dict[str, int]] = {}
        self.game_channels = []
        self.lobby_users = 1
        self.lobby_deletion_threshold = 0

    def is_lobby_vc(self, channel: int, guild_id: int):
        return any([channel_id == channel for channel_id in list(self.lobby_channels[guild_id].values())])

    @Cog.listener("on_voice_state_update")
    async def move_to_lobbies(self, member: Member, before: VoiceState, after: VoiceState):
        if before.channel == after.channel or after.channel is None or member.bot:
            return
        guild = member.guild
        api: Api = self.bot.get_cog("Api")
        guild_config = api.get_server_settings(guild)

        if guild_config is None:
            return
        match_type = get_matchmaking_type_by_id(after.channel.id, guild_config["matchmaking_channels"])
        if match_type is None:
            return
        guild_locks = self.locks.get(guild.id, None)
        if guild_locks is None:
            guild_locks = {}
            self.locks[guild.id] = {}
        game_lock = guild_locks.get(match_type, None)
        if game_lock is None:
            game_lock = Lock()
            self.locks[guild.id][match_type] = game_lock

        async with game_lock:
            guild_lobbies = self.lobby_channels.get(guild.id, {})
            lobby_vc = guild_lobbies.get(match_type, None)
            if lobby_vc is None:
                lobby_category = self.bot.get_channel(guild_config["categories"]["lobby"])
                lobby_vc = (await lobby_category.create_voice_channel(name=match_type)).id
                guild_lobbies[match_type] = lobby_vc
                self.lobby_channels[guild.id] = guild_lobbies
            voice = self.bot.get_channel(lobby_vc)
            await member.move_to(voice, reason="[AQue] Assembling lobby")

    @Cog.listener("on_voice_state_update")
    async def start_games(self, member: Member, before: VoiceState, after: VoiceState):
        if before.channel == after.channel or after.channel is None or member.bot:
            return

        guild = member.guild
        api: Api = self.bot.get_cog("Api")
        guild_config = api.get_server_settings(guild)

        if guild_config is None:
            return
        lobby_category_id = guild_config["categories"]["lobby"]
        in_game_category = self.bot.get_channel(guild_config["categories"]["in_game"])
        voice_channel = after.channel

        if voice_channel.category_id != lobby_category_id:
            return
        game_type = voice_channel.name
        async with self.locks[guild.id][game_type]:
            if len(voice_channel.members) < self.lobby_users:
                return
            await voice_channel.edit(category=in_game_category, name="Use /code <code>", reason="[AQue] Lobby found.")
            del self.lobby_channels[guild.id][game_type]

    @Cog.listener("on_voice_state_update")
    async def delete_lobbies_on_empty(self, member: Member, before: VoiceState, after: VoiceState):
        if after.channel is not None and before.channel != after.channel and not member.bot:
            return
        guild = member.guild
        api: Api = self.bot.get_cog("Api")
        guild_config = api.get_server_settings(guild)

        if guild_config is None:
            return
        in_game_category_id = guild_config["categories"]["in_game"]
        if before.channel.category_id != in_game_category_id:
            return
        if len(before.channel.members) <= self.lobby_deletion_threshold:
            await before.channel.delete(reason="[AQue] Lobby is empty.")

    async def post_queue_stats(self, queue_game: str, guild_name: str, queue_size: int):
        pass  # Kekw cant be assed


def setup(bot: Bot):
    bot.add_cog(Queue(bot))