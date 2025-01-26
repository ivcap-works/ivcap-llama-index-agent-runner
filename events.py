
from datetime import datetime
from typing import Any, Dict
import llama_index.core.instrumentation as instrument

from llama_index.core.instrumentation.event_handlers.base import BaseEventHandler
from llama_index.core.instrumentation.events import BaseEvent
from llama_index.core.instrumentation.events.agent import (
    AgentRunStepEndEvent, AgentChatResponse, AgentChatWithStepEndEvent,
    AgentToolCallEvent, AgentRunStepStartEvent, AgentChatWithStepStartEvent
)
from llama_index.core.instrumentation.events.query import QueryStartEvent, QueryEndEvent
from llama_index.core.instrumentation.events.span import SpanDropEvent
from llama_index.core.tools import ToolOutput
from llama_index.core.base.response.schema import Response
from llama_index.core.instrumentation.events.llm import (
    LLMChatEndEvent, ChatMessage, ChatResponse, LLMChatStartEvent
)
from llama_index.core.base.llms.types import  MessageRole

from llama_index.core.bridge.pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4
import threading
import logging
from queue import Queue

logger = logging.getLogger("events")

def get_events(ctxt_id: str) -> list[BaseEvent]:
    return _event_handler.get_events(ctxt_id)

def is_last_event(event: BaseEvent) -> bool:
    if isinstance(event, QueryEvent):
        return True
    if isinstance(event, ChatEvent):
        return True
    return False

def create_event_id() -> UUID:
    return _event_handler.create_event_id()

def create_event_queue() -> Queue:
    return _event_handler.create_event_queue()

def register_event_queue(queue: Queue) -> Queue:
    """use 'queue' to report all events issued on this particular thread"""
    return _event_handler.register_event_queue(queue)

def unregister_event_queue(queue: Queue):
    _event_handler.unregister_event_queue(queue)

### INTERNAL

class AgentEvent(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        # copy_on_model_validation = "deep"  # not supported in Pydantic V2...
    )
    type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now())

class LLMMessage(BaseModel):
    content: str
    role: str

    @classmethod
    def from_chat_message(cls, m: ChatMessage):
        content=m.content
        role=m.role.value
        if m.role == MessageRole.SYSTEM:
            content="** system **"
        return cls(
            content=content,
            role=role,
        )

    @classmethod
    def from_chat_response(cls, r: ChatResponse):
        m = r.message
        return cls.from_chat_message(m)

class LLMChatEvent(AgentEvent):
    type: str = "LLMChatEvent"
    requests: list[LLMMessage]
    response: LLMMessage

    @classmethod
    def from_chat_end_event(cls, e: LLMChatEndEvent):
        ts = e.timestamp
        requests = [LLMMessage.from_chat_message(m) for m in e.messages]
        if isinstance(e.response, ChatResponse):
            response = LLMMessage.from_chat_response(e.response)
        else:
            raise ValueError(f"Unexpected response type: {type(e.response)}")
        return cls(
            type="LLMChatEvent",
            timestamp=ts,
            requests=requests,
            response=response)

class Source(BaseModel):
    content: str
    tool_name: str
    input: Dict[str, Any]
    is_error: bool = False

    @classmethod
    def from_tool_output(cls, e: ToolOutput):
        return cls(
            content=e.content,
            tool_name=e.tool_name,
            input=e.raw_input,
            is_error=e.is_error,
        )

class StepEvent(AgentEvent):
    response: str
    sources: list[Source]
    is_last: bool

    @classmethod
    def from_step_end_event(cls, e: AgentRunStepEndEvent):
        ts = e.timestamp
        sout = e.step_output
        is_last = sout.is_last
        output = sout.output
        return cls._from(ts, output, is_last)


    @classmethod
    def _from(cls, ts: datetime, agent_response: any,  is_last: bool):
        if isinstance(agent_response, AgentChatResponse):
            response = agent_response.response
            sources = [Source.from_tool_output(s) for s in agent_response.sources]
        else:
            raise ValueError(f"Unexpected output type: {type(agent_response)}")

        return cls(
            type="StepEvent",
            timestamp=ts,
            response=response,
            sources=sources,
            is_last=is_last,
        )

class ChatEvent(AgentEvent):
    response: str

    @classmethod
    def from_chat_end_event(cls, e: AgentChatWithStepEndEvent):
        ts = e.timestamp
        if isinstance(e.response, AgentChatResponse):
            response = e.response.response
        else:
            raise ValueError(f"Unexpected response type: {type(e.response)}")
        return cls(
            type="ChatEvent",
            timestamp=ts,
            response=response,
        )

class QueryEvent(AgentEvent):
    response: str

    @classmethod
    def from_query_end_event(cls, e: QueryEndEvent):
        ts = e.timestamp
        if isinstance(e.response, Response):
            response = e.response.response
        else:
            raise ValueError(f"Unexpected response type: {type(e.response)}")
        return cls(
            type="QueryEvent",
            timestamp=ts,
            response=response,
        )


class EventHandler(BaseEventHandler):
    @classmethod
    def class_name(cls) -> str:
        return "MyEventHandler"

    def __init__(self):
        super().__init__()
        self._events = {}
        self._queues = {}
        self._thread_local = threading.local()

    def get_events(self, thread_id: str) -> list[AgentEvent]:
        return self._events.get(thread_id, [])

    def create_event_id(self) -> UUID:
        eid = uuid4()
        self._thread_local.eid = eid
        return eid

    def create_event_queue(self) -> Queue:
        queue = Queue()
        return self.register_event_queue(queue)

    def register_event_queue(self, queue: Queue) -> Queue:
        qid = uuid4()
        self._thread_local.qid = qid
        self._queues[qid] = queue
        return queue

    def unregister_event_queue(self, queue: Queue):
        for qid, q in self._queues.items():
            if q == queue:
                del self._queues[qid]
                break

    def handle(self, event: BaseEvent, **kwargs):
        try:
            ev = self._process_event(event)
        except Exception as e:
            logger.error(f"handler: processing event: {e}")
            return
        if ev is None: return

        qid = getattr(self._thread_local, "qid", None)
        if qid is not None:
            queue = self._queues.get(qid, None)
            if queue is not None:
                queue.put(ev)
            else:
                logger.warning(f"handler: Queue not found: {qid}")

    def _process_event(self, event: BaseEvent) -> AgentEvent:
        if isinstance(event, LLMChatEndEvent):
            return LLMChatEvent.from_chat_end_event(event)
        if isinstance(event, AgentRunStepEndEvent):
            return StepEvent.from_step_end_event(event)
        if isinstance(event, AgentChatWithStepEndEvent):
            return ChatEvent.from_chat_end_event(event)
        if isinstance(event, QueryEndEvent):
            return QueryEvent.from_query_end_event(event)

        # ignore these events
        if isinstance(event, AgentToolCallEvent):
            return None
        if isinstance(event, AgentRunStepStartEvent):
            return None
        if isinstance(event, AgentChatWithStepStartEvent):
            return
        if isinstance(event, LLMChatStartEvent):
            return None
        if isinstance(event, QueryStartEvent):
            return None
        if isinstance(event, SpanDropEvent):
            return None

        logger.warning(f"eventHandler ignoring event: {event.class_name()}")
        return None

_event_handler = EventHandler()
_dispatcher = instrument.get_dispatcher()
_dispatcher.add_event_handler(_event_handler)
