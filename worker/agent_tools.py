from pydantic import BaseModel, Field
from langchain_core.tools import tool

from db_tools import (get_order_status, create_support_ticket)
from rag import search_internal_documents
import os

from tavily import TavilyClient

class OrderStatusInput(BaseModel):
    order_number: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="The customer's order number, for example ORD-1001.",
    )


def build_order_status_tool(user_id: int, langfuse,):
    @tool(
        "get_order_status",
        args_schema=OrderStatusInput,
    )
    def order_status_tool(order_number: str) -> dict:
        """
        Look up the authenticated customer's order status.

        Use this when the customer asks about the status,
        tracking information, or existence of one of their orders.
        """
        with langfuse.start_as_current_span(
            name="tool_get_order_status",
            input={
                "order_number": order_number,
                "user_id": user_id,
            },
        ) as span:
        
            result = get_order_status(
                user_id=user_id,
                order_number=order_number,
            )
        
            span.update(
                output=result,
            )
        
            return result

    return order_status_tool


class InternalDocumentSearchInput(BaseModel):
    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description=(
            "A question about internal company policies, "
            "product information, warranty, refunds, or FAQs."
        ),
    )


def build_internal_document_search_tool(user_id: int, langfuse,):
    @tool(
        "search_internal_documents",
        args_schema=InternalDocumentSearchInput,
    )
    def internal_document_search_tool(
        query: str,
    ) -> dict:
        """
        Search company-wide and authenticated-user
        internal documents.

        Use this for policies, product FAQs,
        refunds, warranties, and internal documents.
        """
        with langfuse.start_as_current_span(
            name="tool_search_internal_documents",
            input={
                "query": query,
                "user_id": user_id,
            },
        ) as span:
        
            matches = search_internal_documents(
                query=query,
                user_id=user_id,
                n_results=3,
            )
        
            result = {
                "matches": matches,
            }
        
            span.update(
                output=result,
            )
        
            return result

    return internal_document_search_tool


class PublicWebSearchInput(BaseModel):
    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description=(
            "A question that requires current or external "
            "information from the public web."
        ),
    )


def build_public_web_search_tool(langfuse):

    @tool(
        "search_public_web",
        args_schema=PublicWebSearchInput,
    )
    def public_web_search_tool(query: str) -> dict:
        """
        Search the public web for current or external information.

        Use this when the answer depends on information outside
        the company's internal database and documents.
        """

        with langfuse.start_as_current_span(
            name="tool_search_public_web",
            input={
                "query": query,
            },
        ) as span:

            api_key = os.getenv("TAVILY_API_KEY")

            if not api_key:
                raise RuntimeError(
                    "TAVILY_API_KEY is not configured."
                )

            client = TavilyClient(
                api_key=api_key,
            )

            response = client.search(
                query=query,
                search_depth="basic",
                max_results=5,
                include_answer=False,
            )

            results = []

            for item in response.get("results", []):
                results.append(
                    {
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "content": item.get("content"),
                        "score": item.get("score"),
                        "source_type": "web",
                    }
                )

            result = {
                "results": results,
            }

            span.update(
                output=result,
            )

            return result

    return public_web_search_tool

class CreateSupportTicketInput(BaseModel):
    subject: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Short subject describing the customer's support issue.",
    )

    description: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Clear description of the customer's support issue.",
    )


def build_create_support_ticket_tool(user_id: int, correlation_id: str, langfuse,):
    @tool(
        "create_support_ticket",
        args_schema=CreateSupportTicketInput,
    )
    def create_support_ticket_tool(
        subject: str,
        description: str,
    ) -> dict:
        """
        Create a support ticket for the authenticated customer.

        Use this only when the customer explicitly asks to open,
        create, submit, or send a support request.
        """
        with langfuse.start_as_current_span(
            name="tool_create_support_ticket",
            input={
                "subject": subject,
                "description": description,
                "user_id": user_id,
            },
        ) as span:
        
            result = create_support_ticket(
                user_id=user_id,
                correlation_id=correlation_id,
                subject=subject,
                description=description,
            )
        
            span.update(
                output=result,
            )
        
            return result

    return create_support_ticket_tool

