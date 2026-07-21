"""CometAPI's OpenAI-compatible Python clients."""

from importlib.metadata import version

from .client import AsyncCometAPI, CometAPI

__version__ = version("cometapi")

__all__ = ["AsyncCometAPI", "CometAPI", "__version__"]
