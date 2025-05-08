from dotenv import load_dotenv
import os

# 환경 변수 로드
load_dotenv()

# Gunicorn 설정
bind = "0.0.0.0:5000"
workers = 4
worker_class = "eventlet"
worker_connections = 1000
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info" 