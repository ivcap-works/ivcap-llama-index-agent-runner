from dataclasses import dataclass
from typing import ClassVar, List
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse, StreamingResponse

from pydantic import BaseModel, Field, ValidationError
import argparse
from signal import signal, SIGTERM
import sys
import os
from logger import getLogger, service_log_config
import queue
from dotenv import load_dotenv

from llama_index.core.agent import ReActAgent
from llama_index.llms.openai import OpenAI

# Load environment variables from the .env file
load_dotenv()

logger = getLogger("app")

from events import is_last_event, is_last_query_event
from runner import run_query
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

# Add support for JSON-RPC invocation (https://www.jsonrpc.org/)
# from ivcap_fastapi import use_json_rpc_middleware
# use_json_rpc_middleware(app)

# Add support for TryLaterException
# from ivcap_fastapi import TryLaterException, use_try_later_middleware
# use_try_later_middleware(app)

parser = argparse.ArgumentParser(description=title)
parser.add_argument('--host', type=str, default=os.environ.get("HOST", "0.0.0.0"), help='Host address')
parser.add_argument('--port', type=int, default=os.environ.get("PORT", "8080"), help='Port number')
parser.add_argument('--max-wait', type=int, default=30, help='Specifies the max number of seconds to wait for a reply')
parser.add_argument('--testing', action="store_true", help='Add tools for testing (testing.py)')

args = parser.parse_args()
max_wait = args.max_wait

class ModeE(StrEnum):
    Chat = "chat"
    Query = "query"

class ServiceRequest(SchemaModel):
    SCHEMA: ClassVar[str] = "urn:sd-core:schema:llama-agent.request.1"
    msg: str = Field(description="The message to a chat or query", examples=["what is 2 * 5"])
    tools: List[str] = Field([], description="The tools to use while processing this request", examples=[["multiply"]])
    mode: ModeE = Field(ModeE.Query, description="specifies if the message is a chat or a query")
    verbose: bool = Field(False, description="Whether to also return events produced during execution")

class ServiceResponse(SchemaModel):
    SCHEMA: ClassVar[str] = "urn:sd-core:schema:llama-agent.response.1"
    response: str = Field(description="The response to a query or chat")
    msg: str = Field(description="The message to a chat or query", examples=["what is 2 * 5"])

@dataclass
class Job:
    id: str
    msg: str
    queue: queue.Queue
    result: ServiceResponse = None

jobs:dict[str, Job] = {}

@app.post("/")
async def run(request: Request) -> ServiceResponse:
    try:
        data = await request.json()
        req = ServiceRequest(**data)
    except ValueError: # JSONDecodeError is a subclass of ValueError
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON data")
    except ValidationError as e:  # Catch Pydantic validation errors
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

    jobID = request.headers.get("x-job-uuid")
    jobURL = request.headers.get("x-job-url")

    #llm = OpenAI(model="gpt-3.5-turbo-instruct")
    llm = OpenAI(model="gpt-4-turbo")
    tools = [resolve_tool(urn) for urn in req.tools]
    agent = ReActAgent.from_tools(tools, llm=llm, verbose=False)
    q, _ = run_query(agent, req.msg)
    jobs[jobID] = Job(id = jobID, queue=q, msg=req.msg)
    return RedirectResponse(jobURL, status_code=status.HTTP_302_FOUND)

@app.get("/{job_id}")
async def get(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job details not found")

    if job.result: # check if already finished
        return job.result

    q = job.queue

    async def events():
        def to_data(ev: BaseModel):
            s = ev.model_dump_json(by_alias=True, exclude_none=True)
            return f"data: {s}\n\n"

        while True:
            try:
                event = await q.get()
                logger.debug(f"event: {event}")
                yield to_data(event)
                q.task_done()
                if is_last_query_event(event):
                    logger.info(f"Final response: {event.response}")
                    job.result = ServiceResponse(response=event.response, msg=job.msg)
                    yield to_data(job.result)
                    break
            except queue.Empty:
                logger.info("eventloop .... timeout")

    return StreamingResponse(events(), media_type="text/event-stream")

# Allows platform to check if everything is OK
@app.get("/_healtz")
def healtz():
    return {"version": os.environ.get("VERSION", "???")}

if __name__ == "__main__":
    logger.info(f"{title} - {os.getenv('VERSION')}")

    if args.testing:
        logger.info(f"Adding testing support defined in 'testing.py'")
        import testing  # noqa

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_config=service_log_config())