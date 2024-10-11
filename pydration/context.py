"""
Dependency Injection Module

This module provides a flexible dependency injection system with support for
different scopes (singleton, prototype, and thread-local) and context management.

Classes:
    Scope: An enumeration of supported dependency scopes.
    DependencyResolutionException: Exception raised for dependency resolution errors.
    CircularDependencyException: Exception raised when circular dependencies are detected.
    DependencyContext: Main class for managing dependencies and their injection.

Usage:
    context = DependencyContext()
    context.register(my_dependency_function, Scope.SINGLETON)
    instance = context.get('my_dependency')
"""

import threading
import logging
from inspect import signature
from inspect import isgeneratorfunction
from typing import Callable
from typing import Dict
from typing import List
from typing import NamedTuple
from typing import Type
from typing import Any
from typing import Optional
from typing import get_type_hints
from typing import get_args
from typing import get_origin
from functools import wraps
from enum import Enum, auto
from collections.abc import Sequence
from collections.abc import Mapping
from collections.abc import Iterator


class Scope(Enum):
    """Enumeration of supported dependency scopes."""

    SINGLETON = auto()
    PROTOTYPE = auto()
    THREAD_LOCAL = auto()


class DependencyResolutionException(Exception):
    """Raised when an error occurs during dependency resolution."""

    def __init__(
        self, dep_name: str, message: str, inner_exception: Optional[Exception] = None
    ):
        super().__init__(f"Error resolving dependency '{dep_name}': {message}")
        self.dep_name = dep_name
        self.inner_exception = inner_exception


class CircularDependencyException(Exception):
    """Raised when a circular dependency is detected."""

    def __init__(self, dependency_chain):
        chain_str = " -> ".join(dependency_chain)
        super().__init__(f"Circular dependency detected: {chain_str}")
        self.dependency_chain = dependency_chain


class DependencySpec(NamedTuple):
    func: Callable
    return_annotation: Type
    scope: Scope
    is_generator_func: bool


class DependencyContext:
    """A class for managing dependencies and their injection.

    This class provides methods for registering, resolving, and injecting
    dependencies with different scopes (singleton, prototype, thread-local).
    It also supports context management for dependencies that require cleanup.
    """

    def __init__(self) -> None:
        """Initialize the DependencyContext."""
        self._dependencies: Dict[str, DependencySpec] = {}
        self._instances: Dict[str, Any] = {}
        self._context_managers: Dict[str, Any] = {}
        self._thread_local = threading.local()
        self._resolving_dependencies = threading.local()

        self._lock = threading.Lock()
        self._logger = logging.getLogger(__name__)
        self._logger.debug("DependencyContext initialized")

    def register(
        self,
        func_or_scope: Callable | Scope | None = None,
        scope: Scope = Scope.SINGLETON,
    ):
        """
        Register a function as a dependency with a specific scope.

        This method can be used as a decorator with or without arguments to register
        dependencies in the DependencyContext. It supports specifying the scope as an
        argument or using the default singleton scope.

        Examples:
            1. Using as a decorator without arguments (default singleton scope):
                >>> @context.register
                ... def singleton_service() -> str:
                ...     return "Singleton Service"

            2. Using as a decorator with scope as a keyword argument:
                >>> @context.register(scope=Scope.PROTOTYPE)
                ... def prototype_service() -> str:
                ...     return "Prototype Service"

            3. Using as a decorator with scope as a positional argument:
                >>> @context.register(Scope.PROTOTYPE)
                ... def another_prototype_service() -> str:
                ...     return "Another Prototype Service"

        Note:
            The registered function must have a return type annotation, or a ValueError
            will be raised during registration.

        Args:
            func_or_scope (Union[Callable, Scope], optional): Either the function to be
                registered (when used as a decorator without arguments) or the scope
                (when used as a decorator with arguments). Defaults to None.
            scope (Scope, optional): The scope of the dependency. This is used when
                the decorator is called with keyword arguments. Defaults to
                Scope.SINGLETON.

        Returns:
            Callable: A decorator function that registers the dependency.

        Raises:
            ValueError: If the dependency function doesn't have a return type annotation


        """

        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            dep_name = func.__name__
            is_generator = True if isgeneratorfunction(func) else False

            dep_type = signature(func).return_annotation
            if dep_type is None:
                raise ValueError(
                    f"Dependency '{dep_name}' must have a return type annotation."
                )

            actual_scope = scope
            if isinstance(func_or_scope, Scope):
                actual_scope = func_or_scope

            if is_generator and actual_scope != Scope.SINGLETON:
                raise ValueError(
                    "ContextManager deps are only supported for SINGLETON scopes"
                )

            with self._lock:
                self._dependencies[dep_name] = DependencySpec(
                    func=wrapper,
                    return_annotation=dep_type,
                    is_generator_func=is_generator,
                    scope=actual_scope,
                )
            self._logger.debug(
                "Registered dependency '%s' with scope %s", dep_name, actual_scope
            )

            return wrapper

        if callable(func_or_scope):
            # No scope specified, use default
            return decorator(func_or_scope)
        else:
            # Scope specified or no arguments
            return decorator

    def get(self, dep_name: str) -> Any:
        """
        Get a dependency by name, resolving it based on its scope.

        Args:
            dep_name (str): The name of the dependency to retrieve.

        Returns:
            Any: The resolved dependency instance.

        Raises:
            CircularDependencyException: If a circular dependency is detected.
            DependencyResolutionException: If an error occurs while retrieving dependencies.
        """
        if dep_name in self._get_resolving_dependencies_stack():
            raise CircularDependencyException(
                self._get_resolving_dependencies_stack() + [dep_name]
            )

        if dep_name not in self._dependencies:
            raise DependencyResolutionException(
                dep_name, f"Dependency '{dep_name}' is not registered."
            )

        scope = self._dependencies[dep_name].scope

        if scope == Scope.SINGLETON:
            return self._get_singleton(dep_name)
        elif scope == Scope.PROTOTYPE:
            return self._resolve(self._dependencies[dep_name].func)
        elif scope == Scope.THREAD_LOCAL:
            return self._get_thread_local(dep_name)
        else:
            raise DependencyResolutionException(
                dep_name, f"Unknown scope for dependency '{dep_name}'"
            )

    def _get_resolving_dependencies_stack(self):
        """Gets the thread local dependencies stack. # Ensure that each thread has its
        own stack for resolving dependencies
        """
        stack = getattr(self._resolving_dependencies, "stack", None)
        if stack is None:
            stack = []
            setattr(self._resolving_dependencies, "stack", stack)
        return stack

    def get_by_type(self, dep_type: Type) -> Dict[str, Any]:
        """Get all dependencies of a specific type.

        Args:
            dep_type (Type): The type of dependencies to retrieve.

        Returns:
            Dict[str, Any]: A dictionary of dependency names and their instances.

        Raises:
            DependencyResolutionException: If an error occurs while retrieving
                dependencies.
            CircularDependencyException: If a circular dependency is detected.

        """
        dependencies = {
            name: self.get(name)
            for name, dep in self._dependencies.items()
            if dep.return_annotation == dep_type
        }
        self._logger.debug(
            "Retrieved %s dependencies of type  '%s'", len(dependencies), dep_type
        )
        return dependencies

    def _get_singleton(self, dep_name: str) -> Any:
        """Get or create a singleton dependency."""
        if dep_name in self._instances:
            self._logger.debug("Retrieved existing singleton instance '%s'", dep_name)
            return self._instances[dep_name]

        dep = self._dependencies[dep_name]

        if dep.is_generator_func:
            instance = self._resolve_context_manager(dep_name, dep.func)
        else:
            instance = self._resolve(dep.func)

        with self._lock:
            self._instances[dep_name] = instance

        self._logger.debug("Created new singleton instance for '%s'", dep_name)
        return instance

    def _get_thread_local(self, dep_name: str) -> Any:
        """Get or create a thread-local dependency."""
        if not hasattr(self._thread_local, dep_name):
            dep_func = self._dependencies[dep_name].func
            instance = self._resolve(dep_func)
            setattr(self._thread_local, dep_name, instance)
            self._logger.debug("Created new thread-local instance for '%s'", dep_name)

        return getattr(self._thread_local, dep_name)

    def _resolve(self, dep_func: Callable) -> Any:
        """Resolve a function by injecting its dependencies."""
        dep_name = dep_func.__name__
        params = signature(dep_func).parameters
        dependencies_stack = self._get_resolving_dependencies_stack()
        dependencies_stack.append(dep_name)

        try:
            resolved_params = {
                param_name: self.get(param_name) for param_name in params
            }

            self._logger.debug("Resolving dependencies for '%s'", dep_name)
            return dep_func(**resolved_params)
        finally:
            dependencies_stack.pop()

    def _resolve_context_manager(
        self, dep_name: str, dep_func: Callable[[], Iterator[Any]]
    ) -> Any:
        """Resolve a context-managed dependency using a generator function with yield"""
        generator = dep_func()
        instance = next(generator)
        with self._lock:
            self._context_managers[dep_name] = generator
        self._logger.debug("Resolved context manager for '%s'", dep_name)
        return instance

    def hydrate(self, cls: Type) -> Any:
        """
        Inject dependencies into a class constructor or via setters.

        Args:
            cls (Type): The class to inject dependencies into.

        Returns:
            Any: An instance of the class with injected dependencies.
        Raises:
            DependencyResolutionException: If unable to resolve the dependency type.
            CircularDependencyException: If a circular dependency is detected.
        """
        init_signature = signature(cls.__init__)
        type_hints = get_type_hints(cls.__init__)

        resolved_params = {}
        for param_name, param in init_signature.parameters.items():
            if param_name == "self":
                continue
            if param_name in self._dependencies:
                resolved_params[param_name] = self.get(param_name)
            elif param_name in type_hints:
                dep_type = type_hints[param_name]
                resolved_params[param_name] = self._resolve_by_type(dep_type)

        instance = cls(**resolved_params)

        for attr_name, attr_type in get_type_hints(cls).items():
            if not hasattr(instance, attr_name):
                setattr(instance, attr_name, self._resolve_by_type(attr_type))

        self._logger.debug("Injected dependencies for class '%s'", cls.__name__)
        return instance

    def _resolve_by_type(self, dep_type: Type) -> Any:
        """Resolve dependencies based on the provided type"""
        origin_type = get_origin(dep_type)
        if origin_type in (list, List, Sequence):
            inner_type = get_args(dep_type)[0]
            return list(self.get_by_type(inner_type).values())

        elif origin_type in (dict, Dict, Mapping):
            key_type, value_type = get_args(dep_type)
            if key_type is str:
                return self.get_by_type(value_type)

        for dep_name, dep_info in self._dependencies.items():
            if dep_info.return_annotation == dep_type:
                return self.get(dep_name)

        raise DependencyResolutionException(
            str(dep_type), f"Unable to resolve dependency of type {dep_type}"
        )

    def merge(self, other_context: "DependencyContext") -> "DependencyContext":
        """
        Merge the current context with another context, second context overrides
        conflicts. Only dependencies, not live objects, are shared.

        Args:
            other_context (DependencyContext): The context to merge with.

        Returns:
            DependencyContext: A new merged context.
        """
        merged_context = DependencyContext()

        with self._lock, other_context._lock:
            merged_context._dependencies = self._dependencies.copy()
            merged_context._dependencies.update(other_context._dependencies)

        self._logger.debug(
            "Merged context with %s dependencies", len(other_context._dependencies)
        )
        return merged_context

    def __or__(self, other: "DependencyContext") -> "DependencyContext":
        """
        Allow the use of the '|' operator to merge contexts.

        Args:
            other (DependencyContext): The context to merge with.

        Returns:
            DependencyContext: A new merged context.
        """
        return self.merge(other)

    def shutdown(self):
        """Shutdown the context, closing all context managers.

        This method will:
            1. Close all context managers
            2. Clear all dependencies, instances, and thread-local data
        """
        with self._lock:
            for dep_name, generator in self._context_managers.items():
                try:
                    next(generator)
                    self._logger.debug("Closed context manager for '%s'", dep_name)
                except StopIteration:
                    pass
                except Exception as e:
                    self._logger.error(
                        f"Error closing context manager for '{dep_name}': {e}"
                    )
            self._context_managers.clear()
            self._dependencies.clear()
            self._instances.clear()

            # Clear thread-local data
            self._thread_local = threading.local()
            self._resolving_dependencies = threading.local()
        self._logger.debug("DependencyContext shut down")
