import os
import time
import discord
from discord.ext import commands
from dotenv import load_dotenv
from pymongo import MongoClient

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio

from server import stay_alive
"""

ATTENDANCE BOT 

this bot will take a roll call at a given time and users can respond with
!here to be marked as present

Each user gets streaks for attending multiple alarms in a row, increasing the amount of points they get

Users can set up alarms and delete alarms with commands

DATABASE SCHEMEA

we have one collection for each server, 
    in each collection, two types of documents exist
    1. Users: holds user id, points, streak, and last ping time
    2. Alarms: holds time, point value, and message to send

"""

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

bot = commands.Bot(command_prefix='!')

connection = MongoClient(os.getenv('DB_URL'))
db = connection['discordBot']
debug = db['debug']
cwd = os.getcwd()

sched = AsyncIOScheduler()
sched.start()

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
    curr_time = time.time()
    collection = db[str(server)]
    # check if there is an alarm now
    alarm = collection.find_one({"time": time.strftime("%H:%M", time.localtime())})
    if alarm:
        # if there is one then we can update
        increase = int(alarm["points"])
        # check if this user has a streak
        # if so points go up based on that streak

        doc = collection.find_one({"user":user})
        if doc and 'streak' in doc:
            if abs(curr_time - doc["last_update"]) <= 86400: 
                increase *= doc['streak'] + 1
            if abs(curr_time - doc["last_update"]) < 60:
                return await ctx.send("you have already been marked as here for this alarm")

        collection.update_one({"user":user}, {"$inc": {'points' : increase, 'streak' : 1}, "$set" : {"last_update" : time.time()}}, upsert=True)
        await ctx.send(f'thank you for coming {ctx.author.name}!')
    else:
        await ctx.send("there is no alarm set for this time")

@bot.command(name='points')
async def echo_points(ctx):
    user = ctx.author.id
    server = ctx.guild.id
    collection = db[str(server)]
    document = collection.find_one({"user":user})
    await ctx.send(f'Hello {ctx.author.name}, you have {document["points"]} points and a streak of {document["streak"]}!')

@bot.command(name='set_alarm')
async def set_preferences(ctx, _time, _points, _message_to_send):
    try:
        alarm = time.strptime(_time, "%H:%M")
        alarm = time.strftime("%H:%M", alarm)
        p = int(_points)
        user = ctx.author.id
        server = ctx.guild.id
        collection = db[str(server)]
        
        collection.update_one({'time': alarm}, {"$set": {"time": alarm, "points": p, "message": _message_to_send}}, upsert=True)
        document = collection.find_one({'time': alarm})
        # Create job
        sched.add_job(send_attendance_message, 'cron', hour=alarm[:2], minute=alarm[3:5], id=str(document['_id']), args=(ctx, _message_to_send))
        
        await ctx.send(f"alarm set for {alarm}, worth {p} points!")
    except:
        await ctx.send("looks like that command wasn't formatted correctly, use `bot_help` to find the correct way to set up this bot")

async def send_attendance_message(ctx, _message_to_send):
    await ctx.send(_message_to_send)

@bot.command(name='delete_alarm')
async def debug_time(ctx, _time):
    server = ctx.guild.id
    collection = db[str(server)]
    
    try:
        alarm = time.strptime(_time, "%H:%M")
        alarm = time.strftime("%H:%M", alarm)
        document = collection.find_one({"time": alarm})
        collection.delete_one({"time": alarm})
        
        sched.remove_job(str(document['_id']))

        await ctx.send(f"deleted alarm for {alarm}")
    except:
        return await ctx.send("not a valid time format")


@bot.command(name='bot_help')
async def info(ctx):
    await ctx.send("TO SET UP THIS BOT USE THE `set_alarm` command, arguments are space seperated \n <time> -> HH:mm string for when to send (24 hour time)\n <points> -> int how many points this rollcall is worth\n <message_to_send> -> str the message the bot will send ")

stay_alive() # keep this bot alive when hosting
bot.run(TOKEN)
asyncio.get_event_loop().run_forever()
