import asyncio

from backend.app.services.mistral.connectors import MistralConnectorClient


async def check() -> None:
    client = MistralConnectorClient()
    tools = await client.list_tools(refresh=True)
    if not tools:
        raise RuntimeError("The configured connector returned no tools.")

    print("connector_configuration=ok")
    print(f"tool_count={len(tools)}")
    for tool in sorted(tools, key=lambda item: item.name):
        properties = tool.input_schema.get("properties", {})
        required = tool.input_schema.get("required", [])
        print(
            f"tool={tool.name};"
            f"parameters={','.join(sorted(properties))};"
            f"required={','.join(sorted(required))}"
        )


if __name__ == "__main__":
    asyncio.run(check())
