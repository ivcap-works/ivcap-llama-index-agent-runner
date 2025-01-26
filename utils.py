from enum import Enum
from pydantic import BaseModel, Field, TypeAdapter, model_validator


class StrEnum(str, Enum):
    def __repr__(self) -> str:
        return str.__repr__(self.value)

class SchemaModel(BaseModel):
    aspect_schema: str = Field(None, alias="$schema")

    @classmethod
    def json_schema(cls, *, json_schema="https://json-schema.org/draft/2020-12/schema"):
        if not hasattr(cls, 'SCHEMA'):
            raise Exception("Missing 'SCHEMA' declaration")
        s = {
            "$schema": json_schema,
            "$id": cls.SCHEMA,
        }
        if hasattr(cls, 'DESCRIPTION'):
            s["description"] = cls.DESCRIPTION
        t = TypeAdapter(cls)
        s.update(t.json_schema())
        s["properties"].pop("$schema")
        return s

    @model_validator(mode='after')
    def set_aspect_schema(self) -> "SchemaModel":
        if not hasattr(self.__class__, 'SCHEMA'):
            raise Exception("Missing 'SCHEMA' declaration")
        self.aspect_schema = self.__class__.SCHEMA
        return self