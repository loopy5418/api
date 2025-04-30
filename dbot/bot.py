import discord
from discord.ext import commands
import requests
import os

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!!', intents=intents)

@bot.command()
async def getkey(ctx):
    user_id = str(ctx.author.id)
    try:
        res = requests.post("Change this", json={"user_id": user_id})
        api_key = res.json().get("api_key")
        await ctx.send(f"Your API key is:\n```{api_key}```")
    except Exception as e:
        await ctx.send("There was an error fetching your API key.")

def run_bot():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN not found in environment variables")
    bot.run(token)
    
if __name__ == "__main__":
    run_bot()
