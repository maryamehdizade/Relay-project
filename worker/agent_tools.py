from pydantic import BaseModel, Field
from langchain_core.tools import tool

from db_tools import get_order_status
from rag import search_internal_documents

class OrderStatusInput(BaseModel):
    order_number: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="The customer's order number, for example ORD-1001.",
    )


def build_order_status_tool(user_id: int):
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
        return get_order_status(
            user_id=user_id,
            order_number=order_number,
        )

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


@tool(
    "search_internal_documents",
    args_schema=InternalDocumentSearchInput,
)
def internal_document_search_tool(query: str) -> dict:
    """
    Search Relay's internal company documents.

    Use this for questions about company policies,
    product FAQs, refunds, warranty, installation,
    maintenance, and other internal documentation.
    """
    matches = search_internal_documents(
        query=query,
        n_results=3,
    )

    return {
        "matches": matches,
    }


