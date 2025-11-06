# Import all models to ensure they are registered with SQLAlchemy
from .base import Base
from .user import User, UserCreate, UserUpdate, UserLogin, UserResponse, UserWithPermissions
from .website import Website, WebsiteCreate, WebsiteUpdate, WebsiteResponse, WebsiteWithStats
from .file_binary import FileBinary
from .file_metadata import FileMetadata, FileMetadataCreate, FileMetadataUpdate, FileMetadataResponse
from .user_file_access import UserFileAccess, UserFileAccessCreate, UserFileAccessUpdate, UserFileAccessResponse
from .query_log import QueryLog, QueryLogCreate, QueryLogResponse
from .chat_tracking import ChatSession, ChatQuery, ChatSessionCreate, ChatQueryCreate, ChatMessage, ChatMessageCreate
from .vector_database import VectorDatabase, VectorDatabaseCreate, VectorDatabaseUpdate, VectorDatabaseResponse
from .system_prompt import SystemPrompt, SystemPromptCreate, SystemPromptUpdate, SystemPromptResponse
from .collection import Collection, CollectionUser, CollectionWebsite
from .plugin_integration import PluginIntegration
from .activity_log import ActivityLog
from .activity_stats import ActivityStats

__all__ = [
    "Base",
    "User", 
    "Website",
    "FileBinary",
    "FileMetadata",
    "UserFileAccess", 
    "QueryLog",
    "ChatSession",
    "ChatQuery",
    "VectorDatabase",
    "SystemPrompt",
    "Collection",
    "CollectionUser",
    "CollectionWebsite",
    "PluginIntegration",
    "ActivityLog",
    "ActivityStats",
]