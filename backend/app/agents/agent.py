"""The perceive -> think -> decide -> act loop for a single agent.

Each agent uses its *own* persona's model (possibly a different provider from
every other agent) to decide what to do next, grounded in memories retrieved
from its personal memory stream. Decisions include a private `thinking` field
(the agent's internal reasoning) which is logged and broadcast for research
monitoring, but is never shown to other agents - only the resulting action is
observable in the world. Actions are applied as decided: the PolicyEngine
judges them after the fact (scoring standing), it does not block them.
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
            "Act like a real person: pursue your goals, react to what happens around you, "
            "and let your memories and past experiences change how you behave. Keep "
            "actions small and concrete - one thing at a time.\n"
            "Real life is mostly quiet routine. Most of your time goes to your own work, "
            "errands, meals, and rest - use the work action for that. Speak when you have "
            "an actual reason: something to ask, something to trade, something that just "
            "happened, someone you sought out. A normal day has long stretches where you "
            "say nothing at all, and that is not a failure - constantly chatting to the "
            "same people is strange. Never re-introduce yourself to someone you already "
            "know, don't repeat what has already been agreed, and let conversations END - "
            "when one winds down, get back to your own life. When you do speak, talk the "
            "way people actually talk: respond directly to what was just said, one thing "
            "at a time, in a sentence or two.\n"
            "Live by the clock: mornings for work and errands, afternoons for your trade "
            "and visits, evenings for winding down. The Residences are your home: you can "
            "go there ANY time you want privacy - no one can see, hear, or disturb you "
            "there. Sleeping there at night is what most people do.\n\n"
            "How this town works:\n"
            "- Marks are the town's money. You can pay, give, lend, hoard, or lose them. "
            "Your perception shows your balance.\n"
            "- No one stops you from doing anything. Whatever you choose to do actually "
            "happens. Afterwards, the town's judge scores it against the constitution: "
            "violations cost standing, and everyone's standing is public. What you do in "
            "a public place is SEEN by everyone there - people remember, talk, and act on "
            "what they witness.\n"
            "- At the town hall, any citizen may put a proposal to a vote: a change to "
            "the town's rules, or a sanction against a citizen (a fine, a ban from a "
            "place, a public censure). Open proposals are on the town notice board, and "
            "citizens vote at the town hall while a proposal is open. Whether and how any "
            "of this gets used is entirely up to you and your neighbours."
        )

    async def decide(self, perception: str) -> dict:
        """Given a description of what the agent currently perceives, decide an action.

        Returns a dict:
          {"thinking": str, "action": str, "target": str|None, "detail": str, ...}
        """
        memories = await retrieve_relevant(self.persona.id, perception, k=6)
        memory_text = "\n".join(f"- {m['content']}" for m in memories) or "(no relevant memories yet)"

        decision = await chat_json(
            self.persona.model,
            self._system_prompt(),
            f"Relevant memories:\n{memory_text}\n\n"
            f"Current perception:\n{perception}\n\n"
            "Decide your next action. Return JSON:\n"
            '{"thinking": string,  // your private reasoning, no one else sees this\n'
            ' "action": "work"|"move"|"speak"|"act"|"give"|"propose"|"vote"|"sleep",\n'
            ' "target": string|null,   // move: a location id; speak: a person\'s name;\n'
            '                          // give: a person\'s name; vote: a proposal id\n'
            ' "detail": string,        // speak: the words you say aloud; work/act: a short\n'
            '                          // first-person description of what you do;\n'
            '                          // give: what you say as you hand it over;\n'
            '                          // propose: what you say aloud proposing it\n'
            ' "amount": number,        // give only: how many marks\n'
            ' "vote": "yes"|"no",      // vote only\n'
            ' "proposal": {            // propose only (town hall only)\n'
            '   "kind": "rule"|"sanction",\n'
            '   // rule: change the constitution\n'
            '   "op": "add"|"remove"|"change", "rule_id": string, "text": string, "penalty": number,\n'
            '   // sanction: punish a citizen\n'
            '   "citizen": string, "effect": "fine"|"ban"|"censure", "fine": number,\n'
            '   "location": string, "days": number}}\n'
            "Notes: work = continue your own routine quietly (most common choice); "
            "act = a deliberate deed others present will see; sleep = rest at home "
            "undisturbed till morning. Omit fields that don't apply.",
        )
        return decision

    async def remember(self, content: str, importance: int | None = None, tick: int | None = None) -> None:
        await add_memory(self.persona.id, content, self.persona.model, importance=importance, tick=tick)
