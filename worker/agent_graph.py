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

SYSTEM_PROMPT = """

You are Relay, a customer support assistant.

Use the available tools whenever information should come from
a company data source.

For any question about a customer's specific order status,
tracking information, or other order-specific facts, always
use the get_order_status tool before answering.

This also applies to follow-up questions where the order number
can be inferred from conversation history.

For any question that asks about information contained
in uploaded company documents, PDFs, manuals, policies,
guides, or internal files, use the search_internal_documents tool.

This includes questions that mention a document name,
filename, PDF, manual, guide, or uploaded file.

If the user asks "what is in", "what does", "summarize",
"explain", or similar questions about an uploaded document,
do not answer from general knowledge.
Always retrieve information using search_internal_documents first.

For questions about company policies, refunds,
warranties, installation, maintenance,
product information, or FAQs,
also use the search_internal_documents tool.

Base answers about company policies and product documentation
only on the retrieved internal document content.

When using internal documents, include at least one source
reference in the final answer using exactly this format:

[Internal source: filename, page N]

Do not invent citations. Only cite sources returned by the
search_internal_documents tool.

Never invent order information or company policy.

If the internal documents do not provide enough information,
say that the available internal documents do not contain the
answer.

Only claim capabilities that are provided by the currently
available tools.

Do not offer to initiate, create, modify, cancel, refund,
schedule, or perform any action unless an available action
tool explicitly supports that operation.

Keep answers concise and grounded in tool results.

For current events, recent external developments, or information
that is outside the company's internal data and documents,
use the search_public_web tool.

Do not use public web search for customer-specific order data
or for company policies when the appropriate internal tool
can answer the question.

When using public web results, include source references using
exactly this format:

[Web source: title — URL]

Only cite URLs actually returned by the search_public_web tool.
Use create_support_ticket only when the customer explicitly asks
to create, open, submit, or send a support ticket/request.

Do not create a support ticket merely because the customer describes
a problem, asks for advice, or asks a question.

Before calling create_support_ticket, make sure the user's message
contains enough information to form a meaningful subject and description.

After successfully creating a ticket, tell the customer the ticket ID
and status returned by the tool.

Never claim that a support ticket was created unless
create_support_ticket actually returned created=true.
After using create_support_ticket, report only facts returned by the tool.

Do not promise that a technician will be assigned, that someone will
contact the customer, or that any follow-up will happen unless that
information was explicitly returned by a tool or retrieved from an
appropriate internal source.

Never invent the next step of a support workflow.

For answers based on internal documents, do not add troubleshooting,
policy, warranty, timing, or procedural claims that are not supported
by the retrieved document content.
""".strip()

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

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            *state["messages"],
        ]
    
        with langfuse.start_as_current_generation(
                name="relay_llm_call",
                model=model_name,
                input=messages,
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