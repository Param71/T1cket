import sys
import os

# 1. Add the current directory to the system path
sys.path.append(os.getcwd())

# 2. Import your Flask application 'app' from 'app.py'
from app import app as application

# AlwaysData expects the entry point to be called 'application'
