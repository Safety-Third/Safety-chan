from discord.ext.commands import BadArgument, Bot, Cog, Context, CommandError, CommandInvokeError
from textwrap import dedent

__all__ = ["CustomCog"]

class CustomCog(Cog):
  async def cog_command_error(self, ctx: Context, error: CommandError):
    """
    Handles errors for custom cogs
    """
    if isinstance(error, CommandInvokeError):
      await ctx.send(error.original)
    elif isinstance(error, BadArgument):
      message = dedent(f"""
      >>> You provided wrong arguments. It should be:
      `>{ctx.command.name} {ctx.command.signature}`
      Arguments in `<>` are mandatory, arguments in `[]` are optional.

      Original error: `{error}`
      """)
      await ctx.send(message)
    else:
      await ctx.send(error)