from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from dateutil.tz import tzlocal
from discord.channel import TextChannel
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context, CommandInvokeError
from redlock import RedLockFactory
from textwrap import dedent
from typing import List

import bot
from .util import get_local_date

async def register_event(channel_id: int, event: str, time: str, members: List[str]=[]):
  """
  Notifies all members in the channel "channel_id" that the event "event" is about to happen.
  Also mentions all members who signed up.

  Args:
    channel_id (int): the id of the channel the event was created
    event (str): the name of the event
    time (str): a date string representing when the event should happen
    members (List[str]): a list of people who have signed up for this event. The creator is first in the list
  """
  message = dedent(f"""
  Time for "**{event}**"!
  {" ".join(members)} 
  """)
  channel = bot.bot.get_channel(channel_id)
  await channel.send(message)

factory = RedLockFactory([{
  "host": "127.0.0.1"
}])

class EventsManager(Cog):
  def __init__(self, bot: Bot):
    self.bot = bot
    self.scheduler = AsyncIOScheduler()
    self.scheduler.add_jobstore("redis")
    self.scheduler.start()

  async def cog_command_error(self, ctx: Context, error: CommandInvokeError):
    """
    Handles errors for events commands
    """
    await ctx.send(error.original)

  @commands.guild_only()
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
    
    job = self.scheduler.add_job(register_event, 'date', run_date=scheduled_date, args=[
      ctx.channel.id, event, time, [ctx.message.author.mention]
    ])
    
    msg = dedent(f"""
    "**{event}**" by {ctx.message.author.mention} for {time} ({local_time}, {wait} from now)
    Sign up with the id **{job.id}**
    """)

    await ctx.send(msg)

  @commands.command()
  async def signup(self, ctx: Context, jobid: str):
    """
    Signup for a scheduled event using an event ID.
    You must be able to see the channel to sign up for the event.
    Signing up for an event will notify other members in the channel

    >signup 00000000000000000000000000000000

    Args:
      jobid (str): the hex id made when creating an event
    """
    added = False
    author = ""
    channel = None
    event = ""
    time = ""

    with factory.create_lock(jobid):
      job = self.scheduler.get_job(jobid)

      if job is None:
        raise ValueError(f"The job {jobid} does not exist")

      channel = self.bot.get_channel(job.args[0])

      if channel is None or not ctx.message.author in channel.members:
        raise ValueError(f"The job {jobid} does not exist")

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
  async def cancel(self, ctx: Context, jobid: str):
    """
    Cancels an event that you have scheduled.
    You must be the creator of an event to cancel it.
    This will notify members in the channel that you have cancelled the event.

    >cancel 00000000000000000000000000000000

    Args:
      jobid (str): the id of the job you would like to cancel
    """
    args      = []
    author    = ctx.message.author.mention
    error_msg = ""

    with factory.create_lock(jobid):
      job = self.scheduler.get_job(jobid)

      if job:
        args = job.args

        if args[3][0] == author:
          try:
            self.scheduler.remove_job(jobid)
          except:
            error_msg = "An error occurred when trying to cancel your job"
        else:
          error_msg = f"Could not find a job {jobid}. Make sure you provided the correct id and are the creator of this job"
      else:
        error_msg = f"Could not find a job {jobid}. Make sure you provided the correct id and are the creator of this job"

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