# app/services/activity_tracker.py

import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ActivityTracker:
    def __init__(self, storage_dir: str = "activity_logs"):
        """Initialize activity tracker with local storage"""
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.activities_file = self.storage_dir / "activities.json"
        self.stats_file = self.storage_dir / "stats.json"
        
        # Initialize files if they don't exist
        self._init_files()
    
    def _init_files(self):
        """Initialize activity and stats files if they don't exist"""
        if not self.activities_file.exists():
            self._save_activities([])
        
        if not self.stats_file.exists():
            self._save_stats({
                "total_files_uploaded": 0,
                "total_chat_sessions": 0,
                "total_queries": 0,
                "last_document_upload": None,
                "last_chat_session": None,
                "last_activity": None
            })
    
    def _load_activities(self) -> List[Dict]:
        """Load activities from local storage"""
        try:
            with open(self.activities_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_activities(self, activities: List[Dict]):
        """Save activities to local storage"""
        try:
            with open(self.activities_file, 'w', encoding='utf-8') as f:
                json.dump(activities, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Failed to save activities: {e}")
    
    def _load_stats(self) -> Dict:
        """Load stats from local storage"""
        try:
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_stats(self, stats: Dict):
        """Save stats to local storage"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Failed to save stats: {e}")
    
    def log_activity(self, activity_type: str, user: str, details: Dict = None, metadata: Dict = None):
        """Log a new activity"""
        timestamp = datetime.now(timezone.utc)
        
        activity = {
            "id": f"{timestamp.timestamp()}_{activity_type}",
            "type": activity_type,
            "user": user,
            "timestamp": timestamp.isoformat(),
            "details": details or {},
            "metadata": metadata or {}
        }
        
        # Load existing activities
        activities = self._load_activities()
        
        # Add new activity
        activities.append(activity)
        
        # Keep only last 1000 activities to prevent file from growing too large
        if len(activities) > 1000:
            activities = activities[-1000:]
        
        # Save activities
        self._save_activities(activities)
        
        # Update stats
        self._update_stats(activity_type, timestamp)
        
        logger.info(f"Activity logged: {activity_type} by {user}")
    
    def _update_stats(self, activity_type: str, timestamp: datetime):
        """Update statistics based on activity type"""
        stats = self._load_stats()
        
        # Initialize counters if they don't exist
        if "total_files_uploaded" not in stats:
            stats["total_files_uploaded"] = 0
        if "total_chat_sessions" not in stats:
            stats["total_chat_sessions"] = 0
        if "total_queries" not in stats:
            stats["total_queries"] = 0
        
        # Update counters based on activity type
        if activity_type == "file_upload":
            stats["total_files_uploaded"] += 1
            stats["last_document_upload"] = timestamp.isoformat()
        elif activity_type == "chat_session_start":
            stats["total_chat_sessions"] += 1
            stats["last_chat_session"] = timestamp.isoformat()
        elif activity_type == "chat_query":
            stats["total_queries"] += 1
        
        # Update last activity
        stats["last_activity"] = timestamp.isoformat()
        
        # Save updated stats
        self._save_stats(stats)
    
    def get_recent_activities(self, limit: int = 50) -> List[Dict]:
        """Get recent activities"""
        activities = self._load_activities()
        return sorted(activities, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    def get_activities_by_type(self, activity_type: str, limit: int = 50) -> List[Dict]:
        """Get activities filtered by type"""
        activities = self._load_activities()
        filtered = [a for a in activities if a["type"] == activity_type]
        return sorted(filtered, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    def get_activities_by_user(self, user: str, limit: int = 50) -> List[Dict]:
        """Get activities filtered by user"""
        activities = self._load_activities()
        filtered = [a for a in activities if a["user"] == user]
        return sorted(filtered, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    def get_stats(self) -> Dict:
        """Get current statistics"""
        return self._load_stats()
    
    def get_activity_summary(self) -> Dict:
        """Get a summary of recent activities with counts"""
        activities = self._load_activities()
        stats = self._load_stats()
        
        # Count recent activities by type (last 24 hours)
        recent_cutoff = datetime.now(timezone.utc).timestamp() - (24 * 60 * 60)
        recent_activities = [a for a in activities if datetime.fromisoformat(a["timestamp"].replace('Z', '+00:00')).timestamp() > recent_cutoff]
        
        recent_counts = {}
        for activity in recent_activities:
            activity_type = activity["type"]
            recent_counts[activity_type] = recent_counts.get(activity_type, 0) + 1
        
        return {
            "stats": stats,
            "recent_24h": recent_counts,
            "total_activities": len(activities)
        }
    
    def clear_activities(self, days_to_keep: int = 30):
        """Clear old activities, keeping only recent ones"""
        cutoff_date = datetime.now(timezone.utc).timestamp() - (days_to_keep * 24 * 60 * 60)
        
        activities = self._load_activities()
        filtered_activities = [
            a for a in activities 
            if datetime.fromisoformat(a["timestamp"].replace('Z', '+00:00')).timestamp() > cutoff_date
        ]
        
        self._save_activities(filtered_activities)
        logger.info(f"Cleared activities older than {days_to_keep} days")

# Global activity tracker instance
activity_tracker = ActivityTracker()
