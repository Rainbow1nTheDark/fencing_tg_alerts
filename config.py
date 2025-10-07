# config.py

from dotenv import load_dotenv
import os

load_dotenv()

# Replace "YOUR_TELEGRAM_BOT_TOKEN" with the token you get from BotFather
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

BASE_CALENDAR_URL = "https://www.fencersnetwork.com/calendar/calendar_public.asp?c=SWP&v=9"

# The initial URL to visit to get a valid session cookie.
COOKIE_URL = "https://www.swordplayers.com/index.asp"

# This is the 'd' value for a known date. We'll use this to calculate future dates.
# d=6477 corresponds to Sep 24, 2025
REFERENCE_D_VALUE = 6477
REFERENCE_DATE = "2025-09-24" # YYYY-MM-DD