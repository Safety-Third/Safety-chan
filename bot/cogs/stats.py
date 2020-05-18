from discord import Guild, Member, TextChannel, User
from discord.ext.commands import Bot, Context, command, CommandInvokeError, guild_only
from typing import Callable, Optional, Tuple, Union

from .base import CustomCog
from ..util import redis

__all__ = ["StatsManager"]

GuildIdOrNumber = Optional[Union[int, str]]
GuildAndKey = Tuple[str, str]

def get_key_from_context(ctx: Context) -> GuildAndKey:
  """
  Returns the guild name, and a string representing the key in the form user:guild

  Args:
    ctx: the context for the message
  Returns:
    a Tuple with the first entry being the guild name, and the second being a key
  """
  return (ctx.channel.guild.name, f"{ctx.author.id}:{ctx.channel.guild.id}")

class StatsManager(CustomCog):
  """
  Cog for allowing users to consent (or revoke), delete, and see emoji usages
  """
  def __init__(self, bot: Bot):
    self.bot = bot

  def get_guild_key(self, idOrName: Union[int, str], ctx: Context) -> Optional[GuildAndKey]:
    """
    Function for extracting the guild name and key from user-provided id/name

    Args:
      idOrName: either a server name or id
      ctx: the context of the message that was sent

    Returns:
      a Tuple repesenting the guild name and key, if such a guild (name or id) exists
    """
    user_guild: Optional[Guild] = None

    if isinstance(idOrName, int):
      user_guild = self.bot.get_guild(idOrName)
    else:
      for guild in self.bot.guilds:
        if guild.name == idOrName:
          user_guild = guild
          break

    if user_guild:
      key = f"{ctx.author.id}:{user_guild.id}"
      return [user_guild.name, key]
    else:
      return None

  async def handle_message(self, ctx: Context, idOrName: GuildIdOrNumber, 
                          handler: Callable[[str], None]): 
    """
    Generic function for handling messages from a user

    Args: 
      ctx: the context of the message that was sent    
      idOrName: an optional guild id/name (user-provided)
      handler: a function that is called if we can successfully get guild name and key

    Raises:
      ValueError if the guild could not be found. This happens if sent in a DM
      with no guild id/name provided, or if the guild id/name does not exist
    """

    guildName = ""
    message = ""

    if idOrName:
      data = self.get_guild_key(idOrName, ctx)

      if data:
        guildName = data[0]
        message = handler(data[1])
      else:
        raise ValueError(f"Could not find a guild {idOrName}. You must provide a valid guild id/name to consent. Alternatively, you can message in a server channel")      

    else:
      if isinstance(ctx.channel, TextChannel):
        data = get_key_from_context(ctx)

        guildName = data[0]
        message = handler(data[1])
      else:
        raise ValueError("You must provide a guild id/name to consent. Alternatively, you can message in a server channel")

    await ctx.author.send(f"{message} in {guildName}")

  @command()
  async def consent(self, ctx: Context, idOrName: GuildIdOrNumber = None):
    """
    Consent to have this bot record stats of your emoji usage. These start are NOT anonymous

    This can be called in a server to consent to recording stats in that server, 
    or you can provide a server ID/name to consent via a DM with this bot.

    Examples:
    >consent 000000000000000000  (consent using server id)
    >consent "test server"       (consent using server name)
    >consent                     (consent in a server)
    """
    def handler(key: str):
      redis.hset(key, "consent", "1")

      return "You have consented to record stats of your reactions"
      
    await self.handle_message(ctx, idOrName, handler)
  
  @command()
  async def delete(self, ctx: Context, idOrName: GuildIdOrNumber = None):
    """
    Delete all emoji stats associated with a certain server.

    This can be called in a server to deleta all stats in that server, 
    or you can provide a server ID/name to delete all stats via a DM with this bot.

    Examples:
    >delete 000000000000000000  (delete using server id)
    >delete "test server"       (delete using server name)
    >delete                     (delete stats in server channel)
    """
    def handler(key: str):
      redis.delete(key)

      return "You deleted stats about your reactions"
      
    await self.handle_message(ctx, idOrName, handler)

  @command()
  async def revoke(self, ctx: Context, idOrName: GuildIdOrNumber = None):
    """
    Revoke your consent for continued recording of stats. Previous stats will remain

    This can be called in a server to revoke consent for recordint stats in that server, 
    or you can provide a server ID/name via a DM.

    Examples:
    >revoke 000000000000000000  (revoke using server id)
    >revoke "test server"       (revoke using server name)
    >revoke                     (revoke in server text channel)
    """    
    def handler(key: str):
      redis.hset(key, "consent", "0")

      return "You have revoked consent to record stats of your reactions"
      
    await self.handle_message(ctx, idOrName, handler)

  @command()
  async def stats(self, ctx: Context, idOrName: GuildIdOrNumber = None):
    """
    Get stats of your emoji usage in a guild. These stats are DMed

    This can be called in a server to get stats for that server, 
    or you can provide a server ID/name via a DM.

    Examples:
    >stats 000000000000000000  (revoke using server id)
    >stats "test server"       (revoke using server name)
    >stats                     (revoke in server text channel)
    """   
    def handler(key: str):
      react_stats = redis.hgetall(key)
      
      if len(react_stats) > 1:
        message = ">>> "

        for [emoji, count] in react_stats.items():
          if emoji != "consent":
            message += f"{emoji}: {count} time(s)\n"
      else:
        message = "You have used no emojis"

      return message

    await self.handle_message(ctx, idOrName, handler)