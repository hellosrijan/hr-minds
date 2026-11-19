"""
What a tool is, and the registry of them. Modules register their tools here
(with the @tool decorator); this module never imports them.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.models import Membership
from hr_minds.settings.features import FeatureSlug


@dataclass(frozen=True)
class Tool:
    name: str  # namespaced by module, e.g. "recruitment_create_job_posting"
    description: str  # the model decides when to call the tool from this alone
    args: type[BaseModel]  # validates the model's JSON; also generates the schema it sees
    permission: tuple[FeatureSlug, str]  # (feature, action) the caller must hold
    # Org and user come from the Membership, never from the model's arguments.
    handler: Callable[[AsyncSession, Membership, Any], Awaitable[Any]]
    requires_approval: bool = False


_registry: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    """Add a tool to the registry. Normally called for you by the @tool decorator."""
    # Re-registering the same object is fine; a different tool under a taken name is a bug.
    if _registry.get(tool.name, tool) is not tool:
        raise ValueError(f"tool name already registered: {tool.name}")
    _registry[tool.name] = tool


def tool(
        *,
        name: str, 
        description: str, 
        args: type[BaseModel], 
        permission: tuple[FeatureSlug, str],
        requires_approval: bool = False,
    ):
    """
    Decorator that turns a handler into a registered Tool:

        @tool(name="...", description="...", args=MyArgs, permission=(FeatureSlug.X, "read"))
        async def my_handler(db, membership, args): ...

    Registration happens when the file holding the handler is imported.
    """

    def decorator(handler: Callable[[AsyncSession, Membership, Any], Awaitable[Any]]):
        register(
            Tool(
                name=name, 
                description=description, 
                args=args, 
                permission=permission, 
                handler=handler, 
                requires_approval=requires_approval
            )
        )
        return handler

    return decorator


def get(name: str) -> Tool | None:
    """Find the tool the model asked for, or None if it made the name up."""
    return _registry.get(name)


def available_to(membership: Membership) -> list[Tool]:
    """Only the tools this member may use, so the model is never offered the rest."""
    return [t for t in _registry.values() if membership.can(*t.permission)]


def describe(tool: Tool) -> dict:
    """The tool as the model needs to see it, with no provider-specific wrapping."""
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.args.model_json_schema(),
    }
