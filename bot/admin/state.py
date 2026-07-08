"""Admin panel FSM holatlari."""

from aiogram.fsm.state import State, StatesGroup


class AdminFSM(StatesGroup):
    user_search = State()      # foydalanuvchi qidiruv so'rovини kutish
    dm_text = State()          # foydalanuvchiga xabar matnini kutish (data: target)
    ban_reason = State()       # ban sababini kutish (data: target, kind, until)
    broadcast_compose = State()  # broadcast kontentини kutish
    broadcast_schedule = State() # broadcast vaqtini kutish (data: msg)
    add_admin = State()        # yangi admin ID (data: role)
    setting_value = State()    # sozlama qiymatini kutish (data: key)
    fs_add = State()           # majburiy obuna: @username / chat id / forward kutish
