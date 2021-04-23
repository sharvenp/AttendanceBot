from flask import Flask
from threading import Thread

"""
This file exists so that when hosting we can ping a website to keep the bot alive
"""

app = Flask('')

@app.route("/")
def home():
    return "Website to keep AttendanceBot Alive"

def run_bot():
    app.run(host='0.0.0.0', port=8080)

def stay_alive():
    t = Thread(target=run_bot)
    t.start()