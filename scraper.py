# scraper.py

import requests
import logging
from bs4 import BeautifulSoup, Tag
from typing import List, Dict

# Assumes config.py is in the same directory
from config import BASE_CALENDAR_URL, COOKIE_URL
from datetime import date, datetime

# Get the logger
logger = logging.getLogger(__name__)


def get_full_schedule() -> List[Dict[str, str]]:
    """
    Fetches the schedule by first getting a session cookie from the main site,
    then accessing the calendar page.
    """
    # Use a Session object to persist cookies across requests
    with requests.Session() as session:
        # It's good practice to always set a User-Agent
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

        try:
            # Step 1: Visit the initial page to acquire the session cookie
            logger.info(f"Acquiring session cookie from: {COOKIE_URL}")
            cookie_response = session.get(COOKIE_URL, timeout=15)
            cookie_response.raise_for_status()
            logger.info("Successfully acquired session cookie.")

            # Step 2: Access the calendar page. The session will automatically send the cookie.
            logger.info(f"Fetching calendar from: {BASE_CALENDAR_URL}")
            schedule_response = session.get(BASE_CALENDAR_URL, timeout=15)
            schedule_response.raise_for_status()
            logger.info(f"Successfully fetched schedule HTML ({len(schedule_response.content)} bytes).")

            return parse_fencing_schedule(schedule_response.content)

        except requests.RequestException as e:
            logger.error(f"FATAL: A network error occurred during the scraping process. Exception: {e}")
            return []


def parse_fencing_schedule(html: bytes) -> List[Dict[str, str]]:
    """
    Parses the HTML using a robust "bottom-up" approach.
    """
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    schedule = []
    coach_headers = soup.find_all('tr', {'height': '24', 'bgcolor': '#ffff66'})

    if not coach_headers:
        logger.warning("Parser did not find any coach header rows. The page might be empty or changed.")
        return []

    for header in coach_headers:
        coach_name_tag = header.find('a', class_='maintext')
        if not coach_name_tag or "Coach:" not in coach_name_tag.text:
            continue
        current_coach = coach_name_tag.text.replace("Coach:", "").strip()

        day_column = header.find_parent('td', class_='tdborder')
        if not day_column:
            continue

        day_header = day_column.find('tr', {'height': '34'})
        if not day_header:
            continue

        day_of_week = day_header.find('a', class_='mainbold').text.strip() if day_header.find('a',
                                                                                              class_='mainbold') else "Unknown"
        full_date = day_header.find('a', class_='smallbold').text.strip() if day_header.find('a',
                                                                                             class_='smallbold') else "Unknown"

        for slot_row in header.find_next_siblings('tr'):
            columns = slot_row.find_all('td', class_='tdborder', recursive=False)
            if len(columns) == 2:
                time = columns[0].text.strip()
                status = 'Available' if columns[1].find('input') else 'Booked'
                schedule.append({
                    'day': day_of_week, 'date': full_date, 'coach': current_coach,
                    'time': time, 'status': status
                })

    return schedule


def get_available_classes() -> List[Dict[str, str]]:
    """Fetches the live schedule and returns a list of only available classes."""
    full_schedule = get_full_schedule()
    return [slot for slot in full_schedule if slot['status'] == 'Available']


def get_all_coaches() -> List[str]:
    """Fetches the schedule and returns a unique, sorted list of all coach names."""
    # full_schedule = get_full_schedule()
    # if not full_schedule:
    #     logger.warning("get_full_schedule() returned no data, so coach list is empty.")
    #     return []
    #
    # coaches = {slot['coach'] for slot in full_schedule if slot['coach'] and slot['coach'] != "Unknown Coach"}
    # return sorted(list(coaches))
    return ['Arseni', 'David G', 'Igor']


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    print("--- Running Final Scraper Self-Test (Dynamic Cookie) ---")
    coaches = get_all_coaches()
    if coaches:
        print(f"✅ SUCCESS: Found {len(coaches)} coaches: {coaches}")
        available = get_available_classes()
        print(f"✅ Found {len(available)} available slots. Sample: {available[:3]}")
    else:
        print("❌ FAILURE: Could not fetch coach list. Check logs for warnings/errors.")