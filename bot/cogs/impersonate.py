from discord import TextChannel
from discord.ext.commands import Bot, Cog, Context, command, is_owner

__all__ = ["ImpersonateManager"]

def user_present(ctx: Context, channel: TextChannel) -> bool:
  """
  Determines whether the author of a message is a member of a channel, channel
  Used to prevent users from sending messages to channels where they are not members 

  Args:
    ctx (Context): the context of the message
    channel (TextChannel): the target channel

  Returns (bool):
    true if the author is a member of the channel, false otherwise
  """
  for member in channel.members:
    if member.id == ctx.author.id:
      return True

  return False

class ImpersonateManager(Cog):
  def __init__(self, bot: Bot):
    self.bot = bot

  @is_owner()
  @command()
  async def impersonate(self, ctx: Context, channel: TextChannel, msg: str):
    """
    Allows the author (bot owner) to send a message as this bot to a channel
    The author must be a member of the channel

    Args:
      ctx (Context): the context of the message
      channel (TextChannel): the target channel
      msg (str): the message to be sent
    """
    if user_present(ctx, channel): 
      await channel.send(f"```{msg}```")