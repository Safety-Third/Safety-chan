from discord.ext import commands
from discord.ext.commands import Cog, Context, command, CommandInvokeError
from random import SystemRandom
from re import match
from textwrap import dedent
from typing import List, Tuple

from .base import CustomCog

__all__ = ["RollManager"]

r = SystemRandom()

pattern = r'(?P<count>\d+)d(?P<size>\d+)((?P<addition>[+-]\d+))?(dl(?P<low>\d*))?(dh(?P<high>\d*))?'

class RollManager(CustomCog):
  """
  Shortcut for rolling dice
  """
  def __init__(self, bot):
    self.bot = bot

  def make_roll(self, input: str) -> Tuple[str, List[int], List[int], int]:
    """
    Handles a single role

    Args
      input (str): The roll that is being processed. Rolls should match the pattern regex 'pattern'

    Raises:
      ValueError if the input is malformed
    """
    groups = match(pattern, input)

    if groups == None:
      base = max(abs(hash(input)) % 1000, 1)
      roll = r.randint(1, base)

      raise ValueError(f"Not a valid roll {input}. But here's my best guess for {input} = 1d{base}: **{roll}**")

    count = int(groups.group("count"))

    if count == 0:
      raise ValueError("I *can* roll zero dice, but am morally obligated not to")

    size = int(groups.group("size"))

    if size == 0:
      raise ValueError("I will not roll a d0")

    addition = 0

    if groups.group("addition") != None:
      addition = int(groups.group("addition"))

    low_drop = 0
    high_drop = 0

    if groups.group("low") != None:
      low = groups.group("low")
      low_drop = 1 if low == "" else int(low)

    if groups.group("high") != None:
      high = groups.group("high")
      high_drop = 1 if high == "" else int(high)

    if low_drop + high_drop >= count:
      raise ValueError(f"You want to drop {low_drop + high_drop} dice but are only rolling {size} (must have at least one)")

    rolls = []

    for _ in range(0, count):
      rolls.append(r.randint(1, size))

    message = f"{count}d{size}"

    if addition != 0:
      message += f"+{str(addition)}"

    if low_drop != 0:
      message += f", drop {low_drop} lowest"

      if high_drop != 0:
        message += f" and {high_drop} highest"

    elif high_drop != 0:
      message += f", drop {high_drop} highest"

    rolls.sort()
    return (message, rolls, rolls[low_drop:len(rolls) - high_drop], addition)

  def pretty_array(self, list: List) -> str:
    return ', '.join(str(x) for x in list)

  @commands.command()
  async def roll(self, ctx, *args):
    """
    Rolls one or more dice. Dice rolls should be in this general form:
    
    "int"d"int"
    >roll 1d20 2d4
    >roll 3d125129

    You can also add modifiers to the roll:
    +/-"int" 
    >roll 3d8+5
    >roll 2d6-8

    And you can drop the n highest/lowest rolls:
    dl"int"dh"int" (you can omit "int" to drop 1)
    >roll 8d10dl2: drop 2 lowest
    >roll 8d10dh: drop highest
    >roll 8d10dldh: drop lowest and highest

    Put together, we have:
    "int"d"int"+/-"int"dl"int"dh"int" 
    >roll 10d20+2dl2dh2: 10 d 20s, +2, drop 2 lowest and highest

    NOTE: you should follow this order exactly

    Args:
      args (Tuple[str]]): a list of strings
    """
    message = ""

    total_sum = 0

    for entry in args:
      [roll, display_result, actual_result, addition] = self.make_roll(entry)

      result_sum = sum(actual_result) + addition

      if len(display_result) != len(actual_result):
        result_avg = result_sum / len(actual_result)

        removed_elements = sorted(set(display_result) - set(actual_result))

        message += dedent(f"""
        {roll}: **{result_sum}**
        {self.pretty_array(actual_result)} ({result_avg} avg) + {addition}
        {self.pretty_array(removed_elements)} (dropped)
        """)
      else:
        if len(display_result) > 1:
          average = result_sum / len(actual_result)

          message += dedent(f"""
          {roll}: **{result_sum}**
          {self.pretty_array(display_result)} ({average} avg) + {addition}
          """)
        else:
          message += f"\n{roll}: **{result_sum}**\n"

      total_sum += result_sum

    mention = ctx.message.author.mention
    total_mesg = f"{mention}, you rolled a total of **{total_sum}**:\n\n>>> {message.lstrip()}"

    await ctx.send(total_mesg)

