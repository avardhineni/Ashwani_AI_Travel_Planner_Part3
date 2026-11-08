"""MCP tool bridge. Disabled integrations return explicit errors, not dummy prices."""
from pathlib import Path
import sys
from langchain_mcp_adapters.client import MultiServerMCPClient
from config import (BASE_DIR, TAVILY_API_KEY, AVIATION_STACK_API_KEY,
                    OPENWEATHER_API_KEY, AVIATION_MCP_PYTHON, AVIATION_MCP_DIR)


def connections() -> dict:
    connections = {}
    if TAVILY_API_KEY:
        connections['tavily'] = {
            'transport': 'streamable_http',
            'url': f'https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}',
        }
    if AVIATION_STACK_API_KEY and AVIATION_MCP_PYTHON:
        python_exe = Path(AVIATION_MCP_PYTHON).expanduser()
        if not python_exe.is_file():
            raise FileNotFoundError(f'AVIATION_MCP_PYTHON does not exist: {python_exe}')
        config = {
            'transport': 'stdio',
            'command': str(python_exe),
            'args': ['-m', 'aviationstack_mcp', 'mcp', 'run'],
            'env': {'AVIATION_STACK_API_KEY': AVIATION_STACK_API_KEY},
        }
        if AVIATION_MCP_DIR:
            # Some adapter versions support cwd and others do not; use PYTHONPATH only if needed.
            config['env']['PYTHONPATH'] = AVIATION_MCP_DIR
        connections['aviationstack'] = config
    if OPENWEATHER_API_KEY:
        connections['weather'] = {
            'transport': 'stdio',
            'command': sys.executable,
            'args': [str(BASE_DIR / 'weather_mcp_server.py')],
            'env': {'OPENWEATHER_API_KEY': OPENWEATHER_API_KEY},
        }
    return connections


async def call_tool(server: str, name: str, args: dict) -> str:
    conns = connections()
    if server not in conns:
        return f'[NOT CONFIGURED] {server} integration is disabled; no verified provider data.'
    try:
        client = MultiServerMCPClient({server: conns[server]}, handle_tool_errors=False)
        tools = await client.get_tools(server_name=server)
        tool = next((tool for tool in tools if tool.name == name), None)
        if tool is None:
            return f'[MISSING TOOL] {server}.{name} not available. Actual names: {[t.name for t in tools]}'
        return str(await tool.ainvoke(args))[:6500]
    except Exception as exc:
        return f'[MCP FAILURE] {server}.{name}: {type(exc).__name__}: {exc}'[:900]

async def list_airports(city: str):
    return await call_tool('aviationstack', 'list_airports', {'search': city, 'limit': 10, 'offset': 0})

async def list_airlines():
    return await call_tool('aviationstack', 'list_airlines', {'search': '', 'limit': 10, 'offset': 0})

async def hotel_search(query: str):
    return await call_tool('tavily', 'tavily_search', {'query': query})

async def current_weather(city: str):
    return await call_tool('weather', 'get_current_weather', {'city': city})

async def forecast(city: str):
    return await call_tool('weather', 'get_forecast', {'city': city})
