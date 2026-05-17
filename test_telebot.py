import telebot
try:
    telebot.types.Update.de_json('{"update_id": 1}')
    print("de_json with string WORKS")
except Exception as e:
    print(f"ERROR: {e}")
