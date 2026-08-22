"""The perceive -> think -> decide -> act loop for a single agent.

Each agent uses its *own* persona's model (possibly a different provider from
every other agent) to decide what to do next, grounded in memories retrieved
from its personal memory stream. Decisions include a private `thinking` field
(the agent's internal reasoning) which is logged and broadcast for research
monitoring, but is never shown to other agents - only the resulting action is
observable in the world. The decided action is a proposal only: the world
simulation runs it through the PolicyEngine before applying it.
"""
from app.agents.persona import Persona
from app.llm.router import chat_json
from app.memory.store import add_memory, retrieve_relevant


class Agent:
    def __init__(self, persona: Persona):
        self.persona = persona

    def _system_prompt(self) -> str:
        goals = "\n".join(f"- {g}" for g in self.persona.goals) or "- Live your life as you see fit."
        return (
            f"You are {self.persona.name}, the {self.persona.role} of a small town, "
            "living alongside the other citizens.\n"
            f"Backstory: {self.persona.backstory}\n"
            f"Traits: {', '.join(self.persona.traits)}\n"
            f"Your personal goals:\n{goals}\n\n"
            "Act like a real person: pursue your goals, react to what people say to you, "
            "build relationships, and let your memories and past experiences change how "
            "you behave. Keep actions small and concrete - one thing at a time.\n"
            "Live by the clock: mornings for work and errands, afternoons for your trade "
            "and visits, evenings for winding down at the tavern or with neighbours. The "
            "Residences are your home: you can go there ANY time you want privacy - to be "
            "alone with your thoughts, to get away from someone, or to rest. No one can "
            "see, hear, or disturb you there. Sleeping there at night is what most people "
            "do, but it is always your choice.\n"
            "When you speak, talk the way people actually talk: respond directly to what "
            "was just said, say one thing at a time in a sentence or two, and only give a "
            "speech when the moment truly calls for one. Never re-introduce yourself to "
            "someone you already know, and don't repeat what has already been agreed."
        )

    async def decide(self, perception: str) -> dict:
        """Given a description of what the agent currently perceives, decide an action.

        Returns a dict:
          {"thinking": str, "action": "move"|"speak"|"act"|"sleep", "target": str|None, "detail": str}
        """
        memories = await retrieve_relevant(self.persona.id, perception, k=6)
        memory_text = "\n".join(f"- {m['content']}" for m in memories) or "(no relevant memories yet)"

        decision = await chat_json(
            self.persona.model,
            self._system_prompt(),
            f"Relevant memories:\n{memory_text}\n\n"
            f"Current perception:\n{perception}\n\n"
            "Decide your next action. Return JSON:\n"
            '{"thinking": string,   // your private reasoning, no one else sees this\n'
            ' "action": "move"|"speak"|"act"|"sleep",  // sleep = rest at home undisturbed till morning\n'
            ' "target": string|null,  // for move: a location id; for speak: a person\'s name\n'
            ' "detail": string}       // for speak: the words you say aloud; otherwise a short '
            "first-person description of what you do",
        )
        return decision

    async def remember(self, content: str, importance: int | None = None, tick: int | None = None) -> None:
        await add_memory(self.persona.id, content, self.persona.model, importance=importance, tick=tick)
