from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from flask import current_app, g

def get_async_engine():
    """Lazily creates and returns the async engine."""
    if 'async_engine' not in current_app.extensions:
        current_app.extensions['async_engine'] = create_async_engine(
            current_app.config['SQLALCHEMY_ASYNC_DATABASE_URI'],
            echo=current_app.config['SQLALCHEMY_ECHO'],
            poolclass=NullPool
        )
    return current_app.extensions['async_engine']

async def get_async_session():
    """Yields an async session."""
    engine = get_async_engine()
    AsyncSessionLocal = async_sessionmaker(
        bind=engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    async with AsyncSessionLocal() as session:
        yield session
