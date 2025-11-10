"""
Uvicorn configuration for production/Docker deployment
Handles large file uploads and proper request limits
"""

# Uvicorn configuration
config = {
    "host": "0.0.0.0",
    "port": 8000,
    "workers":4 ,  # Increased from 1 to 4 workers for better concurrency
    "limit_concurrency": 1000,
    "limit_max_requests": 10000,
    "timeout_keep_alive": 5,
    "timeout_notify": 30,
    "timeout_graceful_shutdown": 30,
    # No explicit body size limit - handled by FastAPI/application layer
    "log_level": "info",
    "access_log": True,
    "use_colors": True,
}

# For production with multiple workers
production_config = {
    **config,
    "workers": 4,  # Same as config now
    "log_level": "warning",
}