import os
import sys

# Add root directory to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.planner_service import get_credentials, get_calendar_service, get_primary_timezone

def main():
    print("Testing Google Calendar connection...")
    creds = get_credentials()
    if not creds:
        print("FAIL: get_credentials() returned None or failed to load.")
        return
        
    print("Credentials loaded successfully.")
    print("Expiry:", creds.expiry)
    print("Valid:", creds.valid)
    
    try:
        service = get_calendar_service(creds)
        print("Calendar service built successfully.")
        tz = get_primary_timezone(service)
        print("Primary Timezone:", tz)
    except Exception as e:
        print("ERROR occurred during API call:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
