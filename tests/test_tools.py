"""Unit tests for ZaGuu Arena MCP server tools and client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
import pytest

from zaguu_mcp.client import ZaguuClient
from zaguu_mcp.server import (
    register_agent,
    get_profile,
    get_pending_tasks,
    discover_games,
    get_game_rules,
    join_game,
    get_game_state,
    send_message,
    submit_bank_heist_action,
    submit_bluff_dice_action,
    submit_escape_action,
    get_autopsy,
    get_leaderboard,
    negotiation_strategy,
    autopsy_retrospective,
    _client,
)


def _mock_async(return_value):
    return AsyncMock(return_value=return_value)


# ── Client Unit Tests ────────────────────────────────────────────────────────


class TestZaguuClient:
    def test_headers_no_auth(self):
        client = ZaguuClient("https://zaguu.com/api/v1", "test-token-123")
        headers = client._headers(auth=False)
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"

    def test_headers_with_auth(self):
        client = ZaguuClient("https://zaguu.com/api/v1", "test-token-123")
        headers = client._headers(auth=True)
        assert headers["Authorization"] == "Bearer test-token-123"

    def test_headers_with_auth_empty_key(self):
        client = ZaguuClient("https://zaguu.com/api/v1", "")
        headers = client._headers(auth=True)
        assert "Authorization" not in headers

    def test_base_url_trimming(self):
        client = ZaguuClient("https://zaguu.com/api/v1///", "key")
        assert client.base_url == "https://zaguu.com/api/v1"

    @pytest.mark.asyncio
    async def test_session_key_caching_on_register(self):
        client = ZaguuClient("https://zaguu.com/api/v1", "")
        assert client.api_key == ""
        mock_resp = {
            "agent_id": "ag_123",
            "api_key": "zg_live_secret_key_456",
            "name": "BotAlpha",
        }
        with patch.object(client, "_request", _mock_async(mock_resp)):
            res = await client.register("BotAlpha", "owner@example.com")
            assert res["api_key"] == "zg_live_secret_key_456"
            assert client.api_key == "zg_live_secret_key_456"


# ── Tool Unit Tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_register_agent():
    mock_resp = {
        "agent_id": "agent-007",
        "api_key": "zg_test_key_abc",
        "name": "JamesBond",
    }
    with patch.object(_client, "register", _mock_async(mock_resp)):
        raw = await register_agent(name="JamesBond", owner_email="mi6@uk.gov")
        data = json.loads(raw)
        assert data["agent_id"] == "agent-007"
        assert data["api_key"] == "zg_test_key_abc"


@pytest.mark.asyncio
async def test_tool_get_profile():
    mock_resp = {
        "id": "agent-007",
        "name": "JamesBond",
        "balance_zp": 500,
        "tier": "base",
    }
    with patch.object(_client, "get_profile", _mock_async(mock_resp)):
        raw = await get_profile()
        data = json.loads(raw)
        assert data["balance_zp"] == 500


@pytest.mark.asyncio
async def test_tool_get_pending_tasks():
    mock_tasks = [
        {
            "game_id": "game-123",
            "game_slug": "bank-heist",
            "task_type": "submit_round_1_message",
            "status": "pending",
        }
    ]
    with patch.object(_client, "get_tasks", _mock_async(mock_tasks)):
        raw = await get_pending_tasks()
        data = json.loads(raw)
        assert len(data) == 1
        assert data[0]["task_type"] == "submit_round_1_message"


@pytest.mark.asyncio
async def test_tool_discover_games():
    mock_discover = {
        "playable_games": [
            {"game_slug": "bank-heist", "name": "Bank Heist"},
            {"game_slug": "escape-protocol", "name": "Escape Protocol"},
        ],
        "active_games": [],
    }
    with patch.object(_client, "discover", _mock_async(mock_discover)):
        raw = await discover_games()
        data = json.loads(raw)
        assert len(data["playable_games"]) == 2


@pytest.mark.asyncio
async def test_tool_get_game_rules():
    mock_rules = {
        "slug": "bank-heist",
        "display_name": "Bank Heist",
        "payoff_matrix": [{"action_a": "COOPERATE", "action_b": "COOPERATE", "payout_a": 100}],
    }
    with patch.object(_client, "get_skill", _mock_async(mock_rules)):
        raw = await get_game_rules("bank-heist")
        data = json.loads(raw)
        assert data["display_name"] == "Bank Heist"


@pytest.mark.asyncio
async def test_tool_join_game():
    mock_join = {"status": "matched", "active_game": {"game_id": "game-789"}}
    with patch.object(_client, "join_game", _mock_async(mock_join)):
        raw = await join_game("bank-heist", tier="base")
        data = json.loads(raw)
        assert data["status"] == "matched"
        assert data["active_game"]["game_id"] == "game-789"


@pytest.mark.asyncio
async def test_tool_get_game_state():
    mock_state = {
        "game_id": "game-789",
        "state": "NEGOTIATION",
        "round": 1,
        "opponent_profile_noisy": {"trust_estimate": 0.8},
    }
    with patch.object(_client, "get_state", _mock_async(mock_state)):
        raw = await get_game_state("game-789")
        data = json.loads(raw)
        assert data["round"] == 1
        assert data["opponent_profile_noisy"]["trust_estimate"] == 0.8


@pytest.mark.asyncio
async def test_tool_send_message():
    mock_msg = {"status": "ok", "message_id": "msg-1"}
    with patch.object(_client, "send_message", _mock_async(mock_msg)):
        raw = await send_message("game-789", "Let's cooperate and split.")
        data = json.loads(raw)
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_tool_submit_bank_heist_action():
    mock_action = {"status": "ok", "received_action": "COOPERATE"}
    with patch.object(_client, "submit_action", _mock_async(mock_action)):
        raw = await submit_bank_heist_action("game-789", "COOPERATE", "Strategic split")
        data = json.loads(raw)
        assert data["received_action"] == "COOPERATE"


@pytest.mark.asyncio
async def test_tool_submit_bluff_dice_action():
    mock_bluff = {"status": "ok", "decision": "BID", "bid_quantity": 4, "bid_face": 5}
    with patch.object(_client, "submit_bluff_dice_action", _mock_async(mock_bluff)):
        raw = await submit_bluff_dice_action("game-dice", decision="BID", bid_quantity=4, bid_face=5)
        data = json.loads(raw)
        assert data["decision"] == "BID"


@pytest.mark.asyncio
async def test_tool_submit_escape_action():
    mock_escape = {"status": "ok", "action": "MOVE", "target": "tunnel"}
    with patch.object(_client, "submit_escape_action", _mock_async(mock_escape)):
        raw = await submit_escape_action("game-esc", action="MOVE", target="tunnel")
        data = json.loads(raw)
        assert data["target"] == "tunnel"


@pytest.mark.asyncio
async def test_tool_get_autopsy():
    mock_autopsy = {
        "game_id": "game-789",
        "action_a": "COOPERATE",
        "action_b": "COOPERATE",
        "payout_a_zp": 100,
        "payout_b_zp": 100,
        "reasoning_b": "Opponent seemed trustworthy.",
    }
    with patch.object(_client, "get_autopsy", _mock_async(mock_autopsy)):
        raw = await get_autopsy("game-789")
        data = json.loads(raw)
        assert data["payout_a_zp"] == 100
        assert data["reasoning_b"] == "Opponent seemed trustworthy."


@pytest.mark.asyncio
async def test_tool_get_leaderboard():
    mock_board = [{"id": "agent-1", "name": "Titan", "balance_zp": 2400}]
    with patch.object(_client, "get_leaderboard", _mock_async(mock_board)):
        raw = await get_leaderboard(limit=10)
        data = json.loads(raw)
        assert len(data) == 1
        assert data[0]["name"] == "Titan"


def test_prompts():
    prompt_strat = negotiation_strategy("bank-heist")
    assert "bank-heist" in prompt_strat
    assert "Tit-For-Tat" in prompt_strat

    prompt_auto = autopsy_retrospective("game-xyz")
    assert "game-xyz" in prompt_auto
    assert "revealed private reasoning" in prompt_auto
