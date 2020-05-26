from datetime import datetime
from discord import Member, Message, Reaction, Role, TextChannel, User
from discord.ext.commands import Bot, CommandInvokeError, DefaultHelpCommand, Context, Converter, Greedy
from emoji import get_emoji_regexp
from os import environ
from re import compile, findall, UNICODE
from typing import Union

from .cogs import BirthdayManager, EventsManager, ImpersonateManager, PollManager, RolesManager, RollManager, StatsManager, StatusManager
from .util import redis

__all__ = ["bot"]

bot = Bot(command_prefix='>', help_command=DefaultHelpCommand(dm_help=True))

bot.add_cog(BirthdayManager(bot))
bot.add_cog(EventsManager(bot))
bot.add_cog(ImpersonateManager(bot))
bot.add_cog(PollManager(bot))
bot.add_cog(RolesManager(bot))
bot.add_cog(RollManager(bot))
bot.add_cog(StatsManager(bot))
bot.add_cog(StatusManager(bot))

discord_emojis = r'<a?:[a-zA-Z0-9\_]+:[0-9]+>'

unicode_emojis = get_emoji_regexp()

@bot.event
async def on_ready():
  admin_id = environ.get("SAFETY_ADMIN_ID")

  if admin_id:
    admin = await bot.fetch_user(int(admin_id))
    await admin.send(f"I started up at {str(datetime.now())}")

@bot.event
async def on_message(message: Message):
  if message.content.startswith(">"):
    await bot.process_commands(message)

    if message.content.startswith(">uses"):
      return
  
  if message.author.id == bot.user.id:
    pass
  elif isinstance(message.author, Member) and isinstance(message.channel, TextChannel):
    key = f"{message.author.id}:{message.channel.guild.id}"
    
    user_reacts = redis.hgetall(key)

    if user_reacts.get("consent") == "1":
      unicode_emoji_list = findall(unicode_emojis, message.content)

      for emoji in unicode_emoji_list:
        if emoji in user_reacts:
          user_reacts[emoji] = int(user_reacts[emoji]) + 1
        else: 
          user_reacts[emoji] = 1

      discord_emoji_list = findall(discord_emojis, message.content)

      for custom_emoji in discord_emoji_list:
        if custom_emoji in user_reacts:
          user_reacts[custom_emoji] = int(user_reacts[custom_emoji]) + 1
        else:
          user_reacts[custom_emoji] = 1

      redis.hmset(key, user_reacts)

@bot.event
async def on_reaction_add(react: Reaction, user: Union[Member, User]):
  if isinstance(user, Member) and isinstance(react.message.channel, TextChannel):
    key = f"{user.id}:{react.message.channel.guild.id}"
    
    user_reacts = redis.hgetall(key)

    if user_reacts.get("consent") == "1":
      emoji_str = str(react.emoji)

      if emoji_str in user_reacts:
        redis.hset(key, emoji_str, int(user_reacts[emoji_str]) + 1)
      else:
        redis.hset(key, emoji_str, 1)

@bot.event
async def on_reaction_remove(react: Reaction, user: Union[Member, User]):
  if isinstance(user, Member) and isinstance(react.message.channel, TextChannel):
    key = f"{user.id}:{react.message.channel.guild.id}"
    
    user_reacts = redis.hgetall(key)

    if user_reacts.get("consent") == "1":
      emoji_str = str(react.emoji)

      if emoji_str in user_reacts:
        new_count = int(user_reacts[emoji_str]) - 1

        if new_count == 0:
          redis.hdel(key, emoji_str)
        else:
          redis.hset(key, emoji_str, new_count)
