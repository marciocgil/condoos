"""Object storage interface. S3 in every real environment; in-memory for tests."""

from functools import lru_cache
from typing import Protocol

from app.config import get_settings


class ObjectStorage(Protocol):
    def put(self, key: str, body: bytes, content_type: str) -> None: ...
    def delete(self, key: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def presigned_url(self, key: str) -> str: ...


class S3Storage:
    def put(self, key: str, body: bytes, content_type: str) -> None:
        from app.storage.s3 import put_object

        put_object(key, body, content_type)

    def get(self, key: str) -> bytes:
        from app.storage.s3 import get_object

        return get_object(key)

    def delete(self, key: str) -> None:
        from app.storage.s3 import delete_object

        delete_object(key)

    def presigned_url(self, key: str) -> str:
        from app.storage.s3 import presigned_get_url

        return presigned_get_url(key)


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, body: bytes, content_type: str) -> None:
        self.objects[key] = (body, content_type)

    def get(self, key: str) -> bytes:
        return self.objects[key][0]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def presigned_url(self, key: str) -> str:
        return f"memory://{key}"


_memory = MemoryStorage()


@lru_cache
def _s3() -> S3Storage:
    return S3Storage()


def get_storage() -> ObjectStorage:
    return _memory if get_settings().storage_backend == "memory" else _s3()
