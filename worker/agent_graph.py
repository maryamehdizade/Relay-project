import os
import json
import pika
import uuid


from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import tools_condition

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agent_tools import (build_order_status_tool, build_internal_document_search_tool,
                          build_public_web_search_tool, build_create_support_ticket_tool)


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    order_number: str
    usage: dict
    web_searches: int


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

def get_system_prompt(langfuse):

    prompt = langfuse.get_prompt(
        "relay-prompt"
    )

    return {
        "text": prompt.compile(),
        "name": prompt.name,
        "version": prompt.version,
    }

def publish_activity(
    channel,
    conversation_id,
    correlation_id,
    user_id,
    message,
    status="running",
):
    event = {
        "version": "1.0",
        "event_id": str(uuid.uuid4()),
        "correlation_id": correlation_id,
        "type": "agent.activity",
        "payload": {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "message": message,
            "status": status,
        },
    }
    try:

       channel.basic_publish(
           exchange="ai.events",
           routing_key=f"conversation.{conversation_id}",
           body=json.dumps(event),
           properties=pika.BasicProperties(
               delivery_mode=2,
           ),
       )
    except Exception as exc:
        print(
            f"Activity publish failed: {exc}"
        )



def build_agent_graph(user_id: int, correlation_id: str,langfuse, channel,conversation_id: int,):
    order_status_tool = build_order_status_tool(user_id, langfuse)
    internal_document_search_tool = (build_internal_document_search_tool(user_id, langfuse))
    create_support_ticket_tool = build_create_support_ticket_tool(user_id, correlation_id, langfuse)
    public_web_search_tool = build_public_web_search_tool(langfuse,)
    tools = [order_status_tool, internal_document_search_tool, public_web_search_tool, 
             create_support_ticket_tool]

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
        system_prompt = get_system_prompt(
            langfuse
        )
        messages = [
            SystemMessage(content=system_prompt["text"]),
            *state["messages"],
        ]
    
        with langfuse.start_as_current_generation(
                name="relay_llm_call",
                model=model_name,
                input=messages,
                 metadata={
                    "prompt_name": system_prompt["name"],
                    "prompt_version": system_prompt["version"],
                },
            ) as generation:
            
                response = llm_with_tools.invoke(messages)
                usage = response.usage_metadata or {}


                
                generation.update(
                    output=response.content,
                    usage_details={
                        "input": usage.get("input_tokens", 0),
                        "output": usage.get("output_tokens", 0),
                        "total": usage.get("total_tokens", 0),
                    },
                )
    
        return {
            "messages": [response],
            "usage": usage,
        }

    builder = StateGraph(AgentState)

    builder.add_node(
        "agent",
        call_model,
    )

    tool_node = ToolNode(tools)


    def run_tools(state: AgentState):
        last_message = state["messages"][-1]
        for tool_call in last_message.tool_calls:

            tool_name = tool_call["name"]
    
            activity_map = {
                "get_order_status":
                    "Searching orders...",
    
                "search_internal_documents":
                    "Reading internal documents...",
    
                "search_public_web":
                    "Searching web...",
    
                "create_support_ticket":
                    "Creating support ticket...",
            }
    
            publish_activity(
                channel,
                conversation_id,
                correlation_id,
                user_id,
                activity_map.get(
                    tool_name,
                    "Using tool...",
                ),
            )

        try:
    
            result = tool_node.invoke(state)
        
            web_searches = state.get(
                "web_searches",
                0,
            )
        
            for message in result["messages"]:
        
                if isinstance(message, ToolMessage):
    
                    publish_activity(
                        channel,
                        conversation_id,
                        correlation_id,
                        user_id,
                        "Tool execution completed",
                        "completed",
                    )
    
        
                    content = str(
                        message.content
                    )
        
                    if "web_searches" in content:
                        web_searches += 1
        
            return {
                **result,
                "web_searches": web_searches,
            }

        except Exception as e:

            publish_activity(
                channel,
                conversation_id,
                correlation_id,
                user_id,
                "Tool execution failed",
                "failed",
            )
        
            raise e
    
    
    builder.add_node(
        "tools",
        run_tools,
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