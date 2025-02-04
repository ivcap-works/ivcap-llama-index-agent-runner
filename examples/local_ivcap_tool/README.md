# Example on how to test a standalone Tool

This directory contains a standalone simple tool identical in functionality and
configuration of an IVCAP service-as-tool.

## [tool-service.py](./tool-service.py)

Implements a simple http based service which provides a `POST /` service endpoint to test
if the number contained in the request is a prime number or not.

```
% python tool-service.py
2025-02-04T19:30:34+1100 INFO (app): AI tool to check for prime numbers - None
2025-02-04T19:30:34+1100 INFO (uvicorn.error): Started server process [48314]
2025-02-04T19:30:34+1100 INFO (uvicorn.error): Waiting for application startup.
2025-02-04T19:30:34+1100 INFO (uvicorn.error): Application startup complete.
2025-02-04T19:30:34+1100 INFO (uvicorn.error): Uvicorn running on http://0.0.0.0:8090 (Press CTRL+C to quit)
```

The port and host can be set on the command line:
```
% python tool-service.py -h
usage: tool-service.py [-h] [--host HOST] [--port PORT]

AI tool to check for prime numbers

options:
  -h, --help   show this help message and exit
  --host HOST  Host address
  --port PORT  Port number
```

To test the tool, and for instance, test if `997` us a prime number:

```
% curl -X POST -H "content-type: application/json" --data "{\"number\": 997}" http://localhost:8090
{"number":997,"is_prime":true}
```

## [is-prime.tool.json](./is-prime.tool.json)

Describes the tool to allow the agent to understand what the tool can be used for.

Currently, this has to be done manually, but can easily be automated as all the information is available from
a well documented python function.

```
{
  "$schema": "urn:sd.core:schema:ai-tool.1",
  "name": "is-prime",
  "description": "Checks if a number is a prime number.",
  "type": "is_prime(number: integer) -> {number: integer, is_prime: bool}",
  "fn_schema": {
    "properties": {
      "number": {
        "title": "number to check",
        "type": "integer"
      }
    },
    "required": [
      "number"
    ],
    "title": "is_prime",
    "type": "object"
  }
}
```

## [test-agent.py](./test-agent.py)

Implements a simple ReAct agent to test the tool
```
% python test-agent.py -h
usage: test-agent.py [-h] [--model MODEL] [QUERY]

Test Agent for IsPrime tool

positional arguments:
  QUERY          The query for the agent ["Is 997 a prime number?"]

options:
  -h, --help     show this help message and exit
  --model MODEL  OpenAI model to use [gpt-3.5-turbo-instruct]
```

To check if a specific number is a prime?:

```
% python test-agent.py "Is 997 a prime number?"
INFO:agent:query: 'Is 997 a prime number?'
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/completions "HTTP/1.1 200 OK"
...
INFO:runner:event: type='ChatEvent' timestamp=datetime.datetime(2025, 2, 4, 19, 53, 18, 643549) response='997 is a prime number.'
>>>> Final response: 997 is a prime number.
```