"""FSM states for conversational flows (replaces ForceReply to fix sticky keyboard bug)."""
from aiogram.fsm.state import State, StatesGroup


class GenerateStates(StatesGroup):
    waiting_prompt = State()


class EditStates(StatesGroup):
    waiting_instruction = State()
    waiting_editthis_instruction = State()  # for edit-this flow: waiting instruction после file_id loaded


class BalanceStates(StatesGroup):
    waiting_custom_amount = State()
