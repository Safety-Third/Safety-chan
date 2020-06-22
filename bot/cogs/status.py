from asyncio import sleep
from discord import Game
from discord.ext import tasks, commands
from discord.ext.commands import Bot, Cog, Context
from os import environ
from random import SystemRandom

from ..util import sheets

__all__ = ["StatusManager"]

rand = SystemRandom()

class StatusManager(Cog):
  def __init__(self, bot: Bot):
    self.bot = bot
    self.roles_doc = environ.get("SAFETY_ROLES_GOOGLE_LINK")
    self.change_status.start()

  @tasks.loop(minutes=30)
  async def change_status(self):
    """
    Change the "game" this bot is playing by pulling from a list from google docs
    """
    try:
      games = sheets.spreadsheets() \
        .values() \
        .get(spreadsheetId=self.roles_doc, range="A2:A100") \
        .execute() \
        .get("values", [])

      next_game = rand.choice(games)
      game = Game(name=next_game[0])
      await sleep(10)
      await self.bot.change_presence(activity=game)
    except Exception as e:
      print(e)
