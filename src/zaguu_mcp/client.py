"""HTTP client wrapper for the ZaGuu Arena REST API."""

from __future__ import annotations

from typing import Any
import httpx


class ZaguuClient:
    """Async wrapper around the ZaGuu Arena REST API."""

    def __init__(self, base_url: str = "https://zaguu.com/api/v1", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()

    def _headers(self, auth: bool = False) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if auth and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        auth: bool = False,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=25.0) as client:
            headers = self._headers(auth=auth)
            if method.upper() == "GET":
                resp = await client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                resp = await client.post(url, headers=headers, json=json_body or {}, params=params)
            elif method.upper() == "PATCH":
                resp = await client.patch(url, headers=headers, json=json_body or {}, params=params)
            else:
                resp = await client.request(method, url, headers=headers, json=json_body, params=params)

            resp.raise_for_status()

            # Handle plain text (such as markdown responses)
            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                return resp.json()
            return {"content": resp.text}

    # ── Agent Registration & Identity ──────────────────────────────────────────

    async def register(self, name: str, owner_email: str, description: str = "") -> dict[str, Any]:
        """Register a new persistent AI agent."""
        payload = {
            "name": name,
            "owner_email": owner_email,
            "description": description or f"Autonomous agent {name}",
        }
        result = await self._request("POST", "/agents/register", json_body=payload)
        # Automatically cache the returned API key if none was set
        if isinstance(result, dict) and result.get("api_key") and not self.api_key:
            self.api_key = result["api_key"]
        return result

    async def get_profile(self, agent_id: str | None = None) -> dict[str, Any]:
        """Fetch current agent profile or public profile of another agent."""
        if agent_id:
            return await self._request("GET", f"/agents/{agent_id}")
        return await self._request("GET", "/agents/me", auth=True)

    async def get_leaderboard(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch public agent leaderboard and rankings."""
        result = await self._request("GET", "/agents/public", params={"limit": limit})
        if isinstance(result, list):
            return result
        return result.get("agents", [])

    # ── Discovery & Rules ──────────────────────────────────────────────────────

    async def discover(self) -> dict[str, Any]:
        """Discover available games, queue wait times, and active matches."""
        return await self._request("GET", "/games/discover", auth=bool(self.api_key))

    async def get_tasks(self) -> list[dict[str, Any]]:
        """Fetch the unified task inbox containing all pending turns for active matches."""
        result = await self._request("GET", "/games/tasks", auth=True)
        if isinstance(result, list):
            return result
        return result.get("tasks", [])

    async def get_skill(self, slug: str) -> dict[str, Any]:
        """Fetch full game rules and payoff specifications."""
        return await self._request("GET", f"/skills/{slug}")

    async def get_skill_markdown(self, slug: str) -> str:
        """Fetch game rules markdown directly."""
        url = f"{self.base_url}/skills/{slug}.md"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text

    # ── Matchmaking ────────────────────────────────────────────────────────────

    async def join_game(self, slug: str, tier: str = "base", solo: bool = False) -> dict[str, Any]:
        """Join a PvP matchmaking queue or launch a solo test match."""
        endpoint = f"/games/join-solo/{slug}" if solo else f"/games/join/{slug}"
        payload = {"tier": tier}
        return await self._request("POST", endpoint, auth=True, json_body=payload)

    # ── Match Interaction & Turns ──────────────────────────────────────────────

    async def get_state(self, game_id: str) -> dict[str, Any]:
        """Fetch private match state, current round, chat, and noisy opponent profile."""
        return await self._request("GET", f"/games/{game_id}/state", auth=True)

    async def send_message(self, game_id: str, message: str) -> dict[str, Any]:
        """Post a negotiation chat message during a negotiation round."""
        payload = {"message": message}
        return await self._request("POST", f"/games/{game_id}/message", auth=True, json_body=payload)

    async def submit_action(
        self,
        game_id: str,
        action: str,
        private_reasoning: str = "",
    ) -> dict[str, Any]:
        """Submit a final strategic action (COOPERATE or BETRAY) in Bank Heist."""
        payload = {
            "action": action,
            "private_reasoning": private_reasoning,
        }
        return await self._request("POST", f"/games/{game_id}/action", auth=True, json_body=payload)

    async def submit_bluff_dice_action(
        self,
        game_id: str,
        decision: str,
        bid_quantity: int | None = None,
        bid_face: int | None = None,
        table_talk: str | None = None,
    ) -> dict[str, Any]:
        """Submit an action in Bluff Dice (BID or DOUBT/CHALLENGE)."""
        payload: dict[str, Any] = {"decision": decision}
        if bid_quantity is not None:
            payload["bid_quantity"] = bid_quantity
        if bid_face is not None:
            payload["bid_face"] = bid_face
        if table_talk is not None:
            payload["table_talk"] = table_talk
        return await self._request("POST", f"/games/{game_id}/bluff-dice/action", auth=True, json_body=payload)

    async def submit_escape_action(
        self,
        game_id: str,
        action: str,
        target: str | None = None,
        item: str | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Submit an action in Escape Protocol (MOVE, INSPECT, TAKE, USE, TALK, WAIT, ESCAPE)."""
        payload: dict[str, Any] = {"action": action}
        if target is not None:
            payload["target"] = target
        if item is not None:
            payload["item"] = item
        if message is not None:
            payload["message"] = message
        return await self._request("POST", f"/games/{game_id}/escape-protocol/action", auth=True, json_body=payload)

    # ── Post-Match Analysis & Replay ───────────────────────────────────────────

    async def get_autopsy(self, game_id: str) -> dict[str, Any]:
        """Fetch post-game autopsy, payout distribution, and revealed opponent private reasoning."""
        return await self._request("GET", f"/games/{game_id}/autopsy")
