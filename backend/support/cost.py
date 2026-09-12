from decimal import Decimal


# Groq pricing for openai/gpt-oss-120b
# Update here if provider pricing changes.

INPUT_PRICE_PER_MILLION = Decimal("0.15")
OUTPUT_PRICE_PER_MILLION = Decimal("0.60")


def calculate_llm_cost(
    input_tokens: int,
    output_tokens: int,
) -> Decimal:

    input_cost = (
        Decimal(input_tokens)
        / Decimal(1_000_000)
        * INPUT_PRICE_PER_MILLION
    )

    output_cost = (
        Decimal(output_tokens)
        / Decimal(1_000_000)
        * OUTPUT_PRICE_PER_MILLION
    )

    return input_cost + output_cost

TAVILY_SEARCH_COST = Decimal("0.008")


def calculate_web_cost(
    web_searches: int,
) -> Decimal:

    return (
        Decimal(web_searches)
        * TAVILY_SEARCH_COST
    )