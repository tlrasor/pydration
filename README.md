# Pydration

Pydration is a Python dependency injection (DI) framework that simplifies handling simple inversion-of-control (IoC) use cases.

## Table of Contents

- [Pydration](#pydration)
- [Features](#features)
- [Installation](#installation)
- [Basic Usage](#basic-usage)
  - [Registering Dependencies](#registering-dependencies)
  - [Resolving Dependencies](#resolving-dependencies)
  - [Merging Contexts](#merging-contexts)
- [Dependency Scopes](#dependency-scopes)
  - [Singleton Scope](#singleton-scope)
  - [Prototype Scope](#prototype-scope)
  - [Thread-local Scope](#thread-local-scope)
- [How Dependency Matching Works](#how-dependency-matching-works)
  - [Injection by Name](#injection-by-name)
  - [Injection by Type](#injection-by-type)
  - [Injection of Lists](#injection-of-lists)
  - [Injection of Dictionaries](#injection-of-dictionaries)
- [Context Management](#context-management)
- [Handling Circular Dependencies](#handling-circular-dependencies)
- [Running Tests](#running-tests)
- [Contributing](#contributing)
- [License](#license)

## Features

- Dependency injection by name or type.
- Support for singleton, prototype, and thread-local lifecycles.
- Circular dependency detection.
- Type and name-based resolution.
- Context merging with conflict resolution.
- Dependency injection into classes and functions.
- Context manager support for lifecycle handling.

## Installation

To install the Pydration module using [Poetry](https://python-poetry.org/), follow the steps below:

1. Clone the repository:

   ```bash
   git clone https://github.com/tlrasor/pydration.git
   cd pydration
   ```

2. Install the dependencies using Poetry:

   ```bash
   poetry install
   ```

This will install all the necessary dependencies and set up the virtual environment for the project.

## Basic Usage

### Registering Dependencies

To register a dependency, use the `register` method in the `DependencyContext`. By default, dependencies are registered as singletons, but you can specify other scopes like `prototype` or `thread_local`.

```python
from pydration import DependencyContext, Scope

context = DependencyContext()

@context.register
def service_a() -> str:
    return "Service A"

@context.register(scope=Scope.PROTOTYPE)
def service_b() -> str:
    return "Service B (prototype)"
```

### Resolving Dependencies

You can resolve dependencies by name from the context using the `get` method:

```python
service_a_instance = context.get("service_a")
print(service_a_instance)  # Output: "Service A"
```

You can also resolve by type:

```python
service_a_type = context.get_by_type(str)
print(service_a_type)  # Output: {"service_a": "Service A", "service_b": "Service B (prototype)"}
```

You can inject configured dependencies into class constructors or via setters by using the `hydrate` method. This allows runtime creation of class instances.

```python
class ExampleClass:
    def __init__(self, service_a: str):
        self.service_a = service_a

example_instance = context.hydrate(ExampleClass)
print(example_instance.service_a)  # Output: "Service A"
```

### Merging Contexts

You can merge two contexts using the `merge` method or the `|` operator.

```python
context1 = DependencyContext()
context2 = DependencyContext()

@context1.register
def service_a() -> str:
    return "Service A from Context 1"

@context2.register
def service_b() -> str:
    return "Service B from Context 2"

@context2.register
def service_a() -> str:
    return "Service A from Context 2 (overrides)"

merged_context = context1 | context2
print(merged_context.get("service_a"))  # Output: "Service A from Context 2 (overrides)"
print(merged_context.get("service_b"))  # Output: "Service B from Context 2"
```
This is useful for testing. You can take a configured context and then override certain dependencies with mocks using merge.


## Dependency Scopes

Pydration supports three types of dependency scopes: **Singleton**, **Prototype**, and **Thread-local**. 

### Singleton Scope

Singleton, the default scope, is useful for expensive or heavyweight resources, where multiple instances would be inefficient, or high-level services.

In the **Singleton** scope, a single instance of the dependency is created and shared across the entire application. This instance is created the first time the dependency is requested and the same instance is returned on subsequent requests.

#### Example:

```python
from pydration import DependencyContext, Scope

context = DependencyContext()

@context.register(scope=Scope.SINGLETON)
def db_connection() -> str:
    return "Database Connection"

conn1 = context.get("db_connection")
conn2 = context.get("db_connection")

assert conn1 is conn2  # Same instance is returned
```


### Prototype Scope

Prototype is useful when you need a new instance each time.

In the **Prototype** scope, a new instance of the dependency is created each time it is requested. Unlike the singleton scope, a fresh instance is returned every time and different requests do not share instances.

**Protoype** instances are unable to perform tear down on context shutdown.

#### Example:

```python
@context.register(scope=Scope.PROTOTYPE)
def transient_service() -> str:
    return "New Transient Service"

service1 = context.get("transient_service")
service2 = context.get("transient_service")

assert service1 is not service2  # New instance is returned every time
```

### Thread-local Scope

Thread-local is useful for managing thread-specific resources, such as database sessions.

In the **Thread-local** scope, each thread that requests the dependency gets its own instance. This ensures that different threads do not share instances, while the same thread consistently gets the same instance.

#### Example:

```python
import threading

@context.register(scope=Scope.THREAD_LOCAL)
def thread_service() -> str:
    return f"Service for Thread {threading.get_ident()}"

def thread_function():
    print(context.get("thread_service"))

thread1 = threading.Thread(target=thread_function)
thread2 = threading.Thread(target=thread_function)

thread1.start()
thread2.start()

thread1.join()
thread2.join()
```


## How Dependency Matching Works

When Pydration is injecting dependencies into a class, it follows this process:
1. **Match by Name**: If the parameter name matches a registered dependency, it will inject that dependency.
2. **Match by Type**: If no name matches, it will try to match based on the type annotation.
3. **Handle Collections**: If the parameter is a `List[]` or `Dict[]`, it will inject all registered dependencies of that type in the appropriate collection.

### Injection by Name

When a dependency is registered, it can be injected by matching the registered function name to the requested argument. This is the most explicit form of dependency injection and ensures that a specific dependency is injected.

#### Example:

```python
class MyService:
    def __init__(self, db_connection: str):
        self.db_connection = db_connection

context = DependencyContext()

@context.register
def db_connection() -> str: # The name for this dependency is "db_connection"
    return "Database Connection"

service = context.inject(MyService)
print(service.db_connection)  # Output: "Database Connection"
```

In this example, the `db_connection` dependency is injected into the `MyService` constructor by matching the argument name.

### Injection by Type

If a matching name is not found, Pydration will attempt to inject dependencies based on the type annotations of the requested dependency. This is useful when multiple dependencies of the same type are required.

#### Example:

```python
class MyService:
    def __init__(self, connection: str):  # No name match, but the type 'str' will be injected.
        self.connection = connection

context = DependencyContext()

@context.register
def db_connection() -> str:
    return "Database Connection"

service = context.inject(MyService)
print(service.connection)  # Output: "Database Connection"
```

Here, no explicit name matches the argument `connection`, but since the type `str` matches the registered `db_connection` dependency, it is injected based on the type.

### Injection of Lists

When a dependency is declared as a `List[]` or `Sequence[]`, Pydration will automatically inject all the registered dependencies of the specified type. This is useful when you have multiple instances of the same type and want them all to be injected as a collection.

#### Example:

```python
class MyService:
    def __init__(self, services: list[str]):
        self.services = services

context = DependencyContext()

@context.register
def service_a() -> str:
    return "Service A"

@context.register
def service_b() -> str:
    return "Service B"

my_service = context.inject(MyService)
print(my_service.services)  # Output: ['Service A', 'Service B']
```

In this case, `MyService` expects a list of `str`, and Pydration automatically injects both `service_a` and `service_b` since they are both registered as `str`.

### Injection of Dictionaries

When a dependency is declared as a `Dict[str, T]` or `Mapping[str, T]`, Pydration will inject all the registered dependencies of type `T` as a dictionary, using their names as keys. This is helpful when you want to inject a set of named dependencies for dynamic access.

#### Example:

```python
class MyService:
    def __init__(self, services: dict[str, str]):
        self.services = services

context = DependencyContext()

@context.register
def service_a() -> str:
    return "Service A"

@context.register
def service_b() -> str:
    return "Service B"

my_service = context.inject(MyService)
print(my_service.services)  
# Output: {'service_a': 'Service A', 'service_b': 'Service B'}
```

Here, Pydration automatically injects a dictionary of all registered `str` dependencies with their respective names as keys.


## Context Management

Pydration can automatically handle dependency lifecycle using ContextManagers. This is easy to define with Python’s `yield` keyword. This is an easy way to add in tear down or cleanup code. Context Managers will be torn down as a part of the shutdown of the context. Only *Singleton* dependencies are allowed to have lifecycle management.

```python
@context.register
def resource() -> Iterator[str]:
    print("Acquiring resource")
    yield "Resource Acquired"
    print("Releasing resource")

resource_instance = context.get("resource")
print(resource_instance)  # Output: "Resource Acquired"

# Shutdown the context to release resources.
context.shutdown()
```


## Handling Circular Dependencies

If you register two dependencies that depend on each other, Pydration will detect and raise a `CircularDependencyException` to prevent infinite loops.

```python
@context.register
def dep_a(dep_b: str) -> str:
    return f"Dep A with {dep_b}"

@context.register
def dep_b(dep_a: str) -> str:
    return f"Dep B with {dep_a}"

# Raises CircularDependencyException
try:
    context.get("dep_a")
except CircularDependencyException:
    print("Circular dependency detected...")
```


## Running Tests

To run the tests, execute:

```bash
poetry run pytest tests
```

This will execute all the unit tests and display the results.

## Contributing

Contributions are welcome! If you want to contribute:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-xyz`).
3. Make your changes and commit them (`git commit -am 'Add some feature'`).
4. Push to the branch (`git push origin feature-xyz`).
5. Create a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

