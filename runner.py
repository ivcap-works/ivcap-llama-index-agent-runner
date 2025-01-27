import threading
from typing import Any, Callable, Tuple
from llama_index.core.agent.runner.base import AgentRunner
import asyncio
import logging
import queue

from events import is_last_event, unregister_event_queue, register_event_queue

logger = logging.getLogger("runner")

def run_chat(agent: AgentRunner, msg: str) -> Tuple[queue.Queue, threading.Thread]:
    return _run(lambda: agent.chat(msg))

def run_query(agent: AgentRunner, msg: str) -> Tuple[queue.Queue, threading.Thread]:
    return _run(lambda: agent.query(msg))

def _run(fn: Callable[[], Any]) -> Tuple[queue.Queue, threading.Thread]:
    q = queue.Queue()

    def run():
        register_event_queue(q)
        response = fn()
        logger.debug(f"_run final response: {response}")
        q.put(None)
        unregister_event_queue(q)

    thread = threading.Thread(target=run)
    thread.start()
    return (q, thread)

if __name__ == "__main__":
    from llama_index.core.agent import ReActAgent
    from llama_index.llms.openai import OpenAI
    from dotenv import load_dotenv
    from tool import load_example_tool, resolve_tool
    import testing

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    llm = OpenAI(model="gpt-3.5-turbo-instruct")
    tools = [
        load_example_tool('examples/multiply-tool.json', lambda a, b: a * b),
        resolve_tool("urn:ivcap:service:ai-tool.add")
    ]
    agent = ReActAgent.from_tools(tools, llm=llm, verbose=False)
    q, t = run_chat(agent, "What is 2 + 3 * 5")
    while True:
        try:
            event = q.get(timeout=3)
            if event is None:
                break
            logger.info(f"event: {event}")
            q.task_done()
            if is_last_event(event):
                print(f">>>> Final response: {event.response}")
                break
        except queue.Empty:
            logger.info("eventloop .... timeout")
