from asyncio import gather, sleep
from datetime import datetime, timedelta
from dateutil.tz import tzlocal
from discord import Message
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context, command
from discord.utils import get
from re import match
from time import time
from typing import List, Tuple

from .base import CustomCog
from ..util import scheduler

import bot

__all__ = ["PollManager"]

emojis_order = [
  "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"
]

def vote_str(count: int) -> str:
  return "vote" if count == 1 else "votes"

pattern = r'(?P<days>\d+d)?(?P<hours>\d+h)?(?P<minutes>\d+m?)?'

def parse_time(time: str) -> int:
  """
  Parses a simple time string in the format (\d+d)?(\d+h)?(\d+m?)?
  Converts the string to a number representing the amount of minutes

  Args:
    time (str): a time string. Examples include: "10d3h2m"

  Return (int):
    A positive integer representing the number of minutes that would pass

  Raises:
    ValueError: if the input does not match the format, or the time is 0
  """
  result = match(pattern, time)

  if result is None:
    raise ValueError(f"{time} is not a valid time string")

  minutes = 0

  if result.group("minutes"):
    minutes = int(result.group("minutes").replace("m", ""))

  if result.group("hours"):
    hours = int(result.group("hours")[:-1])
    minutes += 60 * hours

  if result.group("days"):
    days = int(result.group("days")[:-1])
    minutes += 24 * 60 * days

  if minutes == 0:
    raise ValueError("You must wait at least one minute for a poll")

  return minutes

async def alert_author(author_id: str, topic: str, reason=""):
  """
  DMs a person notifying the failure of delivering poll results.

  Args:
    author_id (str): the user id to DM
    topic (str): the topic of the original poll
    reason (str): additional error messages to pass on
  """
  author = bot.bot.get_user(author_id)
  
  if author:
    await author.send(f"We could not deliver your poll on {topic}{reason}")

async def poll_result(author_id: str, channel_id: int, msg_id: int, topic: str):
  """
  Handles determining the results of a poll in the channel channel_id with id msg_id
  If the challen cannot be found, alerts the author

  Args:
    author_id (str): the id of who made the poll
    channel_id (str): the id of the channel this poll was created
    msg_id (str): the id of the message that started this poll
    topic (str): the topic of this poll
  """
  channel = bot.bot.get_channel(channel_id)

  if channel is None:
    await alert_author(author_id, topic)
    return
    
  msg = await channel.fetch_message(msg_id)
  
  if msg is None:
    await alert_author(author_id, topic, " because the message no longer exists")
    return
    
  lines = msg.content.split("\n")

  # remove the leading numbers (1., 10.)
  options = [
    line[line.index(".") + 2:] for line in lines[2:]
  ]

  results: List[Tuple[int, str]] = []
  others: List[Tuple[int, str]] = []

  for reaction in msg.reactions:
    try:
      index = emojis_order.index(reaction.emoji)

      if index < len(options):
        results.append((reaction.count - 1, options[index]))
      else:
        others.append((reaction.count, str(reaction)))
    except ValueError:
      others.append((reaction.count, str(reaction)))
  
  others.sort(reverse=True)
  results.sort(reverse=True)
  
  wins = [results[0][1]]
  max_count = results[0][0]

  for idx in range(1, len(results)):
    if results[idx][0] == max_count:
      wins.append(results[idx][1])
    else:
      break
  
  wins.sort()

  max_vote_msg = vote_str(max_count)
  result_msg = f"results of {lines[0]}:\n"

  if len(others) > 0 and others[0][0] > results[0][0]:
    result_msg += f"Your options were crap so {others[0][1]} wins with {others[0][0]} votes\n"

  if len(wins) > 1:
    joined_str = ", ".join(wins)
    result_msg += f"**Tie between {joined_str}** ({max_count} {max_vote_msg} each)\n\n>>> "
  else:
    result_msg += f"**{wins[0]}** wins! ({max_count} {max_vote_msg})\n\n>>> "

  for idx in range(len(wins), len(results)):
    vote_msg = vote_str(results[idx][0])
    result_msg += f"**{results[idx][1]}** ({results[idx][0]} {vote_msg})\n"

  await channel.send(result_msg)

class PollManager(CustomCog):
  def __init__(self, bot: Bot):
    self.bot = bot
    self.polls: List[Tuple[int, float, Message]] = []
    
  @commands.command()
  async def poll(self, ctx: Context, topic: str, timing: str, *options):
    """
    Creates an emoji-based poll for a certain topic.
    NOTE: It is important that statements involving multiple words are quoted if you want them to be together.

    Correct poll:
    >poll "What are birds?" 2d3h1m ":jeff:" "We don't know" (two options, ":jeff:" and "We don't know")
    Create a poll for 2 days, 3 hours, and 1 minute from now
    
    Incorrect poll:
    >poll "What are birds?" 2d3h1m ":jeff:" We don't know (four options, ":jeff:", "We", "don't", and "know")
    Create a poll for 2 minutes

    When providing times, here is the general format: XdXhXm. Replace X with a number. Examples:
      1d (1 day)
      1d3h10m (1 day, 3 hours, 10 minutes)
      3h5m (3 hours, 5 minutes)
      5m (5 minutes)
      5 (5 minutes)
      
    Args:
      topic (str): The topic of this poll
      timing (str): How long this poll should last. You can specify in days, hours, and minutes
        in the form XdXhX (must be this order).
      options (Tuple[str]): A list containing all the options. Currently, we handle up to 10.

    Raises:
      ValueError: if the input is malformed (no options, invalid time, > 10 options)
    """
    if len(options) < 1:
      raise ValueError("Please provide at least one option")

    timing = parse_time(timing)

    if len(options)  > len(emojis_order):
      raise ValueError(f"I can only deal with up to {len(emojis_order)} options")

    time_msg = "minutes" if timing > 1 else "minute"

    poll = f"poll by {ctx.message.author.mention} ({timing} {time_msg}): **{topic}**\n\n>>> "

    for idx in range(len(options)):
      poll += f"{idx + 1}. {options[idx]}\n"

    message = await ctx.send(poll)

    for idx in range(len(options)):
      await message.add_reaction(emojis_order[idx])

    now = datetime.now(tzlocal())
    scheduled_time = now + timedelta(minutes=timing, seconds=2)
    
    scheduler.add_job(poll_result, 'date', run_date=scheduled_time, args=[
      ctx.message.author.id, ctx.channel.id, message.id, topic
    ])
