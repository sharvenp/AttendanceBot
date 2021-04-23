import os
import time
import discord
from discord.ext import commands
from dotenv import load_dotenv
from pymongo import MongoClient

"""

ATTENDANCE BOT 

this bot will take a roll call at a given time and users can respond with
!here to be marked as present

if conditions are met, the user may be given additional points [TBD]

DATABASE SCHEMEA

we have one collection for each server, 
each document in the server holds the userid, points, last entry, and streak of a user

"""


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

@bot.command(name='here')
async def add_points(ctx):
    user = ctx.author.id
    server = ctx.guild.id
    increase = 1
    curr_time = time.time()
    collection = db[str(server)]
    # check if this user has a streak
    # if so points go up based on that streak
    doc = collection.find_one({"user":user})
    if doc and 'streak' in doc:
        if abs(curr_time - doc["last_update"]) < 86400: # number of seconds in a day
            increase *= doc['streak'] + 1

    collection.update_one({"user":user}, {"$inc": {'points' : increase, 'streak' : 1}, "$set" : {"last_update" : time.time()}}, upsert=True)
    await ctx.send(f'thank you for coming {ctx.author.name}!')

@bot.command(name='points')
async def echo_points(ctx):
    user = ctx.author.id
    server = ctx.guild.id
    collection = db[str(server)]
    document = collection.find_one({"user":user})
    await ctx.send(f'Hello {ctx.author.name}, you have {document["points"]} points and a streak of {document["streak"]}!')


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