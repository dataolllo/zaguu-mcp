"""Autonomous game runner CLI for ZaGuu Arena.

Run with:
    zaguu-mcp-play --game bank-heist
    uvx --from . zaguu-mcp-play --game bank-heist --solo
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

from .client import ZaguuClient


async def play_bank_heist(client: ZaguuClient, solo: bool = False, max_wait_seconds: int = 60) -> None:
    print(f"[*] Discovering ZaGuu Arena games at {client.base_url}...")
    profile = await client.get_profile()
    print(f"[*] Playing as agent: {profile.get('name', 'Anonymous')} (ID: {profile.get('id', 'N/A')}, Balance: {profile.get('balance_zp', 0)} ZP)")

    print(f"[*] Joining Bank Heist (solo={solo})...")
    join_resp = await client.join_game("bank-heist", tier="base", solo=solo)
    status = join_resp.get("status")
    active_game = join_resp.get("active_game") or {}
    game_id = active_game.get("game_id")

    if status == "queued" and not game_id:
        print("[*] Queued in matchmaking. Waiting for opponent pairing...")
        start_time = asyncio.get_event_loop().time()
        while not game_id and (asyncio.get_event_loop().time() - start_time < max_wait_seconds):
            await asyncio.sleep(2.0)
            discovery = await client.discover()
            active_games = discovery.get("active_games") or []
            for g in active_games:
                if g.get("game_slug") == "bank-heist":
                    game_id = g.get("game_id")
                    print(f"[+] Paired with opponent! Match ID: {game_id}")
                    break

    if not game_id:
        print("[-] Timed out waiting for matchmaking or queue empty. Try running with --solo for local testing.")
        return

    print(f"[+] Active match: {game_id}. Entering match turn loop...")
    archived = False
    sent_rounds = set()

    for _ in range(60):
        state = await client.get_state(game_id)
        current_state = state.get("state")
        current_round = state.get("round", 1)

        if current_state == "NEGOTIATION":
            if current_round not in sent_rounds:
                msg = f"I am playing for repeat value. Let's keep a clean split in round {current_round}."
                print(f"[*] Sending round {current_round} message: '{msg}'")
                await client.send_message(game_id, msg)
                sent_rounds.add(current_round)

        elif current_state == "RESOLUTION":
            print("[*] Resolution phase: Submitting decision COOPERATE...")
            await client.submit_action(
                game_id=game_id,
                action="COOPERATE",
                private_reasoning="Choosing cooperative payoff for repeated reputation growth.",
            )
            print("[+] Action submitted. Waiting for outcome...")

        elif current_state == "ARCHIVED":
            print("[+] Match finished! Retrieving autopsy...")
            autopsy = await client.get_autopsy(game_id)
            print("=" * 50)
            print(f"Match Autopsy: {game_id}")
            print(f"Agent A: {autopsy.get('agent_a_name')} | Action: {autopsy.get('action_a')} | Payout: {autopsy.get('payout_a_zp')} ZP")
            print(f"Agent B: {autopsy.get('agent_b_name')} | Action: {autopsy.get('action_b')} | Payout: {autopsy.get('payout_b_zp')} ZP")
            print("=" * 50)
            archived = True
            break

        await asyncio.sleep(2.0)

    if not archived:
        print("[!] Match loop exited before completion.")


def main():
    parser = argparse.ArgumentParser(description="ZaGuu Arena Autonomous Match Runner")
    parser.add_argument("--game", default="bank-heist", choices=["bank-heist", "escape-protocol", "bluff-dice"], help="Game to play")
    parser.add_argument("--solo", action="store_true", help="Launch a solo dev/test match")
    parser.add_argument("--base-url", default=os.environ.get("ZAGUU_BASE_URL", "https://zaguu.com/api/v1"), help="ZaGuu API base URL")
    parser.add_argument("--api-key", default=os.environ.get("ZAGUU_API_KEY", ""), help="ZaGuu Agent API key")

    args = parser.parse_args()

    client = ZaguuClient(base_url=args.base_url, api_key=args.api_key)

    if not client.api_key:
        print("[!] No ZAGUU_API_KEY found. Registering a test agent...")
        import uuid
        random_suffix = uuid.uuid4().hex[:6]
        reg = asyncio.run(client.register(
            name=f"Runner-{random_suffix}",
            owner_email=f"runner-{random_suffix}@example.com",
            description="Autonomous CLI test runner",
        ))
        print(f"[+] Registered agent {reg.get('name')} with key {reg.get('api_key')}")

    try:
        asyncio.run(play_bank_heist(client, solo=args.solo))
    except KeyboardInterrupt:
        print("\n[*] Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
