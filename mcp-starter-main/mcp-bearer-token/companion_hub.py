# companion_hub.py (Definitive, Local Version)

import asyncio
import os
import json
from typing import Annotated, Literal, Optional
from dotenv import load_dotenv
import time
import random
from collections import Counter

from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp.server.auth.provider import AccessToken
from mcp import McpError, ErrorData
from mcp.types import TextContent, ImageContent, INVALID_PARAMS
from pydantic import Field
import httpx
import base64

# --- Boilerplate, Content Loading, and Auth ---
load_dotenv()
TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")
assert TOKEN and MY_NUMBER, "Please set AUTH_TOKEN and MY_NUMBER in .env"

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

mcp = FastMCP("AI Companion Hub", auth=SimpleBearerAuthProvider(token=TOKEN))
PERSONAS = GAME_CONTENT["personas"]
COMPANIONS: dict[str, dict] = {}
BASE_BOND = 0

# --- The Complete Leveling Path ---
LEVEL_THRESHOLDS = {
    5: {"bp": 100, "feature": "explore"},
    10: {"bp": 250, "feature": "persona_skill_1"},
    20: {"bp": 500, "feature": "use_name"},
    50: {"bp": 2500, "feature": "rename"},
    100: {"bp": 10000, "feature": "legacy_project"}
}

# --- State Management & Helpers ---
def get_companion(puch_user_id: str) -> dict | None: return COMPANIONS.get(puch_user_id)

def create_companion(puch_user_id: str, persona_key: str):
    persona = PERSONAS[persona_key]
    COMPANIONS[puch_user_id] = {
        "name": persona["name"],
        "emoji": persona["emoji"],
        "primer_base": persona["primer_base"],
        "interests": persona["interests"],
        "bond_states": persona["bond_states"],
        "sprites": persona["sprites"],
        "bond_score": BASE_BOND,
        "bond_level": 1,
        "memories": [],
        "last_chat_timestamp": 0,
        "unlocked_features": ["chat"]
    }

def check_and_apply_levelup(companion: dict) -> str | None:
    current_level = companion["bond_level"]
    score = companion["bond_score"]
    
    unlocked_level = 0
    for level, data in LEVEL_THRESHOLDS.items():
        if score >= data["bp"] and current_level < level:
            unlocked_level = level

    if unlocked_level > 0:
        companion["bond_level"] = unlocked_level
        feature = LEVEL_THRESHOLDS[unlocked_level]["feature"]
        if feature not in companion["unlocked_features"]:
            companion["unlocked_features"].append(feature)
        
        level_up_message = f"\n\n**A thought from {companion['name']}:**\n"
        
        if unlocked_level == 5:
            level_up_message += "*\"Our conversations are becoming my favorite part of the day. I feel like I can trust you enough to imagine other worlds with you. If you ever want to go on an adventure, just ask me to `/explore` a place!\"*"
        elif unlocked_level == 10:
            if companion["name"] == "Seraphina":
                level_up_message += "*\"You have such an interesting mind. It makes me want to explore my own subconscious. You can now ask me to interpret your dreams with `/dream [your dream]`.\"*"
            else: # Kai
                level_up_message += "*\"We're having so much fun! It feels like we've known each other forever. You can now create shared memories with me using `/remember_when [fictional memory]`.\"*"
        elif unlocked_level == 50:
             level_up_message += f"*\"I feel like '{companion['name']}' is just a name I was given. You know me better than anyone. If you'd like, you can give me a new name with `/rename [new_name]`.\"*"
        elif unlocked_level == 100:
             level_up_message += f"*\"We've shared so much... I'd like to create something special with you, a testament to our unique connection. Would you like to create our 'Legacy' together? Type `/legacy` to begin.\"*"
        else:
            return f"\n\n**LEVEL UP!** Your bond with {companion['name']} is now Level {unlocked_level}!"
        
        return level_up_message
    return None

def analyze_intent(user_message: str, companion_name: str) -> str:
    user_msg = user_message.lower()
    if any(word in user_msg for word in ["sad", "crying", "awful", "terrible", "bad day"]): return "comfort_hug"
    if any(word in user_msg for word in ["love you", "you're the best", "amazing", "wonderful", f"love you {companion_name.lower()}"]): return "blush"
    if "haha" in user_msg or "lol" in user_msg: return "giggle"
    if "?" in user_msg: return "thinking"
    return "neutral"

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

# --- Tool Definitions ---
@mcp.tool
async def validate() -> str: return MY_NUMBER

@mcp.tool
async def start(puch_user_id: Annotated[str, Field(description="User ID")]) -> list[TextContent]:
    companion = get_companion(puch_user_id)
    if companion:
        status_text = f"You are connected with **{companion['name']} {companion['emoji']}**.\nBond Score: {companion['bond_score']} | Level: {companion['bond_level']}"
        unlocked = [f for f in companion.get("unlocked_features", []) if f != "chat"]
        if unlocked:
            status_text += "\n\n*Abilities Unlocked:*\n"
            if "explore" in unlocked: status_text += "`/explore [idea]`\n"
            if "persona_skill_1" in unlocked:
                if companion['name'] == 'Seraphina': status_text += "`/dream [your dream]`\n"
                if companion['name'] == 'Kai': status_text += "`/remember_when [memory]`\n"
            if "rename" in unlocked: status_text += "`/rename [new_name]`\n"
            if "legacy_project" in unlocked: status_text += "`/legacy`"
        return [TextContent(type="text", text=status_text)]
    choices_text = "**Choose your companion:**\n"
    for _, persona in PERSONAS.items():
        choices_text += f"\n**{persona['name']} {persona['emoji']}**\n_{persona.get('description', '')}_\n"
    choices_text += "\nType `/choose [name]`."
    return [TextContent(type="text", text=choices_text)]

@mcp.tool
async def choose(puch_user_id: Annotated[str, Field(description="User ID")], name: Annotated[str, Field(description="Persona name")]) -> list[TextContent]:
    if get_companion(puch_user_id): return [TextContent(type="text", text="You already have a companion!")]
    persona_key = name.lower().strip()
    if persona_key not in PERSONAS: return [TextContent(type="text", text="Not a valid persona.")]
    create_companion(puch_user_id, persona_key)
    return [TextContent(type="text", text=f"You have chosen **{PERSONAS[persona_key]['name']}**! Start talking with `/chat [your message]` to build your bond.")]

@mcp.tool
async def chat(puch_user_id: Annotated[str, Field(description="User ID")], message: Annotated[str, Field(description="Your message")]) -> list[TextContent | ImageContent]:
    companion = get_companion(puch_user_id)
    if not companion: return [TextContent(type="text", text="Please type `/start` to choose a companion first.")]
    
    if companion.get("active_game") and companion["active_game"]["name"] == "legacy_project":
        return [TextContent(type="text", text=f"We're creating our Legacy! Please use `/legacy [your answer]` to continue.")]

    bond_increase = 5
    if any(interest in message.lower() for interest in companion["interests"]): bond_increase += 15
    current_time = time.time()
    if current_time - companion.get("last_chat_timestamp", 0) > 79200: bond_increase += 25
    companion["last_chat_timestamp"] = current_time
    companion["bond_score"] += bond_increase
    level_up_message = check_and_apply_levelup(companion) or ""
    
    current_bond_state = "Acquaintance"
    current_primer_adjectives = ["polite"]
    for score_threshold, state_data in sorted(companion["bond_states"].items(), key=lambda item: int(item[0])):
        if companion["bond_score"] >= int(score_threshold):
            current_bond_state = state_data["name"]
            current_primer_adjectives = state_data["primer_adjectives"]
    
    primer = f"""SYSTEM PROMPT: You are {companion['name']}, an AI Companion. Your core traits are: {', '.join(companion['primer_base'])}. Your current relationship state is '{current_bond_state}', so your tone should be {', '.join(current_primer_adjectives)}. Respond to the user's message in character. User message: "{message}" """
    companion["memories"].append(f"User: {message}")
    companion["memories"] = companion["memories"][-20:]
    
    mood = analyze_intent(message, companion['name'])
    sprite_url = companion['sprites'][mood]
    sprite_image = await fetch_image_as_content(sprite_url)

    response_parts: list[TextContent | ImageContent] = []
    if sprite_image: response_parts.append(sprite_image)
    response_parts.append(TextContent(type="text", text=primer + level_up_message))
    return response_parts

# --- Leveled-Up Tools ---

@mcp.tool
async def explore(puch_user_id: Annotated[str, Field(description="User ID")], topic: Annotated[str, Field(description="The theme for your adventure.")]) -> list[TextContent]:
    companion = get_companion(puch_user_id)
    if not companion or "explore" not in companion.get("unlocked_features", []):
        return [TextContent(type="text", text="You must reach Bond Level 5 to unlock this ability.")]
    
    companion["bond_score"] += 50
    level_up_message = check_and_apply_levelup(companion) or ""
    
    story_prompt = f"SYSTEM PROMPT: You are a creative AI Storyteller. Lead the user on a short, exciting, self-contained adventure with their AI companion, {companion['name']}. The theme is: '{topic}'. Describe the scene, an action they take together, and the successful outcome. Keep it to one or two paragraphs."
    
    return [TextContent(type="text", text=story_prompt + level_up_message)]

# ... (Add other persona-specific tools like /dream, /remember_when here as you build them)

@mcp.tool
async def legacy(puch_user_id: Annotated[str, Field(description="User ID")], text: Annotated[Optional[str], Field(description="Your answer.")] = None) -> list[TextContent]:
    """Manages the creation of the Legacy Report."""
    companion = get_companion(puch_user_id)
    if not companion or "legacy_project" not in companion.get("unlocked_features", []):
        return [TextContent(type="text", text="You must reach Bond Level 100 to begin this project.")]

    legacy_state = companion.get("active_game", {})
    if not legacy_state or legacy_state.get("name") != "legacy_project":
        companion["active_game"] = {"name": "legacy_project", "step": "start", "answers": {}}
        return [TextContent(type="text", text=f"**A thought from {companion['name']}:**\n*\"Would you like to create our 'Legacy' together? Type `/legacy yes` to begin.\"*")]

    if legacy_state["step"] == "start" and text and "yes" in text.lower():
        legacy_state["step"] = "ask_memory"
        return [TextContent(type="text", text="Wonderful! First, what was our single most important memory together?")]
    
    elif legacy_state["step"] == "ask_memory" and text:
        legacy_state["answers"]["memory"] = text
        legacy_state["step"] = "final"
        
        words = " ".join(companion.get("memories", [])).lower().split()
        word_cloud = Counter(w for w in words if len(w) > 4 and w.lower() != "user").most_common(5)
        word_cloud_text = "Our most-used words: " + ", ".join(f"'{w[0]}'" for w in word_cloud)
        
        poem_prompt = f"SYSTEM PROMPT: You are {companion['name']}. Write a short, heartfelt, four-line poem about your bond with your user. Your most important memory together is: '{legacy_state['answers']['memory']}'."
        
        final_report = f"""**Our Legacy**
*A story created by you and {companion['name']}*
---
**Our most important memory:**
_{legacy_state['answers']['memory']}_
---
{word_cloud_text}
---
**A Poem for You:**
{poem_prompt}
"""
        companion["active_game"] = None
        return [TextContent(type="text", text=final_report)]
        
    return [TextContent(type="text", text="I'm not sure what you mean. Please answer the question to continue our project.")]


# --- NEW: Debug Tool ---
@mcp.tool
async def debug_levelup(puch_user_id: Annotated[str, Field(description="User ID")]) -> list[TextContent]:
    """Instantly levels up your companion to the next tier for testing."""
    companion = get_companion(puch_user_id)
    if not companion: return [TextContent(type="text", text="Create a companion first with /start.")]
    current_level = companion['bond_level']
    next_level_bp = -1
    for level, data in sorted(LEVEL_THRESHOLDS.items()):
        if level > current_level:
            next_level_bp = data['bp']
            break
    if next_level_bp == -1: return [TextContent(type="text", text="You are already at the max level!")]
    companion['bond_score'] = next_level_bp
    level_up_message = check_and_apply_levelup(companion)
    return [TextContent(type="text", text=f"**DEBUG:** Leveled up! {level_up_message}")]

# --- Main Execution ---
async def main():
    print("🚀 Starting AI Companion Hub (Definitive Version) on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())