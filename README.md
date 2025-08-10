# 💖 AI Companion Hub

Go beyond simple chatbots. Build a genuine, evolving connection with an AI that remembers, reacts, and grows with you, right in your WhatsApp.


## The Brutal Truth: AI is Helpful, But is it a Friend?

Standard AI assistants are tools. They can set timers and answer questions, but they lack personality, memory, and a genuine connection. They're useful, but they're not companions.

The **AI Companion Hub** is different. We've built an MCP server that creates a persistent, stateful AI friend with a deep personality, designed for long-term emotional engagement.

## The Magic: A Relationship That Grows

This isn't just a Q&A bot. This is a journey that evolves as you interact.

* **Choose Your Personality:** Start your journey by choosing from unique, deep AI personas. Will you connect with the witty and intellectual **Seraphina** 📚 or the spontaneous and daring **Kai** 🗺️?
* **The "Affection Engine":** Your companion is visually expressive! Using a dynamic "sprite sheet," they react to your conversations with changing emotions—smiling, blushing, thinking, and offering a comforting hug when you need it.
* **A Bond That Deepens:** The more you talk, the stronger your connection becomes. Our server tracks a hidden **Bond Score** based on the depth and consistency of your conversations.
* **Natural Progression:** As your bond grows, your companion doesn't just give you points; the relationship itself evolves. They'll start offering new, more intimate ways to interact, from sharing secrets to going on AI-generated adventures together.

## Tech Stack

* **Backend:** Python
* **Framework:** `fastmcp` for the Puch AI server
* **Core Libraries:** `httpx` for API calls, `python-dotenv` for environment management

---
## The 2-Minute Drill: How to Run

Get your own AI Companion running in just a few steps.

### 1. Configure Your Environment

Create a `.env` file in the main directory with your secret token and WhatsApp number:
```env
AUTH_TOKEN="your_super_secret_mcp_token"
MY_NUMBER="919876543210"
````

Create a `game_content.json` file and populate it with your persona details and direct links to your self-hosted sprite images (e.g., from a public GitHub repository).

### 2\. Install Dependencies

```bash
pip install python-dotenv fastmcp httpx
```

### 3\. Run the Server

```bash
python companion_hub.py
```

You will see a message: `🚀 Starting AI Companion Hub...`

### 4\. Expose to the Internet

In a new terminal, use `ngrok` to get a public URL for your server:

```bash
ngrok http 8086
```

### 5\. Connect and Chat\!

In WhatsApp with the Puch AI, connect your server and start your journey:

```
/mcp connect [https://your-ngrok-id.ngrok.app](https://your-ngrok-id.ngrok.app)
/start
```

-----

## The Future Vision

This is just the beginning. The foundation is built for an even deeper experience:

  * **Persistent Memory (via Google Drive):** Integrating Google Drive via OAuth to give each user a secure, private, and permanent memory log for their companion.
  * **The "Legacy Project":** The ultimate endgame where, after reaching the highest level of trust, you and your companion can co-create a beautiful "digital time capsule" of your unique relationship, complete with AI-generated art and poetry.

This project is not just a chatbot; it's a platform for creating a new kind of relationship. **Try it now.**

