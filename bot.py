import os
import time
import discord
from discord.ext import commands
from dotenv import load_dotenv
from pymongo import MongoClient

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
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

        doc = collection.find_one({"user": user})
        streak_flag = False
        if doc and 'streak' in doc:
            if abs(curr_time - doc["last_update"]) <= 86400: 
                increase *= doc['streak'] + 1
                streak_flag = True
            if abs(curr_time - doc["last_update"]) < 60:
                return await ctx.send("you have already been marked as here for this alarm")

        if streak_flag:
            collection.update_one({"user":user}, {"$inc": {'points' : increase, 'streak' : 1}, "$set" : {"last_update" : time.time()}}, upsert=True)
        else:
            collection.update_one({"user":user}, {"$inc": {'points' : increase}, "$set" : {"last_update" : time.time(), 'streak' : 1}}, upsert=True)

        await ctx.send(f'thank you for coming {ctx.author.name}!')
    else:
        await ctx.send("there is no alarm set for this time")

@bot.command(name='points')
async def echo_points(ctx):
    user = ctx.author.id
    server = ctx.guild.id
    collection = db[str(server)]
    document = collection.find_one({"user": user})
    if document:
        await ctx.send(f'Hello {ctx.author.name}, you have {document["points"]} points and a streak of {document["streak"]}!')
    else:
        await ctx.send(f'Hello {ctx.author.name}, you have no points. Make sure to be present next time!')

@bot.command(name='set_alarm')
async def set_preferences(ctx, _time, _points, _message_to_send):
    try:
        alarm = time.strptime(_time, "%H:%M")
        alarm = time.strftime("%H:%M", alarm)
        p = int(_points)
        user = ctx.author.id
        server = ctx.guild.id
        collection = db[str(server)]
        
        collection.update_one({'time': alarm}, {"$set": {"time": alarm, "points": p, "message": _message_to_send, "channel": ctx.channel.id}}, upsert=True)
        document = collection.find_one({'time': alarm})
        # Create job
        sched.add_job(send_attendance_message, 'cron', hour=alarm[:2], minute=alarm[3:5], id=str(document['_id']), args=(ctx, db, alarm))
        
        await ctx.send(f"alarm set for {alarm}, worth {p} points!")
    except:
        await ctx.send("looks like that command wasn't formatted correctly, or an alarm already exists at this time")

async def send_attendance_message(ctx, database, alarm):
    channel_id = ctx.channel.id
    server = ctx.guild.id
    collection = database[str(server)]
    document = collection.find_one({"time": alarm, "channel": channel_id})
    msg = document['message']
    await ctx.send(msg)

@bot.command(name='list_alarms')
async def list_alarms(ctx):
    channel_id = ctx.channel.id
    server = ctx.guild.id
    collection = db[str(server)]
    documents = collection.find({"channel": channel_id})
    msg = ""
    for d in documents:
        msg += f"Time: {d['time']}, Points: {d['points']}, Message: {d['message']}\n"

    if (msg):
        await ctx.send(msg)
    else:
        await ctx.send("There are no alarms set in this channel")

@bot.command(name='delete_alarm')
async def remove_alarm(ctx, _time):
    server = ctx.guild.id
    collection = db[str(server)]
    channel_id = ctx.channel.id
    
    try:
        alarm = time.strptime(_time, "%H:%M")
        alarm = time.strftime("%H:%M", alarm)
        document = collection.find_one({"time": alarm, "channel": channel_id})
        collection.delete_one({"time": alarm, "channel": channel_id})
        
        sched.remove_job(str(document['_id']))

        await ctx.send(f"deleted alarm for {alarm}")
    except:
        return await ctx.send("not a valid time format")

@bot.command(name='delete_all_alarms')
async def delete_every_alarm(ctx):
    channel_id = ctx.channel.id
    server = ctx.guild.id
    collection = db[str(server)]
    documents = collection.find({"channel": channel_id})
    msg = ""
    for d in documents:
        msg += f"Deleted Alarm - Time: {d['time']}, Points: {d['points']}, Message: {d['message']}\n"
        d_id = d['_id']
        collection.delete_one({'time': d['time'], 'channel': d['channel']})
        sched.remove_job(str(d_id))

    if (msg):
        await ctx.send(msg)
    else:
        await ctx.send("There are no alarms set in this channel")

@bot.command(name='edit_alarm')
async def edit(ctx, _time, _edited_message):
    channel_id = ctx.channel.id
    server = ctx.guild.id
    collection = db[str(server)]
    document = collection.find_one({"time": _time, "channel": channel_id})

    if (document == None):
        await ctx.send("Could not find alarm at this time for this channel")
    else:
        prev_message = document['message']
        collection.update_one({"time": _time, "channel": channel_id}, {"$set": {"message": _edited_message}})
        await ctx.send(f"Message for time {_time} has been updated from \"{prev_message}\" to \"{_edited_message}\"")

@bot.command(name='bot_help')
async def info(ctx):
    await ctx.send("TO SET UP THIS BOT USE THE `set_alarm` command, arguments are space seperated \n <time> -> HH:mm string for when to send (24 hour time)\n <points> -> int how many points this rollcall is worth\n <message_to_send> -> str the message the bot will send ")

bot.run(TOKEN)
asyncio.get_event_loop().run_forever()
