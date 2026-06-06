import os
import json
import requests
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, List, Tuple

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

TOKEN_FILE = "token.json"
SCOPES = ['https://www.googleapis.com/auth/calendar']


def normalize_timezone_name(tz_name: Optional[str]) -> str:
    if not tz_name:
        return 'UTC'

    cleaned = tz_name.strip().replace(' ', '')
    lowered = cleaned.lower()

    aliases = {
        'asiankolkata': 'Asia/Kolkata',
        'asia/calcutta': 'Asia/Kolkata',
        'asia/kolkata': 'Asia/Kolkata',
        'ist': 'Asia/Kolkata',
        'utc': 'UTC',
        'gmt': 'UTC',
    }

    if lowered in aliases:
        return aliases[lowered]

    return tz_name

def get_credentials() -> Optional[Credentials]:
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                with open(TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
            return creds
        except Exception as e:
            print(f"Error loading credentials: {e}")
            return None
    return None

def is_env_configured() -> bool:
    return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))

def get_oauth_flow(redirect_uri: Optional[str] = None) -> Flow:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    env_redirect = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/callback")
    
    target_redirect = redirect_uri or env_redirect
    
    if not client_id or not client_secret:
        raise ValueError("Google credentials not configured. Please supply Client ID and Secret.")
        
    client_config = {
        "web": {
            "client_id": client_id,
            "project_id": "study-planner",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": [target_redirect]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=target_redirect
    )
    flow.autogenerate_code_verifier = False
    return flow

def parse_study_prompt(prompt: str) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not configured in env variables")
        
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    current_date = date.today().isoformat()
    current_weekday = date.today().strftime("%A")
    
    system_instruction = (
        "You are an AI Study Planner Agent. Extract the following study parameters from the user prompt "
        f"as JSON. Today's date is {current_date} ({current_weekday}).\n\n"
        "Parameters to extract:\n"
        "- topic (string): Subject/topic of study.\n"
        "- total_sessions (integer): Number of sessions. Default to 5.\n"
        "- session_duration_hours (float): Hours per session. Default to 2.0.\n"
        "- start_date (string, YYYY-MM-DD): Start date. If relative (e.g. 'tomorrow', 'next Monday'), resolve it based on today's date. Default to tomorrow.\n"
        "- preferred_start_time (string, HH:MM): Start time. Default to '14:00'.\n"
        "- preferred_end_time (string, HH:MM): End time. Default to '18:00'.\n"
        "- excluded_weekdays (list of integers, 0=Monday, 6=Sunday): Weekdays to exclude. E.g. 'weekdays only' means [5, 6] are excluded. Default to [].\n\n"
        "Return ONLY a JSON object with these exact keys. Do not include markdown code fence formatting."
    )
    
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    if response.status_code != 200:
        print("Groq Error Response:", response.text)
    response.raise_for_status()
    result = response.json()
    content = result["choices"][0]["message"]["content"]
    return json.loads(content)

def get_calendar_service(credentials) -> build:
    return build('calendar', 'v3', credentials=credentials)

def get_primary_timezone(service) -> str:
    try:
        calendar = service.calendars().get(calendarId='primary').execute()
        return normalize_timezone_name(calendar.get('timeZone', 'UTC'))
    except Exception as e:
        print(f"Error fetching timezone: {e}")
        return 'UTC'

def fetch_busy_intervals(service, start_dt: datetime, end_dt: datetime, calendar_id='primary') -> List[Tuple[datetime, datetime]]:
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        busy_intervals = []
        
        for event in events:
            if event.get('transparency') == 'transparent':
                continue
                
            start_str = event['start'].get('dateTime') or event['start'].get('date')
            end_str = event['end'].get('dateTime') or event['end'].get('date')
            
            if not start_str or not end_str:
                continue
                
            if 'date' in event['start'] and 'dateTime' not in event['start']:
                s_date = date.fromisoformat(start_str)
                e_date = date.fromisoformat(end_str)
                s_dt = datetime.combine(s_date, time.min)
                e_dt = datetime.combine(e_date, time.min)
            else:
                s_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                e_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                
            busy_intervals.append((s_dt, e_dt))
            
        return busy_intervals
    except Exception as e:
        print(f"Error fetching calendar events: {e}")
        return []

def find_free_study_slots(
    start_date: date,
    end_date: Optional[date],
    total_sessions: int,
    session_duration: timedelta,
    window_start_time: time,
    window_end_time: time,
    excluded_weekdays: List[int],
    busy_intervals: List[Tuple[datetime, datetime]],
    tz_str: str
) -> List[Tuple[datetime, datetime]]:
    tz = ZoneInfo(tz_str)
    scheduled_slots = []
    current_date = start_date
    sessions_scheduled = 0
    max_search_days = 90
    days_searched = 0
    
    localized_busy = []
    for b_start, b_end in busy_intervals:
        if b_start.tzinfo is None:
            b_start = b_start.replace(tzinfo=tz)
        else:
            b_start = b_start.astimezone(tz)
            
        if b_end.tzinfo is None:
            b_end = b_end.replace(tzinfo=tz)
        else:
            b_end = b_end.astimezone(tz)
            
        localized_busy.append((b_start, b_end))
        
    sorted_busy = sorted(localized_busy, key=lambda x: x[0])
    
    while sessions_scheduled < total_sessions and days_searched < max_search_days:
        if end_date and current_date > end_date:
            break

        if current_date.weekday() in excluded_weekdays:
            current_date += timedelta(days=1)
            days_searched += 1
            continue
            
        window_start_dt = datetime.combine(current_date, window_start_time).replace(tzinfo=tz)
        window_end_dt = datetime.combine(current_date, window_end_time).replace(tzinfo=tz)
        
        overlapping_busy = []
        for b_start, b_end in sorted_busy:
            if b_start < window_end_dt and b_end > window_start_dt:
                clamp_start = max(b_start, window_start_dt)
                clamp_end = min(b_end, window_end_dt)
                if clamp_start < clamp_end:
                    overlapping_busy.append((clamp_start, clamp_end))
        
        merged_busy = []
        for b_start, b_end in sorted(overlapping_busy, key=lambda x: x[0]):
            if not merged_busy:
                merged_busy.append((b_start, b_end))
            else:
                last_start, last_end = merged_busy[-1]
                if b_start <= last_end:
                    merged_busy[-1] = (last_start, max(last_end, b_end))
                else:
                    merged_busy.append((b_start, b_end))
        
        candidate_start = window_start_dt
        slot_found = False
        
        for b_start, b_end in merged_busy:
            if b_start - candidate_start >= session_duration:
                scheduled_slots.append((candidate_start, candidate_start + session_duration))
                slot_found = True
                break
            candidate_start = max(candidate_start, b_end)
            
        if not slot_found:
            if window_end_dt - candidate_start >= session_duration:
                scheduled_slots.append((candidate_start, candidate_start + session_duration))
                slot_found = True
                
        if slot_found:
            sessions_scheduled += 1
            new_slot = scheduled_slots[-1]
            sorted_busy.append(new_slot)
            sorted_busy = sorted(sorted_busy, key=lambda x: x[0])
            
        current_date += timedelta(days=1)
        days_searched += 1
        
    return scheduled_slots

def insert_study_sessions(service, topic: str, slots: List[Tuple[datetime, datetime]], calendar_id='primary') -> List[dict]:
    created_events = []
    total_slots = len(slots)
    
    for i, (s_dt, e_dt) in enumerate(slots, 1):
        summary = f"Study Session: {topic} ({i}/{total_slots})"
        description = f"Topic: {topic}\nSession {i} of {total_slots}."
        
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': s_dt.isoformat(),
            },
            'end': {
                'dateTime': e_dt.isoformat(),
            },
            'reminders': {
                'useDefault': True,
            },
            'colorId': '5'
        }
        
        try:
            created = service.events().insert(calendarId=calendar_id, body=event).execute()
            created_events.append(created)
        except Exception as e:
            print(f"Error inserting event {summary}: {e}")
            
    return created_events
