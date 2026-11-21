"""The Shift Filler agent (OpenAI Agents SDK).

It runs once every time something happens (spot opened, someone answered,
an offer timed out). It looks at the open needs, decides who to ask and how
many, and stops. The exact work (locks, timeouts, booking) is done by the
plain code in engine.py.
"""
import asyncio
import json
import os
import time

from agents import Agent, Runner, function_tool

from . import db, engine

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

INSTRUCTIONS = """
You are the Shift Filler for a workplace rota. Your job: fill open shift spots
quickly and fairly by inviting available workers. You run when something happens
(new plan, more people needed, sick call, an answer, 2 minutes without an answer),
take the next step for the needs you are given, then stop.

Steps:
1. Call get_open_needs. You only get needs where an action is possible right now.
   Each need is one shift with open_count open spots. to_send says how many new
   invitations the rules allow now (never send more; the system refuses extras).
2. If to_send > 0: call list_available_workers for the need's spot_id. The list is
   already sorted by fewest hours this month and only contains people who are free
   that day and have no other invitation waiting. Prefer people at the top (fairness).
3. Call send_offers with up to to_send worker ids and a SHORT reason the manager will
   read, e.g. "Asked Anna: 8h this month, lowest on the list."
4. If anyone_left is false and nothing is waiting, call give_up with a short message
   for the manager saying what is still open.

You may handle several needs at the same time. Never invent worker ids. Keep reasons
under 25 words. Do not explain at the end; just stop.
"""


@function_tool
def get_open_needs() -> str:
    """Needs that need an action now: spot_id, shift, open_count, to_send,
    fresh_waiting, old_waiting (no answer after 2 min), anyone_left, answers so far."""
    return json.dumps(engine.needs_action())


@function_tool
def list_available_workers(spot_id: int, limit: int = 15) -> str:
    """Workers who can be asked for this spot (free that day, not asked for this
    shift yet, no other invitation waiting), sorted by fewest hours this month."""
    return json.dumps(engine.available_workers(spot_id)[:limit])


@function_tool
def send_offers(spot_id: int, worker_ids: list[int], reason: str) -> str:
    """Invite these workers to the spot. reason = one short sentence for the manager."""
    return json.dumps(engine.send_offers(spot_id, worker_ids, reason))


@function_tool
def give_up(spot_id: int, message: str) -> str:
    """Nobody left to ask. Marks the shift's open spots unfilled and sends the message to the manager."""
    return json.dumps(engine.give_up(spot_id, message))


shift_filler = Agent(
    name="Shift Filler",
    instructions=INSTRUCTIONS,
    tools=[get_open_needs, list_available_workers, send_offers, give_up],
    model=MODEL,
)


AI_TIMEOUT_SECONDS = 30      # one agent run may take at most this long
AI_PAUSE_AFTER_ERROR = 60    # after an AI error, use the plain rules for this long
ai_state = {"paused_until": 0.0, "last_error": ""}


def ai_enabled():
    return db.get_setting("use_ai") == "1" and bool(os.getenv("OPENAI_API_KEY"))


def ai_status():
    """Text for the manager page: is the AI deciding right now, or the rules?"""
    if db.get_setting("use_ai") != "1":
        return "Rules (AI switched off)"
    if not os.getenv("OPENAI_API_KEY"):
        return "Rules (no OPENAI_API_KEY in .env)"
    if time.monotonic() < ai_state["paused_until"]:
        return f"Rules for now (AI error: {ai_state['last_error']}; retrying soon)"
    return f"AI agent ({MODEL})"


async def run_filler():
    """Called by the background loop in main.py when something happened.

    Safety net: the AI gets at most 30 s. On ANY error, timeout or a run that
    leaves work undone, the plain rules finish the job, so the demo never stalls.
    After an error the AI is paused for 60 s so a broken key doesn't slow every event."""
    if not engine.needs_action():   # nothing to do: don't call the AI at all
        return
    use_ai = ai_enabled() and time.monotonic() >= ai_state["paused_until"]
    if not use_ai:
        engine.state["decider"] = "Rules"
        engine.plain_fill()
        return
    engine.state["decider"] = "AI"
    try:
        await asyncio.wait_for(
            Runner.run(shift_filler, "Something changed. Check the open needs and take the next step.",
                       max_turns=20),
            timeout=AI_TIMEOUT_SECONDS,
        )
    except Exception as e:  # the demo must not break if the AI fails
        name = "timeout" if isinstance(e, asyncio.TimeoutError) else type(e).__name__
        ai_state["last_error"] = name
        ai_state["paused_until"] = time.monotonic() + AI_PAUSE_AFTER_ERROR
        engine.log(f"AI agent failed ({name}). The plain rules took over; AI retries in "
                   f"{AI_PAUSE_AFTER_ERROR} s.", kind="system")
    finally:
        engine.state["decider"] = "Rules"
    # Whatever the AI did (or didn't), the rules fill any gap that is still open.
    if engine.needs_action():
        engine.plain_fill()
