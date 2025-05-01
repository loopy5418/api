import os
import aiohttp
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

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

@bot.slash_command(name="get-api-key", description="Generate your API key.")
async def get_api_key(ctx: discord.ApplicationContext):
    await ctx.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://api.loopy5418.dev/health") as health_resp:
                health_text = await health_resp.text()
                if health_text.strip() != "OK":
                    await ctx.respond("The API is currently down.", ephemeral=True)
                    return
        except Exception:
            await ctx.respond("Failed to reach the API.", ephemeral=True)
            return

        admin_api_keys = os.getenv("ADMIN_API_KEYS")
        if not admin_api_keys:
            await ctx.respond("Server misconfiguration: Missing ADMIN_API_KEYS.", ephemeral=True)
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
                        await ctx.respond("API key has been sent to your DMs!", ephemeral=True)
                    except discord.Forbidden:
                        await ctx.respond("Couldn't DM you — please check your privacy settings.", ephemeral=True)

                elif data.get("error") == "API Key for this user already exists":
                    key = data.get("api_key")
                    try:
                        await ctx.author.send(f"Here's your API key again: `{key}`")
                        await ctx.respond("You already had an API key — I've sent it again in your DMs.", ephemeral=True)
                    except discord.Forbidden:
                        await ctx.respond("Couldn't DM you — please check your privacy settings.", ephemeral=True)

                else:
                    await ctx.respond("Something went wrong while generating your API key.", ephemeral=True)

        except Exception:
            await ctx.respond("Failed to contact the API.", ephemeral=True)

bot.run(TOKEN)