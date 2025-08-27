import os
from typing import Optional
from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL")


def make_generate_config(schema: Optional[dict] = None) -> Optional[types.GenerateContentConfig]:
    """
    Se 'schema' vier, força JSON com schema (Structured Output).
    """
    if not schema:
        return None
    return types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,  # JSON Schema
    )


def make_tools(function_declarations: list[types.FunctionDeclaration]) -> list[types.Tool]:
    return [types.Tool(function_declarations=function_declarations)]


def tool_config_auto() -> types.ToolConfig:
    # Ativa execução automática de funções (o modelo decide)
    return types.ToolConfig(
        function_calling=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="AUTO"))
    )


def generate(
    contents, 
    schema: Optional[dict] = None, 
    tools: Optional[list[types.Tool]] = None,
    stream: bool = False,
):
    return client.models.generate_content(
        model=CHAT_MODEL,
        contents=contents,
        generation_config=make_generate_config(schema),
        tools=tools,
        tool_config=tool_config_auto() if tools else None,
        stream=stream,  # streaming síncrono suportado no SDK
    )
