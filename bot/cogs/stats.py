from discord import Guild, Member, TextChannel, User
from discord.ext.commands import Bot, Context, check_any, command, \
CommandInvokeError, guild_only, has_permissions, is_owner
from typing import Callable, Dict, List, Optional, Tuple, Union

from .base import CustomCog
from ..util import redis, redlocks

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

  def get_guild(self, idOrName: Union[int, str]) -> Optional[Guild]:
    """
    Function for finding a guild using its id or name
    
    Args:
      idOrName: a possible server name or id

    Returns:
      a guild whose name matches the name or whose id matches the id if exists, or None
    """
    if isinstance(idOrName, int):
      return self.bot.get_guild(idOrName)
    else:
      for guild in self.bot.guilds:
        if guild.name == idOrName:
          return guild

    return None

  def get_guild_key(self, idOrName: Union[int, str], ctx: Context) -> Optional[GuildAndKey]:
    """
    Function for extracting the guild name and key from user-provided id/name

    Args:
      idOrName: either a server name or id
      ctx: the context of the message that was sent

    Returns:
      a Tuple repesenting the guild name and key, if such a guild (name or id) exists
    """
    user_guild = self.get_guild(idOrName)

    if user_guild:
      key = f"{ctx.author.id}:{user_guild.id}"
      return [user_guild.name, key]
    else:
      return None

  async def handle_message(self, ctx: Context, idOrName: GuildIdOrNumber, 
                          handler: Callable[[str], str]): 
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
  async def categories(self, ctx: Context, max_per_category = 5, idOrName: GuildIdOrNumber = None):
    """
    Get stats of your emoji usage in a guild, by category. These stats are DMed.

    By default, will send you the top 5 emojis per section (up to 2x max_per_category, if tied).
    You can change the number of emojis by providing a number as your first argument.
    Regardless, you will get a total count of the emojis per section.

    This can be called in a server to get stats for that server, 
    or you can provide a server ID/name via a DM. 
    You have to provide an emoji count in this case.

    Examples:
    >categories                        (stats in server text channel)
    >categories 20                     (show the top 20 emojis per category)
    >categories 5 000000000000000000   (show top 5 emojis by category using server id)
    >categories 10 "test server"       (show top 10 emojis by category using server name)
    """
    def handler(key: str):
      react_stats = redis.hgetall(key)

      guild_id = key[key.index(":") + 1:]
      categories = redis.hgetall(f"{guild_id}:categories")
      
      if len(react_stats) > 1 and categories:
        message = ">>> "

        score_mapping_by_category: Dict[Optional[str], Dict[int, List[str]]] = {}

        for [emoji, count] in react_stats.items():
          if emoji != "consent":
            category = None

            for [key, emojilist] in categories.items():
              if emoji in emojilist:
                category = key
                break

            category_map = score_mapping_by_category.get(category, {})

            int_score = int(count)

            if int_score in category_map:
              category_map[int_score].append(emoji)
            else:
              category_map[int_score] = [emoji]

            score_mapping_by_category[category] = category_map

        section_and_top_emojis: List[Tuple[int, List[str], Optional[str]]] = []

        for [category, mapping] in score_mapping_by_category.items():
          emoji_count = 0
          top_emojis: List[str] = []
          total_count = 0

          for count in sorted(mapping, reverse=True):
            emojis = mapping[count]

            if emoji_count < max_per_category and emoji_count + len(emojis) < max_per_category * 2:
              top_emojis.append("  ".join(emojis) + f" ({count})")
            
            emoji_count += len(emojis)
            total_count += count * len(emojis)

          section_and_top_emojis.append([total_count, top_emojis, category])

        for [total_count, emojis, category] in sorted(section_and_top_emojis, reverse=True):
          emojis_joined = "  ".join(emojis)

          if category is None:
            message += "**No category**"
          else:
            message += category

          message += f" ({total_count} uses): {emojis_joined}\n"

        return message
      else:
        message = "You have used no emojis"

      return message

    await self.handle_message(ctx, idOrName, handler)

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
  async def stats(self, ctx: Context, maxEmojis = 10, idOrName: GuildIdOrNumber = None):
    """
    Get stats of your emoji usage in a guild. These stats are DMed

    By default, will send you the top 10 emojis (potentially more if many are tied).
    You can change the number of emojis by providing a number as your first argument

    This can be called in a server to get stats for that server, 
    or you can provide a server ID/name via a DM. 
    You have to provide an emoji count in this case.

    Examples:
    >stats                        (stats in server text channel)
    >stats 1000                   (show the top 1000 emojis)
    >stats 10 000000000000000000  (show top 10 emojis using server id)
    >stats 10 "test server"       (show top 10 emojis using server name)
    """   
    def handler(key: str):
      react_stats = redis.hgetall(key)
      
      if len(react_stats) > 1:
        message = ">>> "

        score_mappings: Dict[int, List[str]] = {}

        for [emoji, count] in react_stats.items():
          if emoji != "consent":
            int_score = int(count)

            if int_score in score_mappings:
              score_mappings[int_score].append(emoji)
            else:
              score_mappings[int_score] = [emoji]

        emoji_count = 0

        for count in sorted(score_mappings, reverse=True):
          emojis = score_mappings[count]

          if len(emojis) + emoji_count >= maxEmojis * 2:
            break

          if count == 1:
            message += "1 use: "
          else:
            message += f"{count} uses: "

          message += " ".join(emojis) + "\n"

          emoji_count += len(emojis)

          if emoji_count >= maxEmojis:
            break

        return message
      else:
        message = "You have used no emojis"

      return message

    await self.handle_message(ctx, idOrName, handler)
  
  @check_any(has_permissions(manage_emojis=True), is_owner())
  @command()
  async def setCategory(self, ctx: Context, category: str, *emojis):
    """
    Sets a list of emojis to a specific category.
    This category will be used to determine which "categories" are most used by a specific person.
    An emoji can only belong to a single category.

    If you want to specify which server to use, provide the server id or name
    as the last argument.

    Examples:
    >setCategory joy :three:                      (sets the category 'joy' to be [3])
    >setCategory joy :three: :four: :five:        (sets the category 'joy' to be [3, 4, 5])
    >setCategory joy :three: :four: "test server" (sets the category 'joy' in "test server" to [3])
    >setCategory joy :three: 000000000000000000   (sets the category 'joy' in server with id
                                                  000000000000000000  to [3])
    """
    if len(emojis) == 0:
      raise ValueError("You must provide at least one emoji")

    guildId = ""

    guild = self.get_guild(emojis[-1])

    if guild is None:
      if isinstance(ctx.channel, TextChannel):
        guildId = ctx.channel.guild.id
      else:
        raise ValueError(f"Could not find a server {emojis[-1]}. If you are DM-ing, make sure to provide the server name/id as the last argument")
    else:
      guildId = guild.id
      emojis = emojis[:-1]
        
    key = f"{guildId}:categories"

    with redlocks.create_lock(f"{key}:lock"):
      existing_categories = redis.hgetall(key)

      for [existing_category, emojilist] in existing_categories.items():
        if existing_category == category:
          continue

        for emoji in emojis:
          if emoji in emojilist:
            raise ValueError(f"Emoji {emoji} is already used in category {existing_category}")

      redis.hmset(key, { category: " ".join(emojis)})

    await ctx.send(f"{ctx.author.mention} set category {category} to {' '.join(emojis)}")

  @command()
  async def uses(self, ctx: Context, *emojis):
    """
    Get stats of your specific emojis in a guild.

    You can provide a list of emojis you want to see.
    If you want to specify which server to use, provide the server id or name
    as the last argument.

    Examples:
    >uses :three:                       (number of uses of three)
    >uses :three: :four: :five:         (number of uses of three, four, and five)
    >uses :three: :four: "test server"  (number of uses of three and four in "test server")
    >uses :three: 000000000000000000    (number of uses of three in server with id of all zeroes)
    """   
    if len(emojis) == 0:
      raise ValueError("You must provide at least one emoji")

    idOrName: Optional[GuildIdOrNumber] = None

    if self.get_guild_key(emojis[-1], ctx):
      idOrName = emojis[-1]
      emojis = emojis[:-1]

    def handler(key: str):
      react_stats = redis.hgetall(key)
      
      if len(react_stats) > 1:
        message = ">>> "

        for emoji in emojis:
          count = react_stats.get(emoji, 0)
          message += f"{emoji}: {count} use"

          if count != 1:
            message += "s"
          message += "\n"

        return message
      else:
        message = "You have used no emojis"

      return message

    await self.handle_message(ctx, idOrName, handler)

  @command()
  async def viewCategories(self, ctx: Context, idOrName: GuildIdOrNumber = None):
    """
    View the emoji categories in a specific server.

    You can provide a server id or name to specify a certain server to use, or
    send the message in a server (no arguments) to get the categories for that server.

    Examples:
    >viewCategories                     (view emoji categories in current server)
    >viewCategories "test server"       (view emoji categories in server "test server")
    >viewCategories 000000000000000000  (view emoji categories in server with id 000000000000000000)
    """
    guild: Optional[Guild] = None    

    if idOrName:
      guild = self.get_guild(idOrName)
    else:
      if isinstance(ctx.channel, TextChannel):
        guild = ctx.channel.guild

    if guild is None:
      raise ValueError(f"Could not find a server {idOrName}. If you are DM-ing, make sure to provide the server name/id as the last argument")
      
    categories = redis.hgetall(f"{guild.id}:categories")

    if categories:
      message = f">>> Emoji categories in {guild.name}:"

      for [category, emojilist] in categories.items():
        message += f"\n{category}: {emojilist}"

      await ctx.send(message)
    else:
      await ctx.send(f"No categories for server {guild.name}")
