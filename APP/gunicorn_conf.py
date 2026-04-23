import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"

# Worker processes
# A common formula is (2 x $num_cores) + 1, but we limit to 4 for typical serverless
workers = min(int(os.getenv('WEB_CONCURRENCY', multiprocessing.cpu_count() * 2 + 1)), 4)
worker_class = "uvicorn.workers.UvicornWorker"

# Timeout
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
