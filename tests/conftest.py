import os

# Ensure the TESTING environment variable is set before Django settings are loaded
os.environ['TESTING'] = 'True'
