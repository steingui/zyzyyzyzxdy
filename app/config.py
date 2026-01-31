import os

class Config:
    # Database Configuration
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable must be set")
        
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Cache Configuration
    CACHE_TYPE = os.getenv('CACHE_TYPE', 'RedisCache')
    CACHE_REDIS_URL = os.getenv('CACHE_REDIS_URL', 'redis://redis:6379/0')
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Security Configuration
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable must be set. Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'")
