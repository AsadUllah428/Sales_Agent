
# lead_manager.py


import csv
import os
import threading
import logging
import uuid
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class DataManager:
    """Handles thread-safe reading and writing to the leads CSV file."""

    def __init__(self, filename="leads.csv"):
        self.filename = filename
        self.lock = threading.Lock()
        self.fieldnames = [
            'lead_id', 'name', 'age', 'country', 'interest', 'status',
            'last_agent_msg_ts', 'follow_up_sent_flag'
        ]
        self._initialize_csv()
        logger.info(f"DataManager initialized for file: {self.filename}")

    def _initialize_csv(self):
        """Create CSV file with headers if it doesn't exist."""
        with self.lock:
            try:
                file_exists = os.path.exists(self.filename)
                is_empty = file_exists and os.path.getsize(self.filename) == 0
                
                if not file_exists or is_empty:
                    try:
                        # Create directory if it doesn't exist
                        directory = os.path.dirname(self.filename)
                        if directory and not os.path.exists(directory):
                            os.makedirs(directory)
                            
                        with open(self.filename, 'w', newline='', encoding='utf-8') as csvfile:
                            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                            writer.writeheader()
                        logger.info(f"Initialized CSV file: {self.filename}")
                    except IOError as e:
                        logger.error(f"Error initializing CSV file {self.filename}: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Unexpected error in _initialize_csv: {e}", exc_info=True)

    def _read_all(self) -> List[Dict[str, str]]:
        """Read all rows from the CSV file."""
        rows = []
        if not os.path.exists(self.filename):
            logger.warning(f"CSV file {self.filename} does not exist, initializing")
            self._initialize_csv()
            return rows
            
        try:
            with open(self.filename, 'r', newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                if not reader.fieldnames:
                    logger.warning("CSV file has no headers, reinitializing")
                    self._initialize_csv()
                    return rows
                    
                for row in reader:
                    complete_row = {field: row.get(field, '') for field in self.fieldnames}
                    rows.append(complete_row)
        except Exception as e:
            logger.error(f"Error reading CSV file {self.filename}: {e}", exc_info=True)
            return []
        return rows

    def _write_all(self, data: List[Dict[str, Any]]):
        """Write all rows to the CSV file."""
        try:
            # Create backup before writing
            if os.path.exists(self.filename):
                backup_name = f"{self.filename}.bak"
                try:
                    with open(self.filename, 'r', encoding='utf-8') as src, open(backup_name, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                except Exception as be:
                    logger.error(f"Failed to create backup before writing: {be}")
                    
            with open(self.filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames, extrasaction='ignore')
                writer.writeheader()
                sanitized_data = [{field: str(row.get(field, '')) for field in self.fieldnames} for row in data]
                writer.writerows(sanitized_data)
        except IOError as e:
            logger.error(f"Error writing to CSV file {self.filename}: {e}", exc_info=True)
            # Try to restore from backup if write failed
            backup_name = f"{self.filename}.bak"
            if os.path.exists(backup_name):
                try:
                    with open(backup_name, 'r', encoding='utf-8') as src, open(self.filename, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                    logger.info("Restored CSV file from backup after write failure")
                except Exception as re:
                    logger.error(f"Failed to restore from backup: {re}")

    def get_lead_data(self, lead_id: str):
        """Retrieve data for a specific lead."""
        if not lead_id:
            logger.error("Cannot get lead data: lead_id is empty")
            return None

        with self.lock:
            rows = self._read_all()
            for row in rows:
                if row.get('lead_id', '').strip().lower() == str(lead_id).strip().lower():
                    return row
        return None



    def update_lead(self, lead_data: Dict[str, Any]):
        """Update or add lead information in the CSV."""
        if not lead_data:
            logger.error("Cannot update lead: lead_data is empty")
            return
            
        lead_data_str = {k: str(v) if v is not None else '' for k, v in lead_data.items()}
        with self.lock:
            rows = self._read_all()
            lead_id_to_update = lead_data_str.get('lead_id')
            if not lead_id_to_update:
                logger.error("CSV Update Error: lead_id missing in data.")
                return
                
            updated = False
            update_values = {field: lead_data_str.get(field) for field in self.fieldnames if field in lead_data_str}
            
            for i, row in enumerate(rows):
                if row.get('lead_id') == str(lead_id_to_update):
                    rows[i] = {**row, **update_values}
                    updated = True
                    break
                    
            if not updated:
                new_row = {field: update_values.get(field, '') for field in self.fieldnames}
                new_row['lead_id'] = str(lead_id_to_update)
                
                # Set timestamp if not provided
                if not new_row.get('last_agent_msg_ts'):
                    new_row['last_agent_msg_ts'] = datetime.now().isoformat()
                    
                rows.append(new_row)
                logger.info(f"Adding new lead {lead_id_to_update} to CSV.")
                
            self._write_all(rows)
            logger.debug(f"CSV updated for lead_id: {lead_id_to_update}")

    def get_all_active_leads_for_followup(self) -> List[Dict[str, str]]:
        """Get leads that need follow-up."""
        active_leads = []
        with self.lock:
            try:
                rows = self._read_all()
                for row in rows:
                    status = row.get('status', '')
                    if not status or status.lower() in ['secured', 'no_response', 'declined', 'completed']:
                        continue
                        
                    if not row.get('last_agent_msg_ts'):
                        continue
                        
                    active_leads.append({
                        'lead_id': row.get('lead_id', ''),
                        'name': row.get('name', ''),
                        'status': status,
                        'last_agent_msg_ts': row.get('last_agent_msg_ts', ''),
                        'follow_up_sent_flag': row.get('follow_up_sent_flag', 'False')
                    })
            except Exception as e:
                logger.error(f"Error in get_all_active_leads_for_followup: {e}", exc_info=True)
                
        return active_leads

    def generate_lead_id(self) -> str:
        """Generate a unique lead ID."""
        with self.lock:
            rows = self._read_all()
            existing_ids = {row.get('lead_id') for row in rows}
            while True:
                new_id = f"L{uuid.uuid4().hex[:8].upper()}"
                if new_id not in existing_ids:
                    return new_id