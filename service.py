import os
import sys
this_dir = os.path.dirname(__file__)
src_dir = os.path.abspath(os.path.join(this_dir, "../../src"))
sys.path.insert(0, src_dir)

from typing import ClassVar, List, Optional
from fastapi import FastAPI

from pydantic import BaseModel, Field
import argparse
from signal import signal, SIGTERM

from dotenv import load_dotenv

from ivcap_ai_tool.builder import ToolOptions, add_tool_api_route
from ivcap_ai_tool.server import start_tool_server
from llama_index.core.agent import ReActAgent
from llama_index.llms.openai import OpenAI


from ivcap_fastapi import getLogger, logging_init

logging_init()
logger = getLogger("app")

# Load environment variables from the .env file
load_dotenv()

logger = getLogger("app")

#from runner import run_query
from tool import resolve_tool
from utils import SchemaModel, StrEnum

# shutdown pod cracefully
signal(SIGTERM, lambda _1, _2: sys.exit(0))

title = "LLamaIndex Agent Runner"
summary = "Executes queries or chats with LlamaIndex agents."
description = """
>>> A lot more usefule information here.
"""

app = FastAPI(
    title=title,
    description=description,
    summary=summary,
    version=os.environ.get("VERSION", "???"),
    contact={
        "name": "Max Ott",
        "email": "max.ott@data61.csiro.au",
    },
    docs_url="/docs", # ONLY set when there is no default GET
)

def service_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    parser.add_argument('--litellm-proxy', type=str, help='Address of the the LiteLlmProxy')
    parser.add_argument('--dump-builtin-ivcap-definitions', type=str, help='Write an IVCAP toold description for every builtin tool')
    parser.add_argument('--testing', action="store_true", help='Add tools for testing (testing.py)')

    args = parser.parse_args()

    if args.litellm_proxy != None:
        os.setenv("LITELLM_PROXY", args.litellm_proxy)

    if args.dump_builtin_ivcap_definitions:
        from tool import dump_builtin_ivcap_definitions
        dir = args.dump_builtin_ivcap_definitions
        dump_builtin_ivcap_definitions(dir)
        exit(0)

    if args.testing:
        logger.info(f"Adding testing support defined in 'testing.py'")
        import testing  # noqa

    import builtin_tools # registers all builtin tool

    return args

class ModeE(StrEnum):
    Chat = "chat"
    Query = "query"

class ServiceRequest(BaseModel):
    jschema: str = Field("urn:sd-core:schema.llama-agent.request.1", alias="$schema")
    msg: str = Field(description="The message to a chat or query", examples=["what is 2 * 5"])
    tools: List[str] = Field([], description="The tools to use while processing this request", examples=[["multiply"]])
    model: Optional[str] = Field("gpt-4-turbo", description="The model to use for the agent")
    mode: ModeE = Field(ModeE.Query, description="specifies if the message is a chat or a query")
    verbose: bool = Field(False, description="Whether to also return events produced during execution")

class ServiceResponse(BaseModel):
    jschema: str = Field("urn:sd-core:schema.llama-agent.1", alias="$schema")
    response: str = Field(description="The response to a query or chat")
    msg: str = Field(description="The message to a chat or query", examples=["what is 2 * 5"])

async def agent_runner(req: ServiceRequest) -> ServiceResponse:
    """Provides the ability to request a LlamaIndex ReAct agent to execute
    the query or chat requested."""

    llm = create_openai_client(req.model)
    tools = [resolve_tool(urn) for urn in req.tools]
    agent = ReActAgent.from_tools(tools, llm=llm, verbose=False)
    response = await agent.aquery(req.msg)
    answer = response.response
    return ServiceResponse(response=answer, msg=req.msg)

def create_openai_client(model: str) -> OpenAI:
    base_url = os.getenv("LITELLM_PROXY")
    if base_url == None:
        return OpenAI(model=model)
    else:
        return OpenAI(model=model, api_base=f"{base_url}/v1", api_key="not-needed")

add_tool_api_route(app, "/", agent_runner, opts=ToolOptions(tags=["ReAct Agent"], service_id="/"))

if __name__ == "__main__":
    start_tool_server(app, agent_runner, custom_args=service_args)
