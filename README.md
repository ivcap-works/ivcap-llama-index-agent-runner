# IVCAP LlamaIndex ReActAgent Service

This directory implements an IVCAP service which can query or chat with
a basic [LlamaIndex ReActAgent](https://docs.llamaindex.ai/en/stable/understanding/agent/).

* [Development Setup](#setup)
* [Build & Deploy Service](#build-deployment)
* [Testing Tools](#testing-tools)
* [Design Notes](#design)


## Development Setup <a name="setup"></a>

### Python

First, we need to setup a Python environment. We are using `conda`, but `venv` is
also a widely used alternative

```
conda create --name llama python=3.11 -y
conda activate llama
pip install -r requirements.txt
```

> Important: You will also need to add a `.env` file containing your API_KEYS (depending
on the tools your crews are using)

.env:
```
OPENAI_API_KEY=your_openai_api_key
```

### Initial Test of Service - Locally

Finally, to check if everything is properly installed, use the `run` target to execute the service with a simple agent and query locally:

```
% make run-runner
python runner.py
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/completions "HTTP/1.1 200 OK"
INFO:runner:event: type='LLMChatEvent' ...
INFO:runner:event: type='StepEvent' ...
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/completions "HTTP/1.1 200 OK"
INFO:runner:event: type='LLMChatEvent' ...
INFO:runner:event: type='StepEvent' ...
...
>>>> Final response: 17
```

### Initial Test of Service - HTTP Service

An "normal" deployment is to run the service as an HTTP server waiting for requests:

```
% make run
env VERSION="|644cb0d|2025-01-27T15:56+11:00" \
        python service.py --host localhost --port 8096 --max-wait 10 --testing
2025-01-27T15:56:43+1100 INFO (app): LLamaIndex Agent Runner - |644cb0d|2025-01-27T15:56+11:00
2025-01-27T15:56:43+1100 INFO (app): Adding testing support defined in 'testing.py'
2025-01-27T15:56:43+1100 INFO (uvicorn.error): Started server process [98338]
2025-01-27T15:56:43+1100 INFO (uvicorn.error): Waiting for application startup.
2025-01-27T15:56:43+1100 INFO (uvicorn.error): Application startup complete.
2025-01-27T15:56:43+1100 INFO (uvicorn.error): Uvicorn running on http://localhost:8096 ...
```

The service is now waiting at local port 8096 for requests. The Makefile already defines a
target to use curl to send such request. In a different terminal, issue the following:

```
% make submit-request
curl -X POST -H "Content-Type: application/json" -d @/Users/ott030/src/IVCAP/Services/ivcap-lli-ReActAgent/examples/simple_query.json http://localhost:8096
date: Mon, 27 Jan 2025 04:58:59 GMT
server: uvicorn
content-length: 97
content-type: application/json

{"$schema":"urn:sd.core:schema:llama-agent.response.1","response":"4410","msg":"what is 45 * 98"}
```

## Build & Deploy Service <a name="build-deployment"></a>

An IVCAP service usually consists of a _service description_ and one or more docker
containers implementing the computation components of the service.

The included [Makefile](./Makefile) has already defined a few targets for these tasks.

### Build the Docker Container

For this example, we only require a single docker container as defined in [Dockerfile](./Dockerfile). To build it locally, use:

```
make docker-build
```

To locally test the docker container:
```
% make docker-run
docker run -it \
                -p 8096:8080 \
                --user "502:20" \
                llama_index_agent_runner
2025-01-27T05:23:29+0000 INFO (app): LLamaIndex Agent Runner - None
2025-01-27T05:23:29+0000 INFO (uvicorn.error): Started server process [1]
2025-01-27T05:23:29+0000 INFO (uvicorn.error): Waiting for application startup.
2025-01-27T05:23:29+0000 INFO (uvicorn.error): Application startup complete.
2025-01-27T05:23:29+0000 INFO (uvicorn.error): Uvicorn running on http://0.0.0.0:8080 ...
```

## Testing Tools <a name="testing-tools"></a>

In production, all tools are supposed to deployed as independent IVCAP services. However, developing and testing agents with specific tools locally will likely be beneficial.

The [testing.py](./testing.py) file provides a simple example on how to register a locally implemented tool.

```
# register local function as tool
def add(a: int, b: int) -> int:
    """Add two integers and returns the result integer"""
    return a + b
register_function_as_tool(add)
```

This tool is now registered as `urn:ivcap:service:ai-tool.add` and can be resolved to a
`llama_index.core.tools.BaseTool` with `resolve_tool("urn:ivcap:service:ai-tool.add")`

Check the bottom part of [runner.py](./runner.py) for an example on how to test an agent and its respective tools locally:

```python
...
llm = OpenAI(model="gpt-3.5-turbo-instruct")
tools = [
  load_example_tool('examples/multiply-tool.json', lambda a, b: a * b),
  resolve_tool("urn:ivcap:service:ai-tool.add")
]
agent = ReActAgent.from_tools(tools, llm=llm, verbose=False)
q, t = run_chat(agent, "What is 2 + 3 * 5")
...
```

## Design Notes <a name="design"></a>

### [service.py](./service.py)

The [service.py](./service.py) file implements a simple FastAPI service. It specifically declares the "shape" of the incoming request (`class Request`) as well as the response (`class Response`) to be used for the default service target (`POST /`).

The `run` function defines a simple agent and calls the `run_query` method defined in [runner.py](./runner.py). This method returns a queue object which holds all the events generated as the agent executes. The current implementation  simply loops over all the events as they become available and returns the event which returns true to `is_last_event(event)`.

> Note: There is also a `run_chat` method, but as there is no session support implemented at this stage, there would be no difference in execution and result to `run_query`

> Note: The current implementation blocks on `event = q.get(timeout=3)`, blocking any other waiting service requests. This part of the code will need to be changed to a) wrap `queue` into an "awaitable" one and b) immediately return events as intermediate responses if so requested.

### [runner.py](./runner.py)

The core of the functionality of this file is in the `_run` function which creates an event queue and a separate thread to run
the agent in. Using separate threads allows us to run multiple agents simultaneously.

> Note: It's in this method where we most likely will add the required state management for supporting chat sessions.

### [events.py](./events.py)

This file implements functionality to "reduce" the many events generated by the llama_index library into a smaller number of relevant ones. It also uses `threading.local()` to assign events to the appropriate agent as the llama_index events do not identify that.

> Note: Executing more complex agents may trigger event types which are not handled yet. In this case, a warning  message will be logged (`logger.warning(f"eventHandler ignoring event: {event.class_name()}")`)