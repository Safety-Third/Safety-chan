from datetime import datetime, timedelta
from dateutil.tz import tzlocal
from discord.channel import TextChannel
from discord.ext import commands
from discord.ext.commands import Bot, Context, guild_only
from textwrap import dedent
from typing import List

from .base import CustomCog
from ..util import get_local_date, redlocks, scheduler

import bot

__all__ = ["EventsManager"]

async def register_event(channel_id: int, event: str, time: str, \
                         author_id: str, members: List[str]=[]):
  """
  Notifies all members in the channel "channel_id" that the event "event" is about to happen.
  Also mentions all members who signed up.

  Args:
    channel_id (int): the id of the channel the event was created
    event (str): the name of the event
    time (str): a date string representing when the event should happen
    author_id (str): the id of the creator of this event (if a failure occurs)
    members (List[str]): a list of people who have signed up for this event. The creator is first in the list
  """
  try:
    message = dedent(f"""
    Time for **{event}**!
    {" ".join(members)} 
    """)
    channel = bot.bot.get_channel(channel_id)

    if channel:
      await channel.send(message)
    else:
      author = bot.bot.get_user(author_id)

      if author:
        error_msg = f"Failed to hold event {event}: the channel no longer exists"
        await author.send(error_msg)
  except Exception as e:
    print(e)

class EventsManager(CustomCog):
  def __init__(self, bot: Bot):
    self.bot = bot

  @guild_only()
  @commands.command()
  async def schedule(self, ctx: Context, event: str, time: str):
    """
    Schedule an event. Guild-only.

    >schedule "A test event" "3/27/20 15:39 EDT"
    >schedule "A test event 2" "3/27/20 15:39:00 UCT+4"

    This accepts the following formats:
    - AM/PM, with seconds: mm/dd/yy hh:mm:ss AM/PM tz (1/1/11 1:11:11 AM EDT)
    - AM/PM, no seconds: mm/dd/yy hh:mm AM/PM tz (1/1/11 2:01 pm CST)
    - 24-hour, seconds: mm/dd/yy HH:mm:ss tz (01/1/13 13:13:13 UTC-4)
    - 24-hour, no seconds: mm/dd/yy HH:mm tz (1/01/13 08:27 PST)

    The following time zones have been provided:
    - EDT, EST, CDT, CST, MDT, MST, PDT, PST, AKDT, AKST

    For other time zones, please use UTC offset (e.g. UTC+4 for EDT)
    """
    scheduled_date = get_local_date(time)

    if scheduled_date == None:
      raise ValueError(f"Could not parse {time}")

    now = datetime.now(tzlocal())
    local_time = scheduled_date.strftime("%m/%d/%y %H:%M:%S %p %Z")

    if scheduled_date < now:
      raise ValueError(f"{scheduled_date} ({local_time} is in the past")

    wait = (scheduled_date - now)
    
    job = scheduler.add_job(register_event, 'date', run_date=scheduled_date, args=[
      ctx.channel.id, event, time, ctx.message.author.id, [ctx.message.author.mention]
    ])
    
    msg = dedent(f"""
    **{event}** by {ctx.message.author.mention} for {time} ({local_time}, {wait} from now)
    Sign up with the id **{job.id}**
    """)

    await ctx.send(msg)

  @commands.command()
  async def signup(self, ctx: Context, event_id: str):
    """
    Signup for a scheduled event using an event ID.
    You must be able to see the channel to sign up for the event.
    Signing up for an event will notify other members in the channel

    >signup 00000000000000000000000000000000

    Args:
      event_id (str): the hex id made when creating an event
    """
    added = False
    author = ""
    channel = None
    event = ""
    time = ""

    with redlocks.create_lock(event_id):
      job = scheduler.get_job(event_id)

      if job is None:
        raise ValueError(f"The job {event_id} does not exist")

      channel = self.bot.get_channel(job.args[0])

      if channel is None or not ctx.message.author in channel.members:
        raise ValueError(f"The job {event_id} does not exist")

      new_member = ctx.message.author.mention
      author = job.args[3][0]
      event = job.args[1]
      time = job.args[2]

      if new_member not in job.args[3]:
        members = job.args[3] + [new_member]
        new_args = job.args[0:3] + (members,)
        job.modify(args=new_args)
        added = True
    
    if added:
      await channel.send(f"{ctx.message.author.mention} has signed up for {event} at {time} by {author}")
    else:
      await ctx.message.author.send(f"You have already signed up for {event} at {time} by {author}")

  @commands.command()
  async def cancel(self, ctx: Context, event_id: str):
    """
    Cancels an event that you have scheduled.
    You must be the creator of an event to cancel it.
    This will notify members in the channel that you have cancelled the event.

    >cancel 00000000000000000000000000000000

    Args:
      event_id (str): the id of the job you would like to cancel
    """
    args      = []
    author    = ctx.message.author.mention
    error_msg = ""

    with redlocks.create_lock(event_id):
      job = scheduler.get_job(event_id)

      if job:
        args = job.args

        if args[3][0] == author:
          try:
            scheduler.remove_job(event_id)
          except:
            error_msg = "An error occurred when trying to cancel your job"
        else:
          error_msg = f"Could not find a job {event_id}. Make sure you provided the correct id and are the creator of this job"
      else:
        error_msg = f"Could not find a job {event_id}. Make sure you provided the correct id and are the creator of this job"

    if error_msg:
      await ctx.send(error_msg)
    else:
      channel = self.bot.get_channel(args[0])

      if channel is None:
        await ctx.send(f"The channel {args[0]} no longer exists")
      else:
        msg = dedent(f"""
        {author} cancelled "**{args[1]}**" for {args[2]}
        {" ".join(args[3])}
        """)

        await channel.send(msg)