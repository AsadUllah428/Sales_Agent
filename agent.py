# agent.py

import logging
from datetime import datetime, timezone
from typing import Dict, Any, AsyncGenerator, Optional
import copy

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

class SalesAgent(BaseAgent):
    """A sophisticated sales agent with robust state management."""

    positive_words: set[str] = {"yes", "ok", "okay", "sure", "fine", "alright", "of course", "definitely", "please", "go ahead", "yep", "yah", "yeah", "affirmative"}
    negative_words: set[str] = {"no", "not", "don't", "later", "busy", "not interested", "decline", "nope"}

    def __init__(self, name: str):
        super().__init__(name=name, sub_agents=[])
        self._extra_attrs = {'data_manager': None}
        logger.info(f"SalesAgent '{name}' initialized")

    def set_data_manager(self, data_manager):
        """Sets the data manager instance."""
        self._extra_attrs['data_manager'] = data_manager
        logger.info("Data manager set for SalesAgent")

    def _yield_response(self, text: str, state_delta: Optional[Dict[str, Any]] = None) -> Event:
        """Helper to create a response event with optional state delta."""
        actions = EventActions(state_delta=copy.deepcopy(state_delta)) if state_delta else None
        return Event(
            author=self.name,
            content=genai_types.Content(
                role="agent",
                parts=[genai_types.Part(text=text)]
            ),
            actions=actions
        )

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if not self._extra_attrs['data_manager']:
            logger.error("Data manager not set. Cannot process conversation.")
            yield self._yield_response("System error: Data manager not configured.")
            return

        session_id = getattr(ctx.session, 'id', None)
        if not session_id:
            logger.error("No session ID found in InvocationContext")
            yield self._yield_response("System error: No session ID available.")
            return

        logger.info(f"AGENT: Processing message for session ID: {session_id}")

        user_message_text = None
        if hasattr(ctx, 'user_content') and ctx.user_content and hasattr(ctx.user_content, 'parts'):
            for part in ctx.user_content.parts:
                if hasattr(part, 'text') and isinstance(part.text, str) and part.text.strip():
                    user_message_text = part.text.strip().lower()
                    logger.debug(f"AGENT: Extracted message from ctx.user_content: '{user_message_text}'")
                    break

        current_state = getattr(ctx.session, 'state', {})
        logger.debug(f"AGENT: Current session state for {session_id}: {current_state}")

        state_delta = {}
        timestamp_now_iso = datetime.now(timezone.utc).isoformat()
        terminate_conversation = False
        next_step = current_state.get("current_step", "initial")
        lead_data_from_dm = self._extra_attrs['data_manager'].get_lead_data(session_id)
        logger.debug(f"AGENT: Lead data from DataManager for {session_id}: {lead_data_from_dm}")
        lead_name = lead_data_from_dm.get("name", "there") if lead_data_from_dm else "there"
        next_status = lead_data_from_dm.get('status') if lead_data_from_dm else current_state.get('status')
        message_to_send = None

        
        if next_step == "initial" or current_state.get("status") in ["declined", "completed", "terminated"] or not lead_data_from_dm:
            logger.info(f"AGENT: Starting or restarting conversation for lead {session_id}.")
            lead_name = user_message_text if user_message_text else "there"
            new_lead_data = {
                "lead_id": session_id,
                "name": lead_name,
                "status": "awaiting_consent",
                "last_agent_msg_ts": timestamp_now_iso,
                "follow_up_sent_flag": "False"
            }
            self._extra_attrs['data_manager'].update_lead(new_lead_data)
            logger.info(f"AGENT: Updated DataManager with new lead data for {session_id}: {new_lead_data}")
            state_delta.update(new_lead_data)
            state_delta["current_step"] = "awaiting_consent"
            state_delta["age"] = None
            state_delta["country"] = None
            state_delta["interest"] = None
            next_step = "awaiting_consent"
            next_status = "awaiting_consent"
            message_to_send = f"Hello {lead_name.capitalize()}, thank you for your interest. May I ask you a few questions to understand your needs better?"

        
        elif next_step == "awaiting_consent":
            if any(consent in user_message_text for consent in self.positive_words):
                next_step = "awaiting_age"; next_status = "awaiting_age"
                message_to_send = "Excellent! What is your age?"
            elif any(decline in user_message_text for decline in self.negative_words):
                next_step = "declined"; next_status = "declined"
                message_to_send = "Understood. If you change your mind, feel free to reach out again!"
                state_delta['last_agent_msg_ts'] = timestamp_now_iso
                terminate_conversation = True
            else:
                message_to_send = "Pardon? Could you please confirm if it's okay for me to ask a few questions?"

        elif next_step == "awaiting_age":
            if user_message_text and user_message_text.isdigit() and 0 < int(user_message_text) < 120:
                state_delta['age'] = user_message_text
                next_step = "awaiting_country"; next_status = "awaiting_country"
                message_to_send = "Thank you. And which country are you currently residing in?"
            else:
                message_to_send = "Please enter your age as a number (e.g., 35)."

        elif next_step == "awaiting_country":
            if user_message_text:
                state_delta['country'] = user_message_text
                next_step = "no_response"; next_status = "no_response"
                message_to_send = "Great! What product or service are you most interested in today?"
            else:
                message_to_send = "Could you please specify the country?"

        elif next_step == "no_response":
                if user_message_text:
                    state_delta['interest'] = user_message_text
                    message_to_send = f"Fantastic, {lead_name}! We have noted your interest in {user_message_text.capitalize()}. Is there anything else I can help you with right now?"
                    state_delta['status'] = "secured"
                    state_delta['current_step'] = "secured" 
                else:
                    message_to_send = "To assist you best, could you please tell me what you're interested in?"

        elif next_step == "declined":
            message_to_send = "Thank you for getting back to me. How can I assist you now?"
            next_step = "awaiting_interest" 
            next_status = "re-engaged"

        elif next_step in ["completed", "terminated"]:
            message_to_send = "This conversation is now closed. Is there anything else I can help you with in a new session?"
            terminate_conversation = True

        else:
            logger.warning(f"Unknown state '{next_step}' for lead {session_id}.")
            message_to_send = "I'm sorry, I'm not sure how to proceed from here."
            next_step = "initial"
            next_status = "error"

        
        if next_step != current_state.get("current_step"):
            state_delta['current_step'] = next_step
        if next_status and next_status != (lead_data_from_dm.get('status') if lead_data_from_dm else current_state.get('status')):
            state_delta['status'] = next_status
        if message_to_send and 'last_agent_msg_ts' not in state_delta:
            state_delta['last_agent_msg_ts'] = timestamp_now_iso

        yield self._yield_response(message_to_send, state_delta if message_to_send else None)

        
        updated_lead_data = {"lead_id": session_id}
        updated_lead_data.update(state_delta)
        self._extra_attrs['data_manager'].update_lead(updated_lead_data)
        logger.info(f"AGENT: Updated DataManager for session ID {session_id} with: {updated_lead_data}")

        if terminate_conversation:
            yield Event(author=self.name, actions=EventActions(state_delta={"current_step": "terminated", "status": next_status or (lead_data_from_dm.get('status') if lead_data_from_dm else current_state.get('status', 'terminated'))}))
			