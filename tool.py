import json
from typing import Callable, Optional, List, Any
from llama_index.core.bridge.pydantic import BaseModel, create_model, Field
from llama_index.core.tools.types import ToolMetadata
from llama_index.core.tools import BaseTool, FunctionTool
import os
import logging
import requests

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
    raise ValueError(f"Tool '{urn}' not found")

def load_tool_from_json_file(file_path: str) -> FunctionTool:
    with open(file_path, 'r') as file:
        j = json.load(file)
        tool = _load_tool_from_dict(j)
        return tool

def load_example_tool(file_path: str, fn: Callable[..., Any]) -> FunctionTool:
    script_dir = os.path.dirname(__file__)
    json_file_path = os.path.join(script_dir, file_path)
    tool = load_tool_from_json_file(json_file_path)
    override_tool_func(tool.metadata.name, fn)
    return tool

def load_local_url_tool(url: str, file_path: str) -> FunctionTool:
    script_dir = os.path.dirname(__file__)
    json_file_path = os.path.join(script_dir, file_path)
    tool = load_tool_from_json_file(json_file_path)

    def fn(**kwargs):
        p = tool.metadata.fn_schema(**kwargs)
        j = p.model_dump_json()
        h = {"Content-Type": "application/json"}
        resp = requests.post(url, data=j, headers=h)
        if resp.status_code < 300:
            res = resp.json()
            logger.info("tool request succeeded")
            return res
        else:
            msg = resp.text
            logger.info(f"tool request failed - {resp.status_code} - {msg}")
            raise Exception(msg)

    override_tool_func(tool.metadata.name, fn)
    return tool


def register_function_as_tool(fn: Callable[..., Any]) -> FunctionTool:
    tool = FunctionTool.from_defaults(fn=fn)
    return register_function_tool(tool)

def override_tool_func(name: str, fn: Callable[..., Any]):
    override_fns[name] = fn

def register_function_tool(tool: FunctionTool) -> FunctionTool:
    name = tool.metadata.name
    tools[name] = tool
    if not name.startswith("urn:ivcap:service:ai-tool."):
        tools["urn:ivcap:service:ai-tool." + name] = tool
    return tool

### INTERNAL

def _load_tool_from_dict(d: dict) -> FunctionTool:
    td = ToolDefinition(**d)
    if td.jschema != TOOL_SCHEMA:
        raise ValueError(f"Invalid schema: expected \'{TOOL_SCHEMA}\' but got \'{td.jschema}\'")
    fn_schema = _create_pydantic_model_from_schema(td.fn_schema, td.name)

    def tool_proxy(**kwargs):
        fn_schema(**kwargs) # verify what's being passed in
        if td.name in override_fns:
            return override_fns[td.name](**kwargs)

        raise NotImplementedError(f"Function '{td.name}' not implemented")

    md = ToolMetadata(
        name=td.name,
        description=f"{td.type}\n${td.description}",
        fn_schema=fn_schema,
    )
    tool = FunctionTool(tool_proxy, md)
    return register_function_tool(tool)

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

    tool = load_example_tool('examples/multiply-tool.json', lambda a, b: a * b)
    r = tool.call(a=5, b=2)
    logger.info(f"Result: {r}")