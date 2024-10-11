"""
Pydration: A Python Dependency Injection framework.

Pydration is designed to handle dependency injection for complex Python applications. 
It supports singleton, prototype, and thread-local lifecycles, as well as name- and 
type-based dependency resolution, context management, and automatic injection into classes.
"""

import logging

from .context import DependencyContext
from .context import CircularDependencyException
from .context import DependencyResolutionException
from .context import Scope


logging.getLogger(__name__).addHandler(logging.NullHandler())


__all__ = [
    "DependencyContext",
    "Scope",
    "CircularDependencyException",
    "DependencyResolutionException",
]
