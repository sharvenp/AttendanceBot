import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

bot = commands.Bot(command_prefix='!')

connection = MongoClient(os.getenv('DB_URL'))
db = connection['discordBot']
debug = db['debug']


@bot.event
async def on_ready():
    print(f'{bot.user} has connect Discord!')

@bot.event
async def on_message(message):
    await bot.process_commands(message)

@bot.command(name='echo')
async def echo_ctx(ctx):
    user = ctx.author.id
    server = ctx.guild.id
    debug.update_one({"$and": [{"user": user}, {"server":server}]}, {"$inc": {'echos' : 1}}, upsert=True)
    await ctx.send(f'hello {ctx.author.id} from server {ctx.guild}! you sent {ctx.message.clean_content}')



bot.run(TOKEN)
# client = discord.Client()

# @client.event
# async def on_ready():
#     print(f'{client.user} has connected to Discord!')

# @client.event
# async def on_message(message):
#     if message.author == client.user:
#         return

#     await message.channel.send("Hello! " + message.author.name)

# client.run(TOKEN)