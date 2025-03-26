
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Callable, ClassVar, Dict, ForwardRef, Optional, TypeAlias
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
from llama_index.core.base.base_query_engine import dispatcher
from llama_index.core.instrumentation.events.llm import (
    LLMChatEndEvent, ChatMessage, ChatResponse, LLMChatStartEvent
)
from llama_index.core.base.llms.types import  MessageRole

from llama_index.core.bridge.pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4
import threading
import logging
from utils import SchemaModel

logger = logging.getLogger("events")

EventHandler = Callable[["AgentEvent"], None]

def get_events(ctxt_id: str) -> list[BaseEvent]:
    return _event_handler.get_events(ctxt_id)

def is_last_event(event: BaseEvent) -> bool:
    if isinstance(event, QueryEvent):
        return event.status == Status.FINISHED
    if isinstance(event, ChatEvent):
        return event.status == Status.FINISHED
    return False

def is_last_query_event(event: BaseEvent) -> bool:
    if isinstance(event, QueryEvent):
        return event.status == Status.FINISHED
    return False

def create_event_id() -> UUID:
    return _event_handler.create_event_id()

def dispatch_event(ev: AgentEvent):
    _event_handler.event(ev)

def register_event_handler(ev_handler: EventHandler) -> EventHandler:
    """use 'ev_handler' to report all events issued on this particular thread"""
    return _event_handler.register_event_handler(ev_handler)

def unregister_event_handler(ev_handler: EventHandler):
    _event_handler.unregister_event_handler(ev_handler)

### INTERNAL


class Status(Enum):
    STARTED = "started"
    IN_PROGRESS = "in-progress"
    FINISHED = "finished"
    ERROR = "error"

span2ctxt: dict[str, any] = {}

class AgentEvent(SchemaModel):
    SCHEMA: ClassVar[str] = "urn:sd-core:schema:llama-agent.event.agent.1"

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        # copy_on_model_validation = "deep"  # not supported in Pydantic V2...
    )
    id: Optional[str] = ""
    status: Status
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
    SCHEMA: ClassVar[str] = "urn:sd-core:schema:llama-agent.event.llm.1"

    requests: list[LLMMessage]
    response: Optional[LLMMessage] = None

    @classmethod
    def from_chat_start_event(cls, e: LLMChatStartEvent):
        id = str(uuid4())
        span2ctxt[e.span_id] = id
        ts = e.timestamp
        requests = [LLMMessage.from_chat_message(m) for m in e.messages]
        return cls(
            id=str(id),
            status=Status.STARTED,
            timestamp=ts,
            requests=requests,
            response=None)

    @classmethod
    def from_chat_end_event(cls, e: LLMChatEndEvent):
        id = span2ctxt.pop(e.span_id, None)
        ts = e.timestamp
        requests = [LLMMessage.from_chat_message(m) for m in e.messages]
        if isinstance(e.response, ChatResponse):
            response = LLMMessage.from_chat_response(e.response)
        else:
            raise ValueError(f"Unexpected response type: {type(e.response)}")
        return cls(
            id=id,
            status=Status.FINISHED,
            timestamp=ts,
            requests=requests,
            response=response)

class ToolEvent(AgentEvent):
    SCHEMA: ClassVar[str] = "urn:sd-core:schema:llama-agent.event.tool.1"
    tool_name:str
    arguments: str
    response: Optional[Any] = None
    error: Optional[str] = None

    @classmethod
    def from_tool_event(cls, e: AgentToolCallEvent):
        id = str(uuid4())
        ts = e.timestamp
        return cls(
            id=id,
            status=Status.STARTED,
            ts=ts,
            tool_name=e.tool.name,
            arguments=e.arguments,
        )

    @classmethod
    def dispatch_tool_start(cls, tool_name, **kwargs) -> str:
        id = str(uuid4())
        ev = cls(
                id=id,
                status=Status.STARTED,
                tool_name=tool_name,
                arguments=str(kwargs))
        _event_handler.event(ev)
        return id

    @classmethod
    def dispatch_tool_end(cls, id, response, tool_name, **kwargs):
        ev = cls(
                id=id,
                response=response,
                status=Status.FINISHED,
                tool_name=tool_name,
                arguments=str(kwargs))
        _event_handler.event(ev)

    @classmethod
    def dispatch_tool_error(cls, id, err, tool_name, **kwargs):
        ev = cls(
                id=id,
                status=Status.ERROR,
                error=str(err),
                tool_name=tool_name,
                arguments=str(kwargs))
        _event_handler.event(ev)

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
    SCHEMA: ClassVar[str] = "urn:sd-core:schema:llama-agent.event.step.1"
    response: Optional[str] = None
    sources: Optional[list[Source]] = None
    is_last: Optional[bool] = None

    @classmethod
    def from_step_start_event(cls, e: AgentRunStepStartEvent):
        id = e.step.step_id if e.step != None else uuid4()
        span2ctxt[e.span_id] = id
        ts = e.timestamp
        return cls._from(id, Status.STARTED, ts)

    @classmethod
    def from_step_end_event(cls, e: AgentRunStepEndEvent):
        ts = e.timestamp
        sout = e.step_output
        id = sout.task_step.step_id
        is_last = sout.is_last
        output = sout.output
        return cls._from(id, Status.FINISHED, ts, output, is_last)

    @classmethod
    def _from(cls, id: UUID, status: Status, ts: datetime, agent_response: Optional[any]=None, is_last: Optional[bool]=None):
        if agent_response:
            if isinstance(agent_response, AgentChatResponse):
                response = agent_response.response
                sources = [Source.from_tool_output(s) for s in agent_response.sources]
            else:
                raise ValueError(f"Unexpected output type: {type(agent_response)}")
        else:
            response=None
            sources=None

        return cls(
            id=str(id),
            status=status,
            timestamp=ts,
            response=response,
            sources=sources,
            is_last=is_last,
        )

class ChatEvent(AgentEvent):
    SCHEMA: ClassVar[str] = "urn:sd-core:schema:llama-agent.event.chat.1"
    user_msg: str
    response: Optional[str] = None

    @classmethod
    def from_chat_start_event(cls, e: AgentChatWithStepStartEvent):
        ts = e.timestamp
        id = str(uuid4())
        ev = cls(
            id=id,
            status=Status.STARTED,
            timestamp=ts,
            user_msg=e.user_msg,
        )
        span2ctxt[e.span_id] = ev
        return ev

    @classmethod
    def from_chat_end_event(cls, e: AgentChatWithStepEndEvent):
        ctxt = span2ctxt.pop(e.span_id, None)
        ts = e.timestamp
        if isinstance(e.response, AgentChatResponse):
            response = e.response.response
        else:
            raise ValueError(f"Unexpected response type: {type(e.response)}")
        return cls(
            id=ctxt.id,
            status=Status.FINISHED,
            timestamp=ts,
            user_msg=ctxt.user_msg,
            response=response,
        )

class QueryEvent(AgentEvent):
    SCHEMA: ClassVar[str] = "urn:sd-core:schema:llama-agent.event.query.1"
    query: str
    response: Optional[str] = None

    @classmethod
    def from_query_start_event(cls, e: QueryStartEvent):
        id = str(uuid4())
        ts = e.timestamp
        ev = cls(
            id=id,
            status=Status.STARTED,
            timestamp=ts,
            query=e.query
        )
        span2ctxt[e.span_id] = ev
        return ev

    @classmethod
    def from_query_end_event(cls, e: QueryEndEvent):
        ctxt = span2ctxt.pop(e.span_id, None)
        ts = e.timestamp
        if isinstance(e.response, Response):
            response = e.response.response
        else:
            raise ValueError(f"Unexpected response type: {type(e.response)}")
        return cls(
            id=ctxt.id,
            status=Status.FINISHED,
            timestamp=ts,
            query=ctxt.query,
            response=response,
        )

class EventHandler(BaseEventHandler):
    @classmethod
    def class_name(cls) -> str:
        return "MyEventHandler"

    def __init__(self):
        super().__init__()
        self._events = {}
        self._ev_handlers = {}
        self._thread_local = threading.local()

    def get_events(self, thread_id: str) -> list[AgentEvent]:
        return self._events.get(thread_id, [])

    def create_event_id(self) -> UUID:
        eid = uuid4()
        self._thread_local.eid = eid
        return eid

    def register_event_handler(self, ev_handler: EventHandler) -> EventHandler:
        qid = uuid4()
        self._thread_local.qid = qid
        self._ev_handlers[qid] = ev_handler
        return ev_handler

    def unregister_event_handler(self, ev_handler: EventHandler):
        for qid, q in self._ev_handlers.items():
            if q == ev_handler:
                del self._ev_handlers[qid]
                break

    def handle(self, event: BaseEvent, **kwargs):
        try:
            ev = self._process_event(event)
        except Exception as e:
            logger.error(f"handler: processing event: {e}")
            return
        if ev is None: return
        self.event(ev)

    def event(self, ev: AgentEvent):
        qid = getattr(self._thread_local, "qid", None)
        if qid is not None:
            ev_handler = self._ev_handlers.get(qid, None)
            if ev_handler is not None:
                #asyncio.run_coroutine_threadsafe(ev_handler.put(ev), asyncio.get_running_loop())
                # ev_handler.put(ev)
                ev_handler(ev)
            else:
                logger.warning(f"handler: EventHandler not found: {qid}")

    def _process_event(self, event: BaseEvent) -> AgentEvent:
        if isinstance(event, LLMChatStartEvent):
            return LLMChatEvent.from_chat_start_event(event)
        if isinstance(event, LLMChatEndEvent):
            return LLMChatEvent.from_chat_end_event(event)

        if isinstance(event, AgentToolCallEvent):
            # return ToolEvent.from_tool_event(event)
            return None # we now handle that directly

        if isinstance(event, AgentRunStepStartEvent):
            return StepEvent.from_step_start_event(event)
        if isinstance(event, AgentRunStepEndEvent):
            return StepEvent.from_step_end_event(event)

        if isinstance(event, AgentChatWithStepStartEvent):
            return ChatEvent.from_chat_start_event(event)
        if isinstance(event, AgentChatWithStepEndEvent):
            return ChatEvent.from_chat_end_event(event)

        if isinstance(event, QueryStartEvent):
            return QueryEvent.from_query_start_event(event)
        if isinstance(event, QueryEndEvent):
            return QueryEvent.from_query_end_event(event)

        # ignore these events
        if isinstance(event, SpanDropEvent):
            return None

        logger.warning(f"eventHandler ignoring event: {event.class_name()}")
        return None

_event_handler = EventHandler()
_dispatcher = instrument.get_dispatcher()
_dispatcher.add_event_handler(_event_handler)
