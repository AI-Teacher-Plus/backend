import os
from typing import Optional, Iterable
from google import genai
from google.genai import types
from collections.abc import Mapping

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL")


def make_generate_config(
    schema: Optional[dict] = None,
    tools: Optional[list[types.Tool]] = None,
    tool_config: Optional[types.ToolConfig] = None,
) -> Optional[types.GenerateContentConfig]:
    """
    Monta GenerateContentConfig conforme doc:
      - Structured output: response_mime_type + response_schema
      - Function calling: tools + tool_config
    """
    if not any([schema, tools, tool_config]):
        return None
    cfg_kwargs: dict = {}
    if schema:
        cfg_kwargs["response_mime_type"] = "application/json"
        cfg_kwargs["response_schema"] = schema
    if tools:
        cfg_kwargs["tools"] = tools
    if tool_config:
        cfg_kwargs["tool_config"] = tool_config
    return types.GenerateContentConfig(**cfg_kwargs)


# --- Sanitizadores para evitar 400 INVALID_ARGUMENT em tools ---
# Contexto: parâmetros de FunctionDeclaration aceitam só um subconjunto de OpenAPI.
# Campos como additionalProperties / patternProperties / $schema causam 400.
# Referências: doc + issues.
_DROP_KEYS = {
    "additionalProperties", "additional_properties",
    "$schema", "patternProperties", "unevaluatedProperties", "strict",
}

def _sanitize_schema_dict(d: Mapping) -> dict:
    out = {}
    for k, v in d.items():
        if k in _DROP_KEYS:
            continue
        if isinstance(v, Mapping):
            out[k] = _sanitize_schema_dict(v)
        elif isinstance(v, list):
            out[k] = [
                _sanitize_schema_dict(x) if isinstance(x, Mapping) else x
                for x in v
            ]
        else:
            out[k] = v
    return out

def _schema_from_dict(d: Mapping) -> types.Schema:
    """
    Converte um dict (p.ex. vindo de Pydantic/Zod) para types.Schema,
    removendo chaves não suportadas e normalizando 'type' (STRING/OBJECT/…).
    """
    d = _sanitize_schema_dict(d)
    t = d.get("type") or d.get("Type") or d.get("TYPE")
    if isinstance(t, str):
        t = t.upper()
    props = {
        k: _schema_from_dict(v) if isinstance(v, Mapping) else v
        for k, v in (d.get("properties") or {}).items()
    }
    items = d.get("items")
    if isinstance(items, Mapping):
        items = _schema_from_dict(items)
    return types.Schema(
        type=t,
        description=d.get("description"),
        enum=d.get("enum"),
        properties=props or None,
        items=items,
        required=d.get("required"),
        # não definir additionalProperties: tende a falhar em tools
    )

def _to_function_declaration(fd) -> types.FunctionDeclaration:
    if isinstance(fd, types.FunctionDeclaration):
        p = getattr(fd, "parameters", None)
        if isinstance(p, Mapping):
            p = _schema_from_dict(p)
            return types.FunctionDeclaration(name=fd.name, description=fd.description, parameters=p, response=fd.response)
        return fd
    if isinstance(fd, Mapping):
        params = fd.get("parameters")
        schema = _schema_from_dict(params) if isinstance(params, Mapping) else None
        return types.FunctionDeclaration(name=fd["name"], description=fd.get("description"), parameters=schema)
    raise TypeError("function_declarations must be FunctionDeclaration or dict")


def make_tools(function_declarations: list[types.FunctionDeclaration]) -> list[types.Tool]:
    decls = [_to_function_declaration(fd) for fd in function_declarations]
    return [types.Tool(function_declarations=decls)]


def tool_config_auto() -> types.ToolConfig:
    # Ativa execução automática de funções (o modelo decide)
    return types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(mode="AUTO")
    )


def generate(
    contents,
    schema: Optional[dict] = None,
    tools: Optional[list[types.Tool]] = None,
    stream: bool = False,
):
    """
    Geração unificada com/sem streaming.
    - Para streaming, use generate_content_stream(...) e itere .text dos chunks.
    """
    cfg = make_generate_config(
        schema=schema,
        tools=tools,
        tool_config=tool_config_auto() if tools else None,
    )
    if stream:
        return client.models.generate_content_stream(
            model=CHAT_MODEL,
            contents=contents,
            config=cfg,
        )
    return client.models.generate_content(
        model=CHAT_MODEL,
        contents=contents,
        config=cfg,
    )


def stream_text(
    contents,
    schema: Optional[dict] = None,
    tools: Optional[list[types.Tool]] = None,
) -> Iterable[str]:
    """
    Helper para SSE: devolve somente texto dos chunks de stream.
    """
    for chunk in generate(contents, schema=schema, tools=tools, stream=True):
        if getattr(chunk, "text", None):
            yield chunk.text
