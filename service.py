from time import sleep
from typing import ClassVar, List
from fastapi import FastAPI
from pydantic import Field
import argparse
from signal import signal, SIGTERM
import sys
import os
import logging
import queue

from llama_index.core.agent import ReActAgent
from llama_index.llms.openai import OpenAI

from uvicorn.config import LOGGING_CONFIG
log_config = LOGGING_CONFIG

logger = logging.getLogger("app")

lc = LOGGING_CONFIG.copy()
lc["loggers"] = {
    "app": {"level": "DEBUG", "handlers": ["default"]},
    "ivcap-tool": {"level": "INFO", "handlers": ["default"]},
    "events": {"level": "INFO", "handlers": ["default"]},
}
logging.config.dictConfig(lc)

from events import is_last_event
from runner import run_chat
from tool import load_example_tool, resolve_tool
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

# Add support for JSON-RPC invocation (https://www.jsonrpc.org/)
from ivcap_fastapi import use_json_rpc_middleware
use_json_rpc_middleware(app)

# Add support for TryLaterException
from ivcap_fastapi import TryLaterException, use_try_later_middleware
use_try_later_middleware(app)

parser = argparse.ArgumentParser(description=title)
parser.add_argument('--host', type=str, default=os.environ.get("HOST", "localhost"), help='Host address')
parser.add_argument('--port', type=int, default=os.environ.get("PORT", "8080"), help='Port number')

parser.add_argument('--max-wait', type=int, default=30, help='Specifies the max number of seconds to wait for a reply')

parser.add_argument('--testing', type=bool, default=False, help='Add tools for testing (testing.py)')

args = parser.parse_args()
max_wait = args.max_wait

class ModeE(StrEnum):
    Chat = "chat"
    Query = "query"

class Request(SchemaModel):
    SCHEMA: ClassVar[str] = "urn:sd.core:schema:llama-agent.request.1"
    msg: str = Field(description="The message to a chat or query", examples=["what is 2 * 5"])
    tools: List[str] = Field([], description="The tools to use while processing this request", examples=[["multiply"]])
    mode: ModeE = Field(ModeE.Query, description="specifies if the message is a chat or a query")
    verbose: bool = Field(False, description="Whether to also return events produced during execution")

class Response(SchemaModel):
    SCHEMA: ClassVar[str] = "urn:sd.core:schema:llama-agent.response.1"
    response: str = Field(description="The response to a query or chat")
    msg: str = Field(description="The message to a chat or query", examples=["what is 2 * 5"])

@app.post("/")
def run(req: Request) -> Response:
    llm = OpenAI(model="gpt-3.5-turbo-instruct")

    tools = [resolve_tool(urn) for urn in req.tools]
    agent = ReActAgent.from_tools(tools, llm=llm, verbose=False)
    q, t = run_chat(agent, req.msg)
    while True:
        try:
            event = q.get(timeout=3)
            if event is None:
                break
            logger.debug(f"event: {event}")
            q.task_done()
            if is_last_event(event):
                logger.info(f"Final response: {event.response}")
                return Response(response=event.response, msg=req.msg)
                #break
        except queue.Empty:
            logger.info("eventloop .... timeout")

    raise Exception("finished without finding a result")

# jobs = {}

# @app.get("/jobs/{jobID}")
# def get_job(jobID: str) -> Response:
#     req = jobs[jobID]
#     return work(req)


# Allows platform to check if everything is OK
@app.get("/_healtz")
def healtz():
    return {"version": os.environ.get("VERSION", "???")}

if __name__ == "__main__":
    if args.testing:
        import testing  # noqa

    import uvicorn
    logger.info(f"{title} - {os.getenv('VERSION')}")
    uvicorn.run(app, host=args.host, port=args.port, log_config=log_config)