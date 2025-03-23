import threading
from typing import Any, Callable, Tuple
from llama_index.core.agent.runner.base import AgentRunner
import logging
import queue
import asyncio

from events import is_last_event, register_event_handler, unregister_event_handler

logger = logging.getLogger("runner")

def run_chat(agent: AgentRunner, msg: str) -> Tuple[queue.Queue, threading.Thread]:
    return _run(lambda: agent.chat(msg))

def run_query(agent: AgentRunner, msg: str) -> Tuple[queue.Queue, threading.Thread]:
    return _run(lambda: agent.query(msg))

def wait_for_result(t: Tuple[queue.Queue, threading.Thread]) -> str:
    q = t[0]
    while True:
        try:
            event = q.get(timeout=3)
            if event is None:
                break
            logger.info(f"event: {event}")
            q.task_done()
            if is_last_event(event):
                return event.response
        except queue.Empty:
            logger.info("eventloop .... timeout")
    return None


def _run(fn: Callable[[], Any]) -> Tuple[queue.Queue, threading.Thread]:
    q = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def run():
        def ev_handler(ev):
            asyncio.run_coroutine_threadsafe(q.put(ev), loop)

        register_event_handler(ev_handler)
        response = fn()
        logger.debug(f"_run final response: {response}")
        ev_handler(None)
        unregister_event_handler(ev_handler)

    thread = threading.Thread(target=run)
    thread.start()
    return (q, thread)

if __name__ == "__main__":
    from llama_index.core.agent import ReActAgent
    from llama_index.llms.openai import OpenAI
    from dotenv import load_dotenv
    from tool import resolve_tool

    #import testing # registers various tools and utilities defined in ./testing.py
    import builtin_tools # registers all builtin tool


    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    async def main():
        llm = OpenAI(model="gpt-3.5-turbo-instruct")
        tools = [
            resolve_tool("urn:sd-core:llama.builtin.mulInt"),
            resolve_tool("urn:sd-core:llama.builtin.addInt"),
        ]
        agent = ReActAgent.from_tools(tools, llm=llm, verbose=False)
        result = wait_for_result(run_query(agent, "What is 2 + 3 * 5"))
        print(f">>>> Final response: {result}")

    asyncio.run(main())
