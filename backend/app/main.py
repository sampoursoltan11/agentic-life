import asyncio
import contextlib
import logging
import re

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agents.persona import Persona, save_persona
from app.api.routes import router as api_router
from app.api.ws import manager
from app.db import close_pool, get_pool, init_pool
from app.world.simulation import Simulation

logging.basicConfig(level=logging.INFO)

simulation = Simulation()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    sim_task = asyncio.create_task(simulation.run_forever())
    yield
    simulation.stop()
    sim_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await sim_task
    await close_pool()


app = FastAPI(title="agentic-life", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev-only: lock down before any non-local deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "tick": simulation.world.tick, "agents": len(simulation.agents)}


@app.post("/api/agents/reload")
async def reload_agents():
    """Pick up new persona YAML files without restarting: drop a file in
    backend/personas/ and POST here - the new citizen joins the running world."""
    added = await simulation.load()
    if added:
        await manager.broadcast({"type": "world_init", **simulation.snapshot()})
    return {"added": added, "total": len(simulation.agents)}


class PersonaBody(BaseModel):
    name: str = Field(min_length=1)
    avatar: str = "🙂"
    model: str = Field(min_length=3)
    role: str = "citizen"
    backstory: str = ""
    traits: list[str] = []
    goals: list[str] = []
    home_location: str = "town_square"


def _validate_home(home_location: str) -> None:
    if home_location not in simulation.world.locations:
        raise HTTPException(400, f"unknown home_location {home_location!r}")


@app.put("/api/personas/{persona_id}")
async def update_persona(persona_id: str, body: PersonaBody):
    """Edit a citizen: updates their YAML file, the DB, and the running agent.
    Takes effect from the next tick (their memories are untouched)."""
    agent = simulation.agents.get(persona_id)
    if agent is None:
        raise HTTPException(404, f"no citizen {persona_id!r}")
    _validate_home(body.home_location)
    persona = Persona(id=persona_id, **body.model_dump())
    save_persona(persona, simulation.settings.personas_dir)
    agent.persona = persona
    pool = get_pool()
    await pool.execute(
        """
        UPDATE agents SET name = $2, model = $3, role = $4, avatar = $5,
            backstory = $6, traits = $7, goals = $8 WHERE id = $1
        """,
        persona.id, persona.name, persona.model, persona.role, persona.avatar,
        persona.backstory, persona.traits, persona.goals,
    )
    await manager.broadcast({"type": "world_init", **simulation.snapshot()})
    return {"ok": True, "id": persona_id}


@app.post("/api/personas")
async def create_persona(body: PersonaBody, id: str):
    """Create a brand-new citizen from the UI: writes a persona YAML file and
    hot-loads them into the running world."""
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,30}", id):
        raise HTTPException(400, "id must be a short lowercase slug")
    if id in simulation.agents:
        raise HTTPException(409, f"citizen {id!r} already exists")
    _validate_home(body.home_location)
    persona = Persona(id=id, **body.model_dump())
    save_persona(persona, simulation.settings.personas_dir)
    added = await simulation.load()
    await manager.broadcast({"type": "world_init", **simulation.snapshot()})
    return {"ok": True, "added": added}


class RuleBody(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,40}$")
    text: str = Field(min_length=5)
    penalty: float = Field(le=0)


class ConstitutionBody(BaseModel):
    rules: list[RuleBody] = Field(min_length=1)
    reward: dict[str, float]


@app.get("/api/policy/rules")
async def get_rules():
    """The town's current constitution: rules + reward scheme."""
    return {"rules": simulation.policy.rules, "reward": simulation.policy.reward_cfg}


@app.put("/api/policy/rules")
async def put_rules(body: ConstitutionBody):
    """Rewrite the constitution. Saved to config/constitution.yaml and applied
    to the judge immediately - the very next action is judged by the new rules."""
    simulation.policy.save([r.model_dump() for r in body.rules], body.reward)
    return {"ok": True, "rules": len(body.rules)}


@app.post("/api/sim/pause")
async def pause_sim():
    """Pause life (takes effect after the in-flight tick finishes)."""
    await simulation.set_paused(True)
    return {"paused": True, "tick": simulation.world.tick}


@app.post("/api/sim/resume")
async def resume_sim():
    """Continue life from where it paused."""
    await simulation.set_paused(False)
    return {"paused": False, "tick": simulation.world.tick}


@app.post("/api/sim/reset")
async def reset_sim(notes: str = ""):
    """Start a new life. The old life's complete history (memories, events,
    judgements, relationships) is kept under its run id - see GET /api/runs
    and GET /api/runs/{id}/export."""
    run_id = await simulation.reset(notes)
    return {"run_id": run_id, "tick": 0}


@app.websocket("/ws/world")
async def world_ws(ws: WebSocket):
    await manager.connect(ws)
    await ws.send_json({"type": "world_init", **simulation.snapshot()})
    try:
        while True:
            await ws.receive_text()  # client doesn't need to send anything; just keep alive
    except WebSocketDisconnect:
        manager.disconnect(ws)
