from discord import Member, Role
from discord.ext import commands
from discord.ext.commands import CommandInvokeError, Context, Greedy
from typing import Set

from .base import CustomCog

__all__ = ["RolesManager"]

class NoRolesError(Exception):
  """An exception that is thrown when no valid roles are given"""
  async def handle_error(self, ctx: Context):
    roles = [role.name for role in ctx.guild.roles if role.name != "@everyone"]
    await ctx.send(f"No valid roles provided. Here are some possible roles: {roles}")

def remove_dupe_roles(roles: Greedy[Role]) -> Set[Role]:
  roles = set(roles)

  if len(roles) == 0:
    raise NoRolesError("No roles provded")

  return roles

def pluralize(person: Member, roles: commands.Greedy[Role]) -> str:
  message =  "role" if len(roles) == 1 else "roles"
  roleIds = [role.name for role in roles]

  return f"{message} for {person}: {roleIds}"

class RolesManager(CustomCog):
  """
  Shortcut for managing user roles
  """
  def __init__(self, bot):
    self.bot = bot

  async def cog_command_error(self, ctx: Context, error: CommandInvokeError):
    """
    Handles errors for roles commands
    """
    if isinstance(error.original, NoRolesError):
      await error.original.handle_error(ctx)
    else:
      await super().cog_command_error(ctx, error)

  @commands.has_permissions(administrator=True)
  @commands.command()
  async def addRoles(self, ctx: Context, person: Member, roles: Greedy[Role]):
    """
    Adds one or more roles to a person.

    >addRoles @Safety-chan role1 role2

    Args:
      person (Member): The person who is receiving more roles
      roles (Greedy[Role]) A list of roles to be added

    Raises:
      NoRolesError: if no existing roles are provided
    """
    roles = remove_dupe_roles(roles)

    await person.add_roles(*roles)
    await ctx.send(f"Adding {pluralize(person, roles)}")

  @commands.has_permissions(administrator=True)
  @commands.command()
  async def removeRoles(self, ctx: Context, person: Member, roles: Greedy[Role]):
    """
    Removes one or role roles from a person

    >removeRoles @Safety-chan role1 role2

    Args:
      person (Member): The person who will be losing roles
      roles (Greedy[Role]): A list of roles to be removed

    Raises:
      NoRolesError: if no existing roles are provided
    """
    roles = remove_dupe_roles(roles)

    await person.remove_roles(*roles)
    await ctx.send(f"Removing {pluralize(person, roles)}")

  @commands.has_permissions(administrator=True)
  @commands.command()
  async def setRoles(self, ctx: Context, person: Member, roles: Greedy[Role]):
    """
    Sets the list of roles of one person
   
    >setRoles @Safety-chan role1 role2

    Args:
      person (Member):  The person whose roles are being set
      roles (Greedy[Role]): A list of roles to be set

    Raises:
      NoRolesError: if no existing roles are provided
    """
    roles = remove_dupe_roles(roles)

    await person.edit(roles=roles)
    await ctx.send(f"Setting {pluralize(person, roles)}")