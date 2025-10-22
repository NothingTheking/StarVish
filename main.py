import discord
from discord.ext import commands
import json
import asyncio
import aiohttp

CONFIG_FILE = "config.json"
MEMORY_FILE = "memory.json"

# -------------------------
# Replace this with your Discord ID
OWNER_ID = 1350500152313385000 
# -------------------------

# -------------------------
# Load config
def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

config = load_config()

# -------------------------
# Load memory
def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"global_facts": []}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)

memory = load_memory()

# -------------------------
# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="-ai", intents=intents, help_command=None)
user_memory = {}
active_channel_id = config.get("channel_id")  # Load saved channel

# -------------------------
# Owner-only check
def is_owner():
    async def predicate(ctx):
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)

# -------------------------
@bot.event
async def on_ready():
    print(f"Subscribe to NothingTheKing!!")
    print(f"Logged in as {bot.user}!!")

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="I Am Ai"),
        status=discord.Status.idle
    )

# -------------------------
# Commands

@bot.command(name="setup")
@is_owner()
async def setup(ctx):
    global active_channel_id
    active_channel_id = ctx.channel.id
    config["channel_id"] = active_channel_id
    save_config(config)
    await ctx.send(f"✅ | This is now the active channel for chatting with the bot: <#{active_channel_id}>")

@bot.command(name="unsetup")
@is_owner()
async def unsetup(ctx):
    global active_channel_id
    if "channel_id" in config:
        removed_channel = config.pop("channel_id", None)
        save_config(config)
        active_channel_id = None
        await ctx.send(f"✅ | Channel setup removed: <#{removed_channel}>")
    else:
        await ctx.send("⚠️ | No setup channel found to remove.")

@bot.command(name="help")
@is_owner()
async def custom_help(ctx):
    help_text = "🤖 __**AI BOT CMDS :**__\n" \
                "> **`-aisetup`** - setup bot in a channel\n" \
                "> **`-aiunsetup`** - remove setup channel\n" \
                "> **`-aiclearmemory`** - clear user memory\n" \
                "> **`-aimemoryadd <fact>`** - add fact to bot memory\n" \
                "> **`-aihelp`** - show this help message"
    await ctx.send(help_text)

@bot.command(name="clearmemory")
@is_owner()
async def clear_memory(ctx):
    user_id = str(ctx.author.id)
    if user_id in user_memory:
        del user_memory[user_id]
    await ctx.send("🧠 | Your memory has been cleared!")

# Owner-only memory add command
@bot.command(name="memoryadd")
@is_owner()  # Only the OWNER_ID can run this
async def memory_add(ctx, *, fact):
    # Ensure memory file has global_facts list
    memory.setdefault("global_facts", [])
    
    # Add the new fact
    memory["global_facts"].append({"role": "system", "content": fact})
    
    # Save to memory.json so it persists
    save_memory(memory)
    
    await ctx.send(f"✅ | Added to memory: `{fact}`")

# -------------------------
@bot.event
async def on_message(message):
    global active_channel_id

    if message.author.bot:
        return

    await bot.process_commands(message)

    # Only respond in the designated channel
    if active_channel_id is None or message.channel.id != active_channel_id:
        return

    # Ignore messages starting with command prefix
    if message.content.startswith("-ai"):
        return

    await message.channel.typing()

    user_id = str(message.author.id)
    user_memory.setdefault(user_id, [])
    user_memory[user_id].append({"role": "user", "content": message.content})

    messages = memory.get("global_facts", []) + [{"role": "system", "content": config["system_context"]}] + user_memory[user_id]

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": config["model"],
                "messages": messages
            }
            async with session.post(f"{config['api_base']}/chat/completions", headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_detail = await resp.text()
                    print(f"[API ERROR] {resp.status}: {error_detail}")
                    await message.reply(config.get("error_message", "❌ | API Error, try again later."))
                    return
                response = await resp.json()
                reply = response["choices"][0]["message"]["content"]
                user_memory[user_id].append({"role": "assistant", "content": reply})
                await message.reply(reply)
    except Exception as e:
        await message.reply(config.get("error_message", "⚠️ | Internal error occurred."))
        print(f"[ERROR] {e}")

# -------------------------
bot.run(config["token"])
