					
# main.py

import threading
import logging
import time
import os
import sys
from datetime import datetime, timedelta
from datetime import datetime, timedelta, timezone 

from config import (
    CSV_FILENAME, APP_NAME, SIMULATED_DELAY_SECONDS,
    FOLLOW_UP_CHECK_INTERVAL_SECONDS, GOOGLE_CREDENTIALS_PATH,
    LOG_LEVEL, LOG_FORMAT, LOG_FILE
)
from agent import SalesAgent
from lead_manager import DataManager

from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types as genai_types

def setup_logging():
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    handlers = [logging.StreamHandler(sys.stdout)]

    if LOG_FILE:
        try:
            handlers.append(logging.FileHandler(LOG_FILE))
        except Exception as e:
            print(f"Warning: Could not set up file logging: {e}")

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        handlers=handlers
    )

logger = logging.getLogger(__name__)
_follow_up_running = True

def follow_up_checker(data_manager_instance: DataManager, session_service, runner_instance):
    logger.info("Follow-up checker thread started.")
    global _follow_up_running

    while _follow_up_running:
        try:
            time.sleep(FOLLOW_UP_CHECK_INTERVAL_SECONDS)
            now = datetime.now(timezone.utc) 
            cutoff_time = now - timedelta(seconds=SIMULATED_DELAY_SECONDS)

            active_leads = data_manager_instance.get_all_active_leads_for_followup()
            if not active_leads:
                continue

            logger.debug(f"Checking {len(active_leads)} active leads for follow-up potential.")

            for lead_info in active_leads:
                session_id = lead_info.get('lead_id')
                ts_str = lead_info.get('last_agent_msg_ts')

                follow_up_sent = str(lead_info.get('follow_up_sent_flag', 'False')).strip().lower() == 'true'
                status = lead_info.get('status', 'unknown')

                if not session_id or not ts_str or status in {'unknown', 'secured', 'no_response', 'declined_final', 'terminated'}:
                    logger.debug(f"Skipping follow-up for {session_id}: Invalid data or terminal state ({status}).")
                    continue

                try:
                    last_msg_time = datetime.fromisoformat(ts_str).astimezone(timezone.utc) # Ensure UTC

                    if not follow_up_sent and last_msg_time < cutoff_time:
                        logger.info(f"Follow-up needed for lead {session_id} (Status: {status})")
                        name = lead_info.get('name', 'there')
                        followup_message = ""
                        if status == "awaiting_consent":
                            followup_message = f"Hello {name.capitalize()}! Just checking back to see if you're okay with me asking a few questions."
                        elif status == "awaiting_age":
                            followup_message = f"Hi {name.capitalize()}, just a quick follow-up. Could you please share your age?"
                        elif status == "awaiting_country":
                            followup_message = f"Hello {name.capitalize()}! Following up on our last interaction. Which country are you from?"
                        elif status == "awaiting_interest":
                            followup_message = f"Hi {name.capitalize()}, just wanted to check in. What product or service are you interested in?"
                        elif status == "awaiting_followup_after_decline":
                            followup_message = f"Hello {name.capitalize()}, just a friendly follow-up. If you change your mind, let me know!"
                        else:
                            followup_message = f"Hello {name.capitalize()}, just checking in!"
                            logger.warning(f"Using generic follow-up for lead {session_id} with unhandled status for follow-up: {status}")

                        print(f"\n--- System Follow-up ({session_id}) ---")
                        print(f"{followup_message}")
                        print(f">>> ", end='', flush=True)

                        
                        user_content = genai_types.Content(
                            role='user',
                            parts=[genai_types.Part(text=followup_message)]
                        )
                        try:
                           
                            events = runner_instance.run(user_id="followup_system", session_id=session_id, new_message=user_content)
                            for event in events:
                                if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts') and event.content.parts:
                                    text = event.content.parts[0].text
                                    if text:
                                        print(f"Agent (Follow-up - {session_id}): {text}")
                            data_manager_instance.update_lead({
                                "lead_id": session_id,
                                "follow_up_sent_flag": 'True',
                                "last_agent_msg_ts": datetime.now(timezone.utc).isoformat() 
                            })
                            logger.info(f"Follow-up triggered and flag updated for lead {session_id}.")

                        except Exception as agent_err:
                            logger.error(f"Error running agent for follow-up on {session_id}: {agent_err}", exc_info=True)


                except ValueError:
                    logger.warning(f"Could not parse timestamp '{ts_str}' for lead {session_id}. Cannot determine follow-up time.")

                except Exception as e:
                    logger.error(f"Error processing follow-up for lead {session_id}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in follow-up checker main loop: {e}", exc_info=True)
            time.sleep(10)

    logger.info("Follow-up checker thread stopped.")


def run_sales_agent():
    setup_logging()
    logger.info("--- Setting up Sales Agent ---")

    if GOOGLE_CREDENTIALS_PATH:
        if os.path.exists(GOOGLE_CREDENTIALS_PATH):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIALS_PATH
            logger.info(f"Set Google credentials from: {GOOGLE_CREDENTIALS_PATH}")
        else:
            logger.warning(f"Google credentials file not found: {GOOGLE_CREDENTIALS_PATH}")

    try:
        data_manager = DataManager(filename=CSV_FILENAME)
        session_service = InMemorySessionService()
        sales_agent = SalesAgent(name="SalesAgent")
        sales_agent.set_data_manager(data_manager)

        runner = Runner(
            agent=sales_agent,
            app_name=APP_NAME,
            session_service=session_service
        )

        follow_up_thread = threading.Thread(
            target=follow_up_checker,
            args=(data_manager, session_service, runner),
            daemon=True,
            name="FollowUpChecker"
        )
        follow_up_thread.start()
        logger.info("Follow-up checker thread started")

        print("\n--- Sales Agent System ---")
        print("Enter 'quit' or 'bye' to exit.")
        print("Type your first Name to start a conversation.\n")

        current_lead_id = None

        while True:
            user_input = input(">>> ").strip()
            if not user_input:
                continue

            if user_input.lower() == 'reset':
                current_lead_id = None
                print("\n--- Reset done. Please type a new name to start a new conversation. ---\n")
                continue

            if user_input.lower() == 'quit' or user_input.lower() == 'bye':
                break

            if user_input.lower() == 'list':
                leads = data_manager._read_all()
                if not leads:
                    print("No leads found.")
                else:
                    print("\nCurrent Leads:")
                    print(f"{'ID':<10} {'Name':<15} {'Status':<15} {'Interest':<15} {'FollowUp':<10}")
                    print("-" * 65)
                    for lead in leads:
                        lead_id = lead.get('lead_id', 'N/A')
                        name = lead.get('name', 'N/A')
                        status = lead.get('status', 'N/A')
                        interest = lead.get('interest', 'N/A')
                        follow_up = lead.get('follow_up_sent_flag', 'False')
                        print(f"{lead_id:<10} {name:<15} {status:<15} {interest:<15} {follow_up:<10}")
                    print()
                continue


            if not current_lead_id:
                lead_name = user_input
                lead_id = data_manager.generate_lead_id()
                current_lead_id = lead_id

                logger.info(f"Generated lead_id: {lead_id} for {lead_name}")

                try:
                    session_service.create_session(
                        app_name=APP_NAME,
                        user_id="cli_user",
                        session_id=lead_id
                    )
                    print(f"Starting conversation with: {lead_id} ({lead_name.capitalize()})")
                    user_content = genai_types.Content(
                        role='user',
                        parts=[genai_types.Part(text=lead_name)]
                    )
                    events = runner.run(user_id="cli_user", session_id=lead_id, new_message=user_content)

                    for event in events:
                        if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts') and event.content.parts:
                            text = event.content.parts[0].text
                            if text:
                                print(f"Agent ({lead_id}): {text}")

                except Exception as e:
                    logger.error(f"Error creating new lead session: {e}", exc_info=True)
                    print("Error creating lead. Check logs.")
                continue


            try:
                user_content = genai_types.Content(
                    role='user',
                    parts=[genai_types.Part(text=user_input)]
                )

                events = runner.run(
                    user_id="cli_user",
                    session_id=current_lead_id,
                    new_message=user_content
                )

                for event in events:
                    if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts') and event.content.parts:
                        text = event.content.parts[0].text
                        if text:
                            print(f"Agent ({current_lead_id}): {text}")
                            if text.lower().startswith("goodbye"): 
                                current_lead_id = None
                                print("\n--- Conversation ended. Type a new name to start another. ---\n")
                                break

            except Exception as e:
                logger.error(f"Error sending message: {e}", exc_info=True)
                print("Error sending message. Check logs.")


    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)
        print(f"Critical error: {e}")

    finally:
        global _follow_up_running
        _follow_up_running = False
        if 'follow_up_thread' in locals() and follow_up_thread.is_alive():
            follow_up_thread.join(timeout=1.0)
        print("Sales Agent stopped.")

if __name__ == "__main__":
    run_sales_agent()