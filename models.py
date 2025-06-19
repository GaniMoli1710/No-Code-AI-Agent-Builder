from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, Text, DateTime, func, Boolean
from passlib.context import CryptContext
import os

# Load environment variables (ensure this runs early or in app.py)
from dotenv import load_dotenv
load_dotenv()
os.makedirs("/tmp", exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./tmp/app.db") # Default to local file
print(f"DEBUG: DATABASE_URL being used: {DATABASE_URL}") 
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

engine = create_async_engine(DATABASE_URL, echo=False) # echo=True for SQL logs
Base = declarative_base()
AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

    def verify_password(self, password: str):
        return pwd_context.verify(password, self.hashed_password)

class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True) # Foreign key to User
    name = Column(String, index=True)
    purpose = Column(Text)
    tone = Column(String) # e.g., "Formal", "Friendly", "Professional"
    fallback_message = Column(Text, default="I'm sorry, I don't have enough information to answer that.")
    knowledge_base_path = Column(String, nullable=True) # Path to agent-specific ChromaDB dir
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) # Create tables if they don't exist

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Helper for password hashing
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
