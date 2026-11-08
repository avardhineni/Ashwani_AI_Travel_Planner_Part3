"""Static checks without external MCP/LLM calls."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_all_main_files_parse():
    for name in ('agents.py', 'config.py', 'graph.py', 'mcp_client.py',
                 'state.py', 'frontend.py', 'weather_mcp_server.py',
                 'pdf_export.py', 'cli.py', 'guardrails/alternatives.py'):
        ast.parse((ROOT / name).read_text(encoding='utf-8'))


def test_credentials_not_in_repository():
    assert not (ROOT / '.env').exists()
    ignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
    assert '.env' in ignore
    assert 'travel_plans/' in ignore


def test_blocked_route_is_to_end():
    source = (ROOT / 'graph.py').read_text(encoding='utf-8')
    assert "if state.get('request_status') == 'blocked':" in source
    assert "return 'end'" in source
