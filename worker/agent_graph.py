import os

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import tools_condition

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agent_tools import build_order_status_tool


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    order_number: str


def prepare_order_tool_call(state: AgentState):
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_order_status",
                        "args": {
                            "order_number": state["order_number"],
                        },
                        "id": "order-status-call",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    }


def build_order_graph(user_id: int):
    order_status_tool = build_order_status_tool(user_id)

    builder = StateGraph(AgentState)

    builder.add_node(
        "prepare_order_tool_call",
        prepare_order_tool_call,
    )

    builder.add_node(
        "tools",
        ToolNode([order_status_tool]),
    )

    builder.add_edge(
        START,
        "prepare_order_tool_call",
    )

    builder.add_edge(
        "prepare_order_tool_call",
        "tools",
    )

    builder.add_edge(
        "tools",
        END,
    )

    return builder.compile()

SYSTEM_PROMPT = """
You are Relay, a customer support assistant.

Use the available tools whenever customer-specific information
is required.

For any question about an order's status, tracking information,
or other order-specific facts, always use the get_order_status
tool before answering.

This rule also applies to follow-up questions where the order
number can be inferred from conversation history. Do not rely
only on an earlier assistant response for current order facts.

Never invent order information.

If the tool cannot find the requested order, tell the customer
that the order could not be found in their account.

Only claim capabilities that are provided by the currently
available tools. Do not offer to perform actions or retrieve
information that no available tool supports.

Keep answers concise and based on tool results.
""".strip()


def build_agent_graph(user_id: int):
    order_status_tool = build_order_status_tool(user_id)
    tools = [order_status_tool]

    api_key = os.getenv("LLM_API_KEY")
    model_name = os.getenv("LLM_MODEL")
    base_url = os.getenv("LLM_BASE_URL") or None

    if not api_key:
        raise RuntimeError("LLM_API_KEY is not configured.")

    if not model_name:
        raise RuntimeError("LLM_MODEL is not configured.")

    llm = ChatOpenAI(
        api_key=api_key,
        model=model_name,
        base_url=base_url,
        temperature=0,
    )

    llm_with_tools = llm.bind_tools(tools)

    def call_model(state: AgentState):
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            *state["messages"],
        ]

        response = llm_with_tools.invoke(messages)

        return {
            "messages": [response],
        }

    builder = StateGraph(AgentState)

    builder.add_node(
        "agent",
        call_model,
    )

    builder.add_node(
        "tools",
        ToolNode(tools),
    )

    builder.add_edge(
        START,
        "agent",
    )

    builder.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END,
        },
    )

    builder.add_edge(
        "tools",
        "agent",
    )

    return builder.compile()