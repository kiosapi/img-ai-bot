"""FSM states for conversational flows."""
from aiogram.fsm.state import State, StatesGroup

class GenerateStates(StatesGroup):
    waiting_prompt = State()
    waiting_negative = State()
    waiting_seed = State()
    waiting_ref_photo = State()

class EditStates(StatesGroup):
    waiting_instruction = State()
    waiting_editthis_instruction = State()  # for edit-this flow: waiting instruction after file_id loaded

class BalanceStates(StatesGroup):
    waiting_custom_amount = State()
