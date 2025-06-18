from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

from models import (
    init_db, AsyncSessionLocal, User, Agent, get_password_hash, pwd_context
)
from services.llm_service import llm_service

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change for production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AgentConfig(BaseModel):
    name: str
    purpose: str
    tone: str
    fallback_message: str

class AgentRequest(BaseModel):
    agent_id: int
    agent_config: AgentConfig
    user_query: str

@app.on_event("startup")
async def on_startup():
    await init_db()
    os.makedirs(llm_service.base_vector_store_path, exist_ok=True)

@app.post("/register")
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == request.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists.")
    hashed_password = get_password_hash(request.password)
    new_user = User(email=request.email, hashed_password=hashed_password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {"id": new_user.id, "email": new_user.email}

@app.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    if user and pwd_context.verify(request.password, user.hashed_password):
        return {"id": user.id, "email": user.email}
    raise HTTPException(status_code=401, detail="Invalid credentials.")

@app.get("/agents/{user_id}")
async def list_agents(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.user_id == user_id))
    agents = result.scalars().all()
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "purpose": agent.purpose,
            "tone": agent.tone,
            "fallback_message": agent.fallback_message,
        }
        for agent in agents
    ]

@app.post("/agent")
async def save_agent(
    user_id: int,
    agent: AgentConfig,
    agent_id: int = None,
    db: AsyncSession = Depends(get_db)
):
    if agent_id:
        db_agent = await db.get(Agent, agent_id)
        if db_agent and db_agent.user_id == user_id:
            db_agent.name = agent.name
            db_agent.purpose = agent.purpose
            db_agent.tone = agent.tone
            db_agent.fallback_message = agent.fallback_message
            db.add(db_agent)
            await db.commit()
            await db.refresh(db_agent)
            return {"id": db_agent.id}
        raise HTTPException(status_code=404, detail="Agent not found or not authorized.")
    else:
        new_agent = Agent(
            user_id=user_id,
            name=agent.name,
            purpose=agent.purpose,
            tone=agent.tone,
            fallback_message=agent.fallback_message,
        )
        db.add(new_agent)
        await db.commit()
        await db.refresh(new_agent)
        return {"id": new_agent.id}

@app.post("/chat")
async def chat_with_agent(request: AgentRequest):
    try:
        response = await llm_service.get_agent_response(
            agent_id=request.agent_id,
            agent_config=request.agent_config.dict(),
            user_query=request.user_query
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload_kb/")
async def upload_kb(agent_id: int, file: UploadFile = File(...)):
    upload_dir = "data/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    try:
        await llm_service.process_knowledge_base(agent_id, file_path)
        os.remove(file_path)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}