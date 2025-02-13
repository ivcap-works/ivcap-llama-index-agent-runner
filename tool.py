from datetime import datetime
import json
from typing import Awaitable, Callable, Optional, List, Any
from uuid import uuid4
import aiohttp
from fastapi import HTTPException, status
from llama_index.core.bridge.pydantic import BaseModel, create_model, Field
from llama_index.core.tools.types import ToolMetadata
from llama_index.core.tools import BaseTool, FunctionTool

import os
import logging
import requests

from events import ToolEvent

TOOL_SCHEMA = "urn:sd-core:schema:ai-tool.1"

logger = logging.getLogger("ivcap-tool")

class ToolDefinition(BaseModel):
    jschema: str = Field(default=TOOL_SCHEMA, alias="$schema")
    name: str
    description: str
    type: str
    fn_schema: dict

override_fns: dict[str, Callable[..., Any]] = {}
tools: dict[str, BaseTool] = {}

def resolve_tool(urn: str) -> BaseTool:
    if urn in tools:
        return tools[urn]

    if urn.startswith("http://localhost"):
        # for debugging we support loading metadata from local tools
        r = requests.get(urn)
        j = r.json()
        return register_url_tool(urn, j)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Tool '{urn}' not found\n")

def load_tool_from_json_file(file_path: str) -> FunctionTool:
    with open(file_path, 'r') as file:
        j = json.load(file)
        tool = _load_tool_from_json(j)
        return tool


def load_local_url_tool(url: str, file_path: str) -> FunctionTool:
   with open(file_path, 'r') as file:
        j = json.load(file)
        return register_url_tool(url, j)

def register_url_tool(url: str, description: dict) -> FunctionTool:
    md = _load_meta_from_json(description)

    async def afn(**kwargs):
        span_id = ToolEvent.dispatch_tool_start(md.name, **kwargs)
        if kwargs.get("properties") and kwargs.get("type") == "object":
            err = TypeError("arguments are of wrong type and format")
            ToolEvent.dispatch_tool_error(span_id, err, md.name, **kwargs)
            raise err
        p = md.fn_schema(**kwargs)
        j = p.model_dump()

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=j) as response:
                    if response.status == 200:
                        data = await response.json()
                        ToolEvent.dispatch_tool_end(span_id, data, md.name, **kwargs)
                        return data
                    else:
                        err = HTTPException(status_code=response.status, detail="tool reply")
                        ToolEvent.dispatch_tool_error(span_id, err, md.name, **kwargs)
                        raise err
            except Exception as e: # Catch any other error
                ToolEvent.dispatch_tool_error(span_id, err, md.name, **kwargs)
                raise e

    tool = FunctionTool(metadata=md, async_fn=afn)
    return _register_function_tool(tool)

def register_function_as_tool(fn: Callable[..., Any]) -> FunctionTool:
    tool = FunctionTool.from_defaults(fn=fn)
    tool._fn = _wrap(tool.metadata.name, fn)
    return _register_function_tool(tool)

### INTERNAL

def _register_function_tool(tool: FunctionTool) -> FunctionTool:
    name = tool.metadata.name
    tools[name] = tool
    if not name.startswith("urn:ivcap:service:ai-tool."):
        tools["urn:ivcap:service:ai-tool." + name] = tool
    return tool

def _wrap(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    def w(**kwargs):
        try:
            span_id = ToolEvent.dispatch_tool_start(name, **kwargs)
            data = fn(**kwargs)
            ToolEvent.dispatch_tool_end(span_id, data, name, **kwargs)
            return data
        except Exception as e: # Catch any other error
            ToolEvent.dispatch_tool_error(span_id, e, name, **kwargs)
            raise e
    return w

def _load_tool_from_json(d: dict) -> FunctionTool:
    md = _load_meta_from_json(d)

    def tool_proxy(**kwargs):
        md.fn_schema(**kwargs) # verify what's being passed in
        if md.name in override_fns:
            return override_fns[md.name](**kwargs)

        raise NotImplementedError(f"Function '{md.name}' not implemented")

    tool = FunctionTool(tool_proxy, md)
    return _register_function_tool(tool)

def _load_meta_from_json(d: dict) -> ToolMetadata:
    td = ToolDefinition(**d)
    if td.jschema != TOOL_SCHEMA:
        raise ValueError(f"Invalid schema: expected \'{TOOL_SCHEMA}\' but got \'{td.jschema}\'")
    fn_schema = _create_pydantic_model_from_schema(td.fn_schema, td.name)

    md = ToolMetadata(
        name=td.name,
        description=f"{td.type}\n{td.description}",
        fn_schema=fn_schema,
    )
    return md


def _create_pydantic_model_from_schema(schema: dict, model_name: str) -> Any:
    """Creates a Pydantic model from a JSON schema definition."""
    fields = {}
    for field_name, field_schema in schema.get("properties", {}).items():
        field_type = field_schema.get("type")
        required = field_name in schema.get("required", [])

        # Handle different JSON schema types and map them to Python types
        if field_type == "string":
            python_type = str
        elif field_type == "integer":
            python_type = int
        elif field_type == "number":
            python_type = float
        elif field_type == "boolean":
            python_type = bool
        elif field_type == "array":
            items_type = field_schema.get("items", {}).get("type")
            if items_type == "string":
                python_type = List[str]
            elif items_type == "integer":
                python_type = List[int]
            elif items_type == "number":
                python_type = List[float]
            elif items_type == "boolean":
                python_type = List[bool]
            elif "properties" in field_schema.get("items", {}): #nested object
                nested_model_name = model_name + "_" + field_name.capitalize()
                nested_model = _create_pydantic_model_from_schema(field_schema["items"], nested_model_name)
                python_type = List[nested_model]
            else:
                python_type = List[Any]  # Default to List[Any] if item type is not specified
        elif field_type == "object":
            nested_model_name = model_name + "_" + field_name.capitalize()
            python_type = _create_pydantic_model_from_schema(field_schema, nested_model_name)

        else:
            python_type = Any  # Default to Any if type is unknown

        # Handle optional fields
        if not required:
            python_type = Optional[python_type]

        #Create Field with extra information
        field_kwargs = {}
        if "description" in field_schema:
            field_kwargs["description"] = field_schema["description"]
        if "minimum" in field_schema:
            field_kwargs["ge"] = field_schema["minimum"]
        if "maximum" in field_schema:
            field_kwargs["le"] = field_schema["maximum"]
        if "pattern" in field_schema:
            field_kwargs["regex"] = field_schema["pattern"]

        fields[field_name] = (python_type, Field(**field_kwargs) if field_kwargs else None)

    return create_model(model_name, **fields)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    def load_example_tool(file_path: str, fn: Callable[..., Any]) -> FunctionTool:
        with open(file_path, 'r') as file:
            j = json.load(file)
            md = _load_meta_from_json(j)
            tool = FunctionTool(metadata=md, fn=_wrap(md.name, fn))
            return _register_function_tool(tool)

    tool = load_example_tool('examples/multiply-tool.json', lambda a, b: a * b)
    r = tool.call(a=5, b=2)
    logger.info(f"Result: {r}")