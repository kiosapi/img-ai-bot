"""FSM states for conversational flows (replaces ForceReply to fix sticky keyboard bug)."""
from aiogram.fsm.state import State, StatesGroup


class GenerateStates(StatesGroup):
    waiting_prompt = State()


class EditStates(StatesGroup):
    waiting_instruction = State()


class BalanceStates(StatesGroup):
    waiting_custom_amount = State()
