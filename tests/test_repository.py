from dataclasses import dataclass

import pytest

from redis_kit.exceptions import (
    EntityNotFoundError,
    OptimisticLockError,
    RedisKitError,
    RepositoryError,
)
from redis_kit.repository.model import BaseModel


@dataclass
class SampleEntity(BaseModel):
    name: str = ""
    value: str = ""


class TestBaseModel:
    def test_defaults(self):
        e = SampleEntity()
        assert e.id == ""
        assert e.version == 0
        assert e.created_at is None
        assert e.deleted is False

    def test_custom_fields(self):
        e = SampleEntity(name="foo", value="bar")
        assert e.name == "foo"
        assert e.value == "bar"

    def test_inherits_metadata(self):
        e = SampleEntity(id="123", version=3)
        assert e.id == "123"
        assert e.version == 3


class TestRepositoryExceptions:
    def test_hierarchy(self):
        with pytest.raises(RedisKitError):
            raise RepositoryError("fail")
        with pytest.raises(RepositoryError):
            raise EntityNotFoundError("not found")
        with pytest.raises(RepositoryError):
            raise OptimisticLockError("conflict")
