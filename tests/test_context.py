from collections.abc import Iterator
import threading

import pytest

from pydration import DependencyContext
from pydration import Scope
from pydration import DependencyResolutionException
from pydration import CircularDependencyException


@pytest.fixture
def context():
    return DependencyContext()


def test_register_and_get_singleton(context):
    @context.register
    def singleton_service() -> str:
        return "Singleton Service"

    assert context.get("singleton_service") == "Singleton Service"
    assert context.get("singleton_service") is context.get("singleton_service")


def test_register_and_get_prototype(context):
    @context.register(scope=Scope.PROTOTYPE)
    def prototype_service() -> object:
        return object()

    assert context.get("prototype_service") is not context.get("prototype_service")


def test_register_and_get_thread_local(context):
    @context.register(scope=Scope.THREAD_LOCAL)
    def thread_local_service() -> str:
        return f"Thread Local Service: {threading.get_ident()}"

    def thread_func():
        assert "Thread Local Service:" in context.get("thread_local_service")

    threads = [threading.Thread(target=thread_func) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_circular_dependency_detection(context):
    @context.register
    def service_a() -> str:
        return context.get("service_b")

    @context.register
    def service_b() -> str:
        return context.get("service_a")

    with pytest.raises(CircularDependencyException):
        context.get("service_a")


def test_dependency_resolution_error(context):
    with pytest.raises(DependencyResolutionException):
        context.get("non_existent_service")


def test_get_by_type(context):
    @context.register
    def string_service1() -> str:
        return "String Service 1"

    @context.register
    def string_service2() -> str:
        return "String Service 2"

    @context.register
    def int_service() -> int:
        return 42

    string_services = context.get_by_type(str)
    assert len(string_services) == 2
    assert "String Service 1" in string_services.values()
    assert "String Service 2" in string_services.values()

    int_services = context.get_by_type(int)
    assert len(int_services) == 1
    assert 42 in int_services.values()


def test_inject_class(context):
    @context.register
    def dependency_a() -> str:
        return "Dependency A"

    @context.register
    def dependency_b() -> int:
        return 42

    class TestClass:
        def __init__(self, dependency_a: str, dependency_b: int):
            self.dep_a = dependency_a
            self.dep_b = dependency_b

    instance = context.hydrate(TestClass)
    assert instance.dep_a == "Dependency A"
    assert instance.dep_b == 42


def test_context_manager_dependency(context):
    @context.register
    def context_managed_service() -> Iterator[str]:
        resource = "Resource acquired"
        yield resource
        print("Resource released")  # This will be called during shutdown

    assert context.get("context_managed_service") == "Resource acquired"
    context.shutdown()
    # You might want to capture stdout to verify "Resource released" is printed


def test_merge_contexts():
    context1 = DependencyContext()
    context2 = DependencyContext()

    @context1.register
    def service_a() -> str:
        return "Service A from Context 1"

    @context2.register
    def service_b() -> str:
        return "Service B from Context 2"

    @context2.register
    def service_a() -> str:  # noqa: F811
        return "Service A from Context 2 (overrides)"

    merged_context = context1 | context2

    assert merged_context.get("service_a") == "Service A from Context 2 (overrides)"
    assert merged_context.get("service_b") == "Service B from Context 2"


def test_resolve_list_dependencies(context):
    @context.register
    def service_a() -> str:
        return "Service A"

    @context.register
    def service_b() -> str:
        return "Service B"

    class TestClass:
        def __init__(self, services: list[str]):
            self.services = services

    instance = context.hydrate(TestClass)
    assert set(instance.services) == {"Service A", "Service B"}


def test_resolve_dict_dependencies(context):
    @context.register
    def service_a() -> str:
        return "Service A"

    @context.register
    def service_b() -> str:
        return "Service B"

    class TestClass:
        def __init__(self, services: dict[str, str]):
            self.services = services

    instance = context.hydrate(TestClass)
    assert instance.services == {"service_a": "Service A", "service_b": "Service B"}


def test_singleton_thread_safety(context):
    counter = 0

    @context.register
    def singleton_service() -> int:
        nonlocal counter
        counter += 1
        return counter

    def thread_func():
        context.get("singleton_service")

    threads = [threading.Thread(target=thread_func) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert context.get("singleton_service") == 1


def test_prototype_thread_safety(context):
    counter = 0

    @context.register(scope=Scope.PROTOTYPE)
    def prototype_service() -> int:
        nonlocal counter
        counter += 1
        return counter

    def thread_func():
        context.get("prototype_service")

    threads = [threading.Thread(target=thread_func) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert counter == 10
