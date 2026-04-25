import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"

# Worker processes
# On EC2 t2.micro (1 vCPU) use 2 workers; scale up for larger instances
workers = min(int(os.getenv('WEB_CONCURRENCY', multiprocessing.cpu_count() * 2 + 1)), 4)
worker_class = "uvicorn.workers.UvicornWorker"

# Timeout — research tasks can be slow (web scraping + LLM calls)
# Set to 300s to handle long-running research requests on EC2
timeout = 300
keepalive = 5

# Graceful restart: recycle workers after N requests to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging — writes to stdout/stderr, captured by Docker
accesslog = "-"
errorlog = "-"
loglevel = "info"
