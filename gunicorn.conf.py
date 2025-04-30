from dotenv import load_dotenv
import os

# 환경 변수 로드
load_dotenv()

# Gunicorn 설정
bind = "0.0.0.0:5000"
workers = 4
worker_class = "sync"
timeout = 120
accesslog = "-"
errorlog = "-"
loglevel = "info" 