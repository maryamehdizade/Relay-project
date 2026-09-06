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
