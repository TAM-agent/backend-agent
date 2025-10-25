"""Firestore service for simulated sensor data.

This module provides functions to interact with Firestore
as a replacement for the physical Raspberry Pi sensors during development.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    logger.warning("google-cloud-firestore not installed, will use local JSON simulation")
    FIRESTORE_AVAILABLE = False
    firestore = None


class FirestoreSimulator:
    """Simulates IoT sensor data using Firestore or local JSON file."""

    def __init__(self, use_firestore: bool = True):
        """Initialize Firestore simulator.

        Args:
            use_firestore: If True, use Firestore. If False, use local JSON file.
        """
        self.use_firestore = use_firestore
        self.local_data_file = os.path.join(
            os.path.dirname(__file__), '..', 'simulation_data.json'
        )
        self.db = None

        if use_firestore and FIRESTORE_AVAILABLE:
            try:
                self.db = firestore.Client()
                logger.info("Firestore initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Firestore: {e}, using local data")
                self.use_firestore = False
        elif use_firestore and not FIRESTORE_AVAILABLE:
            logger.warning("Firestore requested but not available, using local data")
            self.use_firestore = False

    def _load_local_data(self) -> Dict[str, Any]:
        """Load data from local JSON file."""
        try:
            with open(self.local_data_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Simulation data file not found: {self.local_data_file}")
            return self._get_default_data()
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing simulation data: {e}")
            return self._get_default_data()

    def _get_default_data(self) -> Dict[str, Any]:
        """Return default simulation data if file is missing."""
        return {
            "plants": {
                "tomato": {
                    "name": "tomato",
                    "current_moisture": 50,
                    "health_score": 3,
                    "history": []
                }
            },
            "water_tank": {
                "level_percentage": 50,
                "capacity_liters": 100
            },
            "system_status": {
                "overall_health": "ok",
                "active_alerts": []
            }
        }

    def get_plant_moisture(self, plant_name: str) -> Optional[int]:
        """Get current moisture level for a plant."""
        if self.use_firestore and self.db:
            try:
                doc_ref = self.db.collection('plants').document(plant_name)
                doc = doc_ref.get()
                if doc.exists:
                    return doc.to_dict().get('current_moisture')
                return None
            except Exception as e:
                logger.error(f"Error reading from Firestore: {e}")
                return None
        else:
            data = self._load_local_data()
            plant_data = data.get('plants', {}).get(plant_name)
            return plant_data.get('current_moisture') if plant_data else None

    def get_plant_history(self, plant_name: str, hours: int = 24) -> list:
        """Get historical moisture data for a plant."""
        if self.use_firestore and self.db:
            try:
                doc_ref = self.db.collection('plants').document(plant_name)
                doc = doc_ref.get()
                if doc.exists:
                    history = doc.to_dict().get('history', [])
                    return history[:hours] if isinstance(history, list) else []
                return []
            except Exception as e:
                logger.error(f"Error reading history from Firestore: {e}")
                return []
        else:
            data = self._load_local_data()
            plant_data = data.get('plants', {}).get(plant_name)
            if plant_data and 'history' in plant_data:
                return plant_data['history'][:hours]
            return []

    def get_water_tank_status(self) -> Dict[str, Any]:
        """Get water tank status."""
        if self.use_firestore and self.db:
            try:
                doc_ref = self.db.collection('system').document('water_tank')
                doc = doc_ref.get()
                if doc.exists:
                    return doc.to_dict()
                return {}
            except Exception as e:
                logger.error(f"Error reading water tank from Firestore: {e}")
                return {}
        else:
            data = self._load_local_data()
            return data.get('water_tank', {})

    def get_all_plants(self) -> Dict[str, Any]:
        """Get all plant data."""
        if self.use_firestore and self.db:
            try:
                plants_ref = self.db.collection('plants')
                docs = plants_ref.stream()
                plants = {}
                for doc in docs:
                    plants[doc.id] = doc.to_dict()
                return plants
            except Exception as e:
                logger.error(f"Error reading plants from Firestore: {e}")
                return {}
        else:
            data = self._load_local_data()
            return data.get('plants', {})

    def update_plant_moisture(self, plant_name: str, moisture: int) -> bool:
        """Update plant moisture level."""
        if self.use_firestore and self.db:
            try:
                doc_ref = self.db.collection('plants').document(plant_name)
                doc_ref.update({
                    'current_moisture': moisture,
                    'last_updated': firestore.SERVER_TIMESTAMP
                })
                return True
            except Exception as e:
                logger.error(f"Error updating Firestore: {e}")
                return False
        else:
            try:
                data = self._load_local_data()
                if plant_name in data.get('plants', {}):
                    data['plants'][plant_name]['current_moisture'] = moisture
                    with open(self.local_data_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    return True
                return False
            except Exception as e:
                logger.error(f"Error updating local data: {e}")
                return False

    def trigger_irrigation(self, plant_name: str, duration_seconds: int) -> bool:
        """Simulate irrigation trigger."""
        logger.info(f"Simulating irrigation for {plant_name} for {duration_seconds}s")

        current_moisture = self.get_plant_moisture(plant_name)
        if current_moisture is not None:
            new_moisture = min(100, current_moisture + (duration_seconds // 10))
            return self.update_plant_moisture(plant_name, new_moisture)
        return False


simulator = FirestoreSimulator(use_firestore=os.getenv('USE_FIRESTORE', 'true').lower() == 'true')
