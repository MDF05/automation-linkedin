"""
ORM models package — exports all models and the shared Base.

Usage:
    from app.models import Base, Post, BotLog, Interaction, JobApplication
    from app.models import Schedule, AiUsage, Settings, SystemConfig
"""

from .base import Base
from .post import Post
from .bot_log import BotLog
from .interaction import Interaction
from .job_application import JobApplication
from .schedule import Schedule
from .ai_usage import AiUsage
from .settings import Settings

# SystemConfig is an alias for Settings (same table: key-value store for
# system configuration). Exposed under both names for convenience.
SystemConfig = Settings

__all__ = [
    "Base",
    "Post",
    "BotLog",
    "Interaction",
    "JobApplication",
    "Schedule",
    "AiUsage",
    "Settings",
    "SystemConfig",
]
