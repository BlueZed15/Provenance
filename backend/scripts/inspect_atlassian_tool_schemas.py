import asyncio
import json

from backend.app.services.mistral.connectors import MistralConnectorClient


READ_TOOLS = {
    "getAccessibleAtlassianResources",
    "getJiraIssue",
    "searchJiraIssuesUsingJql",
    "getConfluencePage",
    "searchConfluenceUsingCql",
}


async def inspect() -> None:
    tools = await MistralConnectorClient().list_tools()
    selected = {tool.name: tool for tool in tools if tool.name in READ_TOOLS}
    missing = READ_TOOLS - selected.keys()
    if missing:
        raise RuntimeError(f"Missing required read tools: {sorted(missing)}")

    for name in sorted(selected):
        print(f"tool={name}")
        print(json.dumps(selected[name].input_schema, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(inspect())
