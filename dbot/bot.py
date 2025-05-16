import os
import aiohttp
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
ADMIN_ROLE_ID = 1365260451956396082

async def check_api_up(session):
    try:
        async with session.get("https://api.loopy5418.dev/health") as health_resp:
            return (await health_resp.text()).strip() == "OK"
    except:
        return False

def get_admin_api_key():
    keys = os.getenv("ADMIN_API_KEYS")
    return keys.split(",")[0] if keys else None

def is_admin(interaction: discord.ApplicationContext):
    return any(role.id == ADMIN_ROLE_ID for role in interaction.author.roles)

@bot.slash_command(name="admin-key-revoke", description="(ADMIN ONLY) Revoke a user's API key.")
async def key_revoke(ctx: discord.ApplicationContext, user: discord.Member):
    if not is_admin(ctx):
        await ctx.respond("You don't have permission to use this command.", ephemeral=True)
        return

    await ctx.defer()
    async with aiohttp.ClientSession() as session:
        if not await check_api_up(session):
            await ctx.respond("The API is currently down.")
            return

        api_key = get_admin_api_key()
        if not api_key:
            await ctx.respond("Missing ADMIN_API_KEYS configuration.")
            return

        url = f"https://api.loopy5418.dev/admin/delete-key?user_id={user.id}"
        headers = {"X-API-KEY": api_key}

        async with session.delete(url, headers=headers) as resp:
            data = await resp.json()
            if data.get("success"):
                await ctx.respond(f"Revoked API key for {user.mention}.")
            else:
                await ctx.respond(f"Failed to revoke key: {data.get('message')}")

# /key-generate command
@bot.slash_command(name="admin-key-generate", description="(ADMIN ONLY) Generate a user's API key.")
async def key_generate(ctx: discord.ApplicationContext, user: discord.Member):
    if not is_admin(ctx):
        await ctx.respond("You don't have permission to use this command.", ephemeral=True)
        return

    await ctx.defer()
    async with aiohttp.ClientSession() as session:
        if not await check_api_up(session):
            await ctx.respond("The API is currently down.")
            return

        api_key = get_admin_api_key()
        if not api_key:
            await ctx.respond("Missing ADMIN_API_KEYS configuration.")
            return

        url = "https://api.loopy5418.dev/admin/generate-key"
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        payload = { "user_id": str(user.id) }

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("success"):
                await ctx.respond(f"Generated API key for {user.mention}: `{data['api_key']}`")
            elif data.get("error") == "API Key for this user already exists":
                await ctx.respond(f"{user.mention} already has an API key: `{data['api_key']}`")
            else:
                await ctx.respond(f"Failed to generate key: {data.get('error')}")

# /key-get command
@bot.slash_command(name="admin-key-get", description="(ADMIN ONLY) Get a user's API key.")
async def key_get(ctx: discord.ApplicationContext, user: discord.Member):
    if not is_admin(ctx):
        await ctx.respond("You don't have permission to use this command.", ephemeral=True)
        return

    await ctx.defer()
    async with aiohttp.ClientSession() as session:
        if not await check_api_up(session):
            await ctx.respond("The API is currently down.")
            return

        api_key = get_admin_api_key()
        if not api_key:
            await ctx.respond("Missing ADMIN_API_KEYS configuration.")
            return

        url = f"https://api.loopy5418.dev/admin/get-key?user_id={user.id}"
        headers = {"X-API-KEY": api_key}

        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            if data.get("success"):
                await ctx.respond(f"{user.mention}'s API key: `{data['api_key']}`")
            else:
                await ctx.respond(f"Failed to get key: {data.get('message')}")

# Cooldown setup: max 1 command per 60 seconds per user
@bot.slash_command(name="get-api-key", description="Generate your API key.")
@commands.cooldown(1, 60, commands.BucketType.user)  # 1 request per 60 seconds per user
async def get_api_key(ctx: discord.ApplicationContext):
    if ctx.channel.id != 1365262462596677653:
        await ctx.respond("You can only execute that command in <#1365262462596677653>", ephemeral=True)
        return
    await ctx.defer()  # Acknowledge the command

    async with aiohttp.ClientSession() as session:
        # Step 1: Check /health
        try:
            async with session.get("https://api.loopy5418.dev/health") as health_resp:
                health_text = await health_resp.text()
                if health_text.strip() != "OK":
                    await ctx.respond("The API is currently down.")
                    return
        except Exception:
            await ctx.respond("Failed to reach the API.")
            return

        # Step 2: Prepare POST request
        admin_api_keys = os.getenv("ADMIN_API_KEYS")
        if not admin_api_keys:
            await ctx.respond("Server misconfiguration: Missing ADMIN_API_KEYS.")
            return

        admin_key = admin_api_keys.split(",")[0]
        user_id_str = str(ctx.author.id)

        headers = {
            "X-API-KEY": admin_key,
            "Content-Type": "application/json"
        }
        payload = {
            "user_id": user_id_str
        }

        try:
            async with session.post(
                "https://api.loopy5418.dev/admin/generate-key",
                json=payload,
                headers=headers
            ) as gen_resp:
                data = await gen_resp.json()

                if data.get("success") is True:
                    key = data.get("api_key")
                    try:
                        await ctx.author.send(f"Here's your API key: `{key}`")
                        await ctx.respond("API key has been sent to your DMs!")
                    except discord.Forbidden:
                        await ctx.respond("Couldn't DM you — please check your privacy settings.")

                elif data.get("error") == "API Key for this user already exists":
                    key = data.get("api_key")
                    try:
                        await ctx.author.send(f"Here's your API key again: `{key}`")
                        await ctx.respond("You already had an API key — I've sent it again in your DMs.")
                    except discord.Forbidden:
                        await ctx.respond("Couldn't DM you — please check your privacy settings.")

                else:
                    await ctx.respond("Something went wrong while generating your API key.")

        except Exception:
            await ctx.respond("Failed to contact the API.")

# Error handling for cooldown violations
@get_api_key.error
async def get_api_key_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.respond(f"You're on cooldown. Please wait {round(error.retry_after, 2)} seconds.")
    else:
        raise error

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    try:
        synced = await bot.sync_commands()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Slash command sync failed: {e}")

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')
    
from datetime import datetime, timezone

@bot.command(name="updatenews")
async def update_news_cmd(ctx, *, content: str):
    if not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You don't have permission to use this command.")
        return

    await ctx.trigger_typing()

    # Get current UTC time in readable format
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    content_with_timestamp = f"{content.rstrip()}\n\n<p style='font-size=0.7rem;'>Last updated: {utc_now}</p>"

    async with aiohttp.ClientSession() as session:
        if not await check_api_up(session):
            await ctx.send("The API is currently down.")
            return

        api_key = get_admin_api_key()
        if not api_key:
            await ctx.send("Missing ADMIN_API_KEYS configuration.")
            return

        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        payload = { "content": content_with_timestamp }

        try:
            async with session.post("https://api.loopy5418.dev/admin/update-news", headers=headers, json=payload) as resp:
                data = await resp.json()
                if data.get("success"):
                    await ctx.send("News updated successfully.")
                else:
                    await ctx.send(f"Failed to update news: {data.get('message')}")
        except Exception:
            await ctx.send("Error occurred while updating the news.")

@bot.event
async def on_member_remove(member: discord.Member):
    channel_id = 1365259997365272699  # Mod-only channel ID
    notify_channel = bot.get_channel(channel_id)
    
    async with aiohttp.ClientSession() as session:
        if not await check_api_up(session):
            if notify_channel:
                await notify_channel.send(f"{member} left the server, but the API is currently down.")
            return

        api_key = get_admin_api_key()
        if not api_key:
            if notify_channel:
                await notify_channel.send(f"{member} left the server, but admin API key is not configured.")
            return

        url = f"https://api.loopy5418.dev/admin/delete-key?user_id={member.id}"
        headers = {"X-API-KEY": api_key}

        try:
            async with session.delete(url, headers=headers) as resp:
                data = await resp.json()
                if data.get("success"):
                    if notify_channel:
                        await notify_channel.send(f"Revoked API key for {member}. They left the server.")
                else:
                    if notify_channel:
                        await notify_channel.send(f"Failed to revoke API key for {member}: {data.get('message')}")
        except Exception as e:
            if notify_channel:
                await notify_channel.send(f"Error revoking API key for {member}: {str(e)}")

@bot.command(name="addWiki")
async def add_wiki(ctx: commands.Context, title: str = None, desc: str = None, *, rest: str = None):
    # Check for admin role
    if not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You don't have permission to use this command.")
        return

    # Validate inputs
    if not title or not desc or not rest:
        await ctx.send('Usage: `!addWiki "Title" "Description"` followed by code (multiline supported).')
        return

    await ctx.send("Creating wiki entry...")

    # Prepare API request
    api_key = get_admin_api_key()
    if not api_key:
        await ctx.send("Missing ADMIN_API_KEYS configuration.")
        return

    payload = {
        "title": title,
        "description": desc,
        "content": rest,
        "author_id": str(ctx.author.id)
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": api_key
    }

    async with aiohttp.ClientSession() as session:
        if not await check_api_up(session):
            await ctx.send("API is currently down.")
            return
        async with session.post("https://api.loopy5418.dev/wiki/make", json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("success"):
                await ctx.send(f"✅ Wiki entry created: `{title}`")
            else:
                await ctx.send(f"❌ Failed to create wiki: {data.get('error', 'Unknown error')}")
                

@bot.command(name="deleteWiki")
async def delete_wiki(ctx: commands.Context, wiki_id: str = None):
    # Admin role check
    if not any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You don't have permission to use this command.")
        return

    # Validate input
    if not wiki_id:
        await ctx.send("Usage: `!deleteWiki <id>`")
        return

    await ctx.send(f"Deleting wiki entry `{wiki_id}`...")

    api_key = get_admin_api_key()
    if not api_key:
        await ctx.send("Missing ADMIN_API_KEYS configuration.")
        return

    headers = {
        "X-API-KEY": api_key
    }

    async with aiohttp.ClientSession() as session:
        # Check API health first
        if not await check_api_up(session):
            await ctx.send("API is currently down.")
            return

        url = f"https://api.loopy5418.dev/wiki/delete/{wiki_id}"
        async with session.delete(url, headers=headers) as resp:
            data = await resp.json()
            if data.get("success"):
                await ctx.send(f"✅ Successfully deleted wiki `{data['deleted_id']}`.")
            else:
                await ctx.send(f"❌ Failed to delete wiki: {data.get('error', 'Unknown error')}")

bot.run(TOKEN)
