# game_night_hq.py

import asyncio
import os
import json
from typing import Annotated, Literal, Optional
from dotenv import load_dotenv
import httpx
import base64

from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp.server.auth.provider import AccessToken
from mcp import McpError, ErrorData
from mcp.types import TextContent, ImageContent, INVALID_PARAMS
from pydantic import Field, BaseModel

# --- Boilerplate, Content Loading, and Auth ---
load_dotenv()
TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")
assert TOKEN and MY_NUMBER, "Please set AUTH_TOKEN and MY_NUMBER"

try:
    with open("game_content.json", "r") as f:
        GAME_CONTENT = json.load(f)
except FileNotFoundError:
    print("FATAL ERROR: game_content.json not found.")
    exit()

class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token
    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(token=token, client_id="puch-client", scopes=["*"], expires_at=None)
        return None

mcp = FastMCP("The Player's Hub", auth=SimpleBearerAuthProvider(token=TOKEN))

# --- State Management & Helpers ---
PLAYER_DATA: dict[str, dict] = {}
BASE_ELO = 1200

def get_player_data(puch_user_id: str) -> dict:
    if not puch_user_id: raise McpError(ErrorData(code=INVALID_PARAMS, message="puch_user_id is required."))
    if puch_user_id not in PLAYER_DATA:
        PLAYER_DATA[puch_user_id] = {"elo": BASE_ELO, "active_game": None, "last_rank": None}
    return PLAYER_DATA[puch_user_id]

async def fetch_image_as_content(url: str) -> ImageContent | None:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, follow_redirects=True, timeout=15)
            response.raise_for_status()
            mime_type = response.headers.get("content-type", "image/png")
            image_data = response.content
            base64_data = base64.b64encode(image_data).decode("utf-8")
            return ImageContent(type="image", mimeType=mime_type, data=base64_data)
        except httpx.HTTPError as e:
            print(f"Error fetching image from {url}: {e}")
            return None

# --- Core Hub Tools ---

@mcp.tool
async def validate() -> str: return MY_NUMBER

@mcp.tool
async def lobby(puch_user_id: Annotated[str, Field(description="Puch User ID")]) -> list[TextContent]:
    player = get_player_data(puch_user_id)
    elo_score = player.get("elo", BASE_ELO)
    
    sorted_players = sorted(PLAYER_DATA.items(), key=lambda item: item[1].get("elo", 0), reverse=True)
    current_rank = -1
    for i, (user_id, _) in enumerate(sorted_players):
        if user_id == puch_user_id:
            current_rank = i + 1
            break

    last_rank = player.get("last_rank")
    rank_text = f"Rank: #{current_rank}" if current_rank != -1 else "Unranked"
    if last_rank and current_rank != -1:
        if current_rank < last_rank: rank_text += f" (▲{last_rank - current_rank})"
        elif current_rank > last_rank: rank_text += f" (▼{current_rank - last_rank})"
    player["last_rank"] = current_rank

    menu_text = f"""**Welcome to The Player's Hub!**
Your Rating: **{elo_score} ELO** 🏆 | {rank_text}

* **/play f1**: 🏎️ Grand Prix Strategist
* **/leaderboard**: 📊 View Standings

*To play an active game, use **/action [your choice]**.*"""
    return [TextContent(type="text", text=menu_text)]
    
@mcp.tool
async def leaderboard() -> list[TextContent]:
    if not PLAYER_DATA: return [TextContent(type="text", text="The leaderboard is empty.")]
    sorted_players = sorted(PLAYER_DATA.items(), key=lambda item: item[1].get("elo", 0), reverse=True)
    leaderboard_text = "**🏆 ELO Leaderboard 🏆**\n\n"
    for i, (user_id, data) in enumerate(sorted_players[:10]):
        user_display = f"Player-{user_id[:6]}"
        score = data.get("elo", BASE_ELO)
        rank = i + 1
        emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else ""
        leaderboard_text += f"{rank}. {user_display} - {score} ELO {emoji}\n"
    return [TextContent(type="text", text=leaderboard_text)]

@mcp.tool
async def play(puch_user_id: Annotated[str, Field(description="Puch User ID")], game: Annotated[Literal["f1"], Field(description="The game to start.")]) -> list[TextContent | ImageContent]:
    player = get_player_data(puch_user_id)
    if player.get("active_game"):
        return [TextContent(type="text", text="You're already in a game! Use `/action` to play or `/endgame` to quit.")]

    if game == "f1":
        race = GAME_CONTENT["f1_races"]["monza"]
        player["active_game"] = {"name": "f1", "race_id": "monza", "step": 0, "position": 2}
        
        step_data = race["steps"][0]
        cinematic_image = await fetch_image_as_content(step_data["image_url"])
        
        scene_text = f"🏎️ Welcome to the {race['name']}!\n\n{step_data['text']}\n\n**Type `/action choices` to see your options.**"
        
        response = []
        if cinematic_image: response.append(cinematic_image)
        response.append(TextContent(type="text", text=scene_text))
        return response

@mcp.tool
async def action(puch_user_id: Annotated[str, Field(description="Puch User ID")], move: Annotated[str, Field(description="Your choice or command.")]) -> list[TextContent | ImageContent]:
    player = get_player_data(puch_user_id)
    active_game = player.get("active_game")
    if not active_game:
        return [TextContent(type="text", text="You're not in a game! Type `/play f1` to start.")]

    race = GAME_CONTENT["f1_races"][active_game["race_id"]]
    step_data = race["steps"][active_game["step"]]
    move = move.lower().strip()

    if move == "choices":
        choices_text = "\n".join([f"**[{choice['label']}]** {choice['text']}" for choice in step_data["choices"]])
        prompt_text = "Type `/action [your choice]` (e.g., /action A)"
        return [TextContent(type="text", text=f"{choices_text}\n\n{prompt_text}")]
    
    chosen_option = next((c for c in step_data["choices"] if c["label"].lower() == move), None)
    if not chosen_option:
        return [TextContent(type="text", text="That's not a valid choice right now.")]

    outcome = chosen_option["outcome"]
    response_parts: list[TextContent | ImageContent] = [TextContent(type="text", text="➡️ " + outcome["feedback"])]
    
    if "meme_url" in outcome:
        meme_image = await fetch_image_as_content(outcome["meme_url"])
        if meme_image: response_parts.append(meme_image)

    if "next_step" in outcome:
        active_game["step"] = outcome["next_step"]
        next_step_data = race["steps"][active_game["step"]]
        cinematic_image = await fetch_image_as_content(next_step_data["image_url"])
        if cinematic_image: response_parts.append(cinematic_image)
        
        scene_text = f"\n{next_step_data['text']}\n\n**Type `/action choices` to see your new options.**"
        response_parts.append(TextContent(type="text", text=scene_text))
    elif "result" in outcome:
        player["elo"] += outcome["result"]["elo_change"]
        sign = "+" if outcome["result"]["elo_change"] >= 0 else ""
        result_text = f"\n🏁 Race finished! **Rating Change: {sign}{outcome['result']['elo_change']} ELO** (New Rating: {player['elo']})"
        response_parts.append(TextContent(type="text", text=result_text))
        player["active_game"] = None
        
    return response_parts

@mcp.tool
async def endgame(puch_user_id: Annotated[str, Field(description="Puch User ID")]) -> list[TextContent]:
    player = get_player_data(puch_user_id)
    if player.get("active_game"):
        player["active_game"] = None
        return [TextContent(type="text", text="Game ended. Type `/lobby` to start a new one.")]
    return [TextContent(type="text", text="You are not in a game.")]

# --- Main Execution ---
async def main():
    print("🚀 Starting The Player's Hub - DEFINITIVE MODEL on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())