# structured_output.py
"""
Helper để gọi LLM với structured output (qua tool_use forced).
"""

import json
from anthropic import Anthropic
from pydantic import BaseModel, ValidationError
from rich.console import Console

console = Console()


def call_with_schema(
    client: Anthropic,
    model: str,
    system_prompt: str,
    user_message: str,
    schema: type[BaseModel],
    max_tokens: int = 4096,
) -> tuple[BaseModel | None, dict]:
    """
    Gọi LLM với schema ép buộc.
    Trả về: (parsed_object, usage_dict)

    Cách hoạt động:
    1. Convert Pydantic schema → JSON Schema
    2. Wrap schema thành "tool"
    3. Force LLM phải gọi tool đó (không được trả text thường)
    4. LLM trả về tool_use với input đúng schema
    5. Parse và validate bằng Pydantic
    """
    # Convert Pydantic → JSON Schema
    json_schema = schema.model_json_schema()

    tool_name = f"output_{schema.__name__.lower()}"

    # Định nghĩa tool ép LLM dùng
    forced_tool = {
        "name": tool_name,
        "description": f"Trả về kết quả theo đúng schema {schema.__name__}",
        "input_schema": json_schema,
    }

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        tools=[forced_tool],
        # tool_choice ép LLM PHẢI gọi tool này (không được trả text)
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user_message}],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

    # Tìm tool_use block trong response
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            try:
                # Validate & parse bằng Pydantic
                parsed = schema(**block.input)
                return parsed, usage
            except ValidationError as e:
                console.print(f"[red]❌ LLM trả về data không đúng schema:[/red]")
                console.print(f"[red]{e}[/red]")
                console.print(
                    f"[dim]Raw input: {json.dumps(block.input, indent=2)}[/dim]"
                )
                return None, usage

    console.print("[red]❌ LLM không gọi tool[/red]")
    return None, usage
