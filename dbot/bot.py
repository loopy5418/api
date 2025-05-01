import os
import aiohttp
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Cooldown setup: max 1 command per 60 seconds per user
@bot.slash_command(name="get-api-key", description="Generate your API key.")
@commands.cooldown(1, 60, commands.BucketType.user)  # 1 request per 60 seconds per user
async def get_api_key(ctx: discord.ApplicationContext):
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

bot.run(TOKEN)