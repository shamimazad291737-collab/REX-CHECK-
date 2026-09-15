import os
from bson.objectid import ObjectId
from pymongo import MongoClient
import telebot
from telebot.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

# আপনার দেওয়া MongoDB URI এবং সাথে ডেটাবেজের নাম 'telegram_bot' যুক্ত করা হলো
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://shamimazad291736_db_user:CwJ0XbyRhDrRfgRJ@cluster0.mswnw5q.mongodb.net/telegram_bot?retryWrites=true&w=majority&appName=Cluster0",
)

bot = telebot.TeleBot(TOKEN)

# মঙ্গোডিবি কানেকশন
client = MongoClient(MONGO_URI)
db = client[
    "telegram_bot"
]  # ডেটাবেজ সঠিকভাবে ডিক্লেয়ার করা হলো যাতে ক্র্যাশ না করে
users_collection = db["users"]
numbers_collection = db["numbers"]
settings_collection = db["settings"]
purchase_collection = db["purchase_history"]
deposits_collection = db["deposits"]


def get_setting(key, default_val):
  setting = settings_collection.find_one({"key": key})
  return setting["value"] if setting else default_val


def set_setting(key, val):
  settings_collection.update_one(
      {"key": key}, {"$set": {"value": val}}, upsert=True
  )


# ==================== মেইন রিপ্লাই কিবোর্ড (নিচের বাটন) ====================
def main_menu_markup(user_id):
  markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  markup.add(
      KeyboardButton("🛍️ বাই নাম্বার"),
      KeyboardButton("👤 আমার প্রোফাইল"),
      KeyboardButton("💰 ডিপোজিট"),
      KeyboardButton("📜 আমার হিস্টরি"),
      KeyboardButton("🛠️ সাপোর্ট"),
  )
  if user_id == ADMIN_ID:
    markup.add(
        KeyboardButton("⚙️ অ্যাডমিন প্যানেল")
    )  # অ্যাডমিন প্যানেল বাটন যুক্ত করা হলো
  return markup


# ==================== /start কমান্ড ====================
@bot.message_handler(commands=["start"])
def send_welcome(message):
  user_id = message.from_user.id
  name = message.from_user.first_name
  username = message.from_user.username or "No Username"

  user = users_collection.find_one({"user_id": user_id})
  if user and user.get("is_banned", 0) == 1:
    bot.reply_to(message, "⚠️ আপনি এই বট থেকে ব্লক বা ব্যান হয়েছেন!")
    return

  if not user:
    users_collection.insert_one({
        "user_id": user_id,
        "name": name,
        "username": username,
        "balance": 0.0,
        "total_deposit": 0.0,
        "numbers_bought": 0,
        "is_banned": 0,
    })

  welcome_text = get_setting(
      "welcome_text",
      "✨ **স্বাগতম!** আপনার প্রয়োজনীয় অপশনটি নিচের কিবোর্ড থেকে বেছে নিন:",
  )
  bot.send_message(
      message.chat.id,
      welcome_text,
      reply_markup=main_menu_markup(user_id),
      parse_mode="Markdown",
  )


user_states = {}


# ==================== টেক্সট মেসেজ ও মেনু হ্যান্ডলার ====================
@bot.message_handler(
    func=lambda message: message.text
    in [
        "🛍️ বাই নাম্বার",
        "👤 আমার প্রোফাইল",
        "💰 ডিপোজিট",
        "📜 আমার হিস্টরি",
        "🛠️ সাপোর্ট",
        "⚙️ অ্যাডমিন প্যানেল",
    ]
)
def handle_text_menu(message):
  user_id = message.from_user.id
  text = message.text
  user_states.pop(user_id, None)

  if text == "🛍️ বাই নাম্বার":
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🛒 বাই সিঙ্গেল নাম্বার", callback_data="buy_single"),
        InlineKeyboardButton("🛒 বাই মাল্টিপল নাম্বার", callback_data="buy_multi"),
    )
    bot.send_message(
        message.chat.id,
        "📦 **নাম্বার ক্রয়ের ক্যাটাগরি সিলেক্ট করুন:**",
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif text == "👤 আমার প্রোফাইল":
    user = users_collection.find_one({"user_id": user_id})
    if not user:
      bot.send_message(message.chat.id, "❌ ডাটা পাওয়া যায়নি। /start লিখুন।")
      return

    profile_text = (
        f"👤 **আপনার প্রোফাইল বিবরণী:**\n\n"
        f"🆔 ইউজার আইডি: `{user_id}`\n"
        f"📛 নাম: {user.get('name', 'N/A')}\n"
        f"💰 কারেন্ট ব্যালেন্স: ${user.get('balance', 0.0):.2f} USD\n"
        f"💵 মোট ডিপোজিট: ${user.get('total_deposit', 0.0):.2f} USD\n"
        f"🛒 মোট কেনা নাম্বার: {user.get('numbers_bought', 0)} টি"
    )
    bot.send_message(message.chat.id, profile_text, parse_mode="Markdown")

  elif text == "💰 ডিপোজিট":
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("💳 বিকাশ", callback_data="dep_bkash"),
        InlineKeyboardButton("📱 নগদ", callback_data="dep_nagad"),
        InlineKeyboardButton("🪙 বাইন্যান্স", callback_data="dep_binance"),
    )
    bot.send_message(
        message.chat.id,
        "💰 **ডিপোজিট সেকশন:**\nরেট: ১ ডলার ($1) = ১২৮ টাকা (BDT)\nনিচের পেমেন্ট মাধ্যমটি সিলেক্ট করুন:",
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif text == "📜 আমার হিস্টরি":
    history = list(purchase_collection.find({"user_id": user_id}).limit(10))
    if not history:
      bot.send_message(message.chat.id, "📜 আপনার কোনো ক্রয়ের হিস্টরি নেই।")
    else:
      h_text = "📜 **আপনার সাম্প্রতিক কেনাকাটার ইতিহাস:**\n\n"
      for h in history:
        h_text += (
            f"• নাম্বার: `{h['number']}` | Link: {h.get('link','N/A')} | OTP:"
            f" {h['otp']}\n"
        )
      bot.send_message(message.chat.id, h_text, parse_mode="Markdown")

  elif text == "🛠️ সাপোর্ট":
    support_username = get_setting("support_username", "@YourSupportAdmin")
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "🛠️ লাইভ সাপোর্টে যোগাযোগ করুন",
            url=f"https://t.me/{support_username.replace('@','')}",
        )
    )
    bot.send_message(
        message.chat.id,
        "🛠️ কোনো সমস্যা বা সাহায্যের জন্য নিচের লিংকে যোগাযোগ করুন:",
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif text == "⚙️ অ্যাডমিন প্যানেল" and user_id == ADMIN_ID:
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "👥 ইউজার ম্যানেজমেন্ট ও হিস্টরি", callback_data="adm_users"
        ),
        InlineKeyboardButton(
            "📊 সব ইউজারের ক্রয়ের হিস্টরি", callback_data="adm_all_history"
        ),
        InlineKeyboardButton(
            "⚙️ পেমেন্ট অ্যাকাউন্ট ও রেট সেটআপ", callback_data="adm_set_payment"
        ),
        InlineKeyboardButton(
            "📁 নাম্বার ফাইল আপলোড নির্দেশনা", callback_data="adm_upload_help"
        ),
    )
    bot.send_message(
        message.chat.id,
        "⚙️ **অ্যাডমিন কন্ট্রোল প্যানেল:**",
        reply_markup=markup,
        parse_mode="Markdown",
    )


# ==================== ইনলাইন কলব্যাক হ্যান্ডলার ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
  user_id = call.from_user.id

  if call.data.startswith("dep_"):
    method = call.data.split("_")[1].upper()
    user_states[user_id] = {"step": "waiting_amount", "method": method}
    bot.send_message(
        call.message.chat.id,
        f"💵 আপনি **{method}** সিলেক্ট করেছেন।\nকত ডলার ($) ডিপোজিট করতে চান তার পরিমাণ সংখ্যায় লিখুন (যেমন: 5 বা 10):",
        parse_mode="Markdown",
    )
    bot.answer_callback_query(call.id)

  elif call.data == "buy_single":
    num_data = numbers_collection.find_one({"is_sold": False})
    if not num_data:
      bot.answer_callback_query(
          call.id,
          "❌ দুঃখিত, বর্তমানে কোনো সিঙ্গেল নাম্বার স্টকে নেই!",
          show_alert=True,
      )
      return

    user = users_collection.find_one({"user_id": user_id})
    price_usd = 0.5
    if user["balance"] < price_usd:
      bot.answer_callback_query(
          call.id,
          f"❌ পর্যাপ্ত ব্যালেন্স নেই! প্রয়োজন: ${price_usd} USD",
          show_alert=True,
      )
      return

    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": -price_usd, "numbers_bought": 1}},
    )
    numbers_collection.update_one(
        {"_id": num_data["_id"]},
        {"$set": {"is_sold": True, "buyer_id": user_id}},
    )

    p_id = purchase_collection.insert_one({
        "user_id": user_id,
        "number": num_data["number"],
        "link": num_data.get("link", "N/A"),
        "otp": "Pending",
        "type": "Single",
    }).inserted_id

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🔄 চেক ওটিপি", callback_data=f"chk_otp_{p_id}")
    )

    msg = (
        f"✅ **সফলভাবে নাম্বার ক্রয় করা হয়েছে!**\n\n"
        f"📱 নাম্বার: `{num_data['number']}`\n"
        f"🔗 লিংক: {num_data.get('link', 'N/A')}\n\n"
        f"ওটিপি দেখতে নিচে 'চেক ওটিপি' বাটনে ক্লিক করুন।"
    )
    bot.send_message(
        call.message.chat.id, msg, reply_markup=markup, parse_mode="Markdown"
    )
    bot.answer_callback_query(call.id)

  elif call.data == "adm_all_history" and user_id == ADMIN_ID:
    all_purchases = list(purchase_collection.find({}).sort("_id", -1).limit(15))
    if not all_purchases:
      bot.answer_callback_query(call.id, "কোনো হিস্টরি নেই!")
      return

    text = "📊 **সকল ইউজারের সাম্প্রতিক ক্রয়ের হিস্টরি:**\n\n"
    for p in all_purchases:
      text += (
          f"• User: `{p['user_id']}` | No: `{p['number']}` | Link:"
          f" {p.get('link','N/A')} | OTP: {p['otp']}\n"
      )
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, parse_mode="Markdown"
    )

  elif call.data == "adm_set_payment" and user_id == ADMIN_ID:
    bkash_num = get_setting("bkash_num", "01XXXXXXXXX")
    nagad_num = get_setting("nagad_num", "01XXXXXXXXX")
    binance_uid = get_setting("binance_uid", "XXXXXXXX")

    text = (
        f"⚙️ **বর্তমান পেমেন্ট ডিটেইলস:**\n"
        f"• বিকাশ নম্বর: `{bkash_num}`\n"
        f"• নগদ নম্বর: `{nagad_num}`\n"
        f"• বাইন্যান্স UID: `{binance_uid}`\n\n"
        f"পরিবর্তন করতে কমান্ড ব্যবহার করুন:\n"
        f"`/setbkash নম্বর` | `/setnagad নম্বর` | `/setbinance UID`"
    )
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, parse_mode="Markdown"
    )

  elif call.data == "adm_users" and user_id == ADMIN_ID:
    users = list(users_collection.find({}).limit(20))
    markup = InlineKeyboardMarkup(row_width=1)
    for u in users:
      markup.add(
          InlineKeyboardButton(
              f"👤 {u.get('name')} (ID: {u['user_id']}) - কেনাকাটা:"
              f" {u.get('numbers_bought',0)}টি",
              callback_data=f"adm_u_detail_{u['user_id']}",
          )
      )
    bot.edit_message_text(
        "👥 **সকল ইউজারের তালিকা ও হিস্টরি:** (ডিটেইলস দেখতে ক্লিক করুন)",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif call.data.startswith("adm_u_detail_") and user_id == ADMIN_ID:
    target_id = int(call.data.split("_")[3])
    u_data = users_collection.find_one({"user_id": target_id})
    purchases = list(purchase_collection.find({"user_id": target_id}))

    detail = (
        f"👤 **ইউজার ডিটেইলস ও হিস্টরি:**\n"
        f"• আইডি: `{target_id}`\n"
        f"• নাম: {u_data.get('name')}\n"
        f"• ব্যালেন্স: ${u_data.get('balance',0):.2f} USD\n"
        f"• মোট কেনা নাম্বার: {u_data.get('numbers_bought',0)} টি\n\n"
        f"📜 **নাম্বার ও লিংক হিস্টরি:**\n"
    )
    for p in purchases:
      detail += (
          f"📱 `{p['number']}` | Link: {p.get('link','N/A')} | OTP:"
          f" {p['otp']}\n"
      )

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "💵 কাস্টম ব্যালেন্স অ্যাড করুন",
            callback_data=f"adm_addbal_{target_id}",
        )
    )
    bot.edit_message_text(
        detail, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown"
    )

  elif call.data.startswith("adm_addbal_") and user_id == ADMIN_ID:
    target_id = int(call.data.split("_")[2])
    user_states[user_id] = {"step": "custom_balance", "target_user": target_id}
    bot.send_message(
        call.message.chat.id,
        f"💵 ইউজার (`{target_id}`)-কে কত ডলার ($) যোগ করতে চান তার পরিমাণ লিখুন:",
        parse_mode="Markdown",
    )


# ==================== টেক্সট ইনপুট ও ডিপোজিট প্রসেসিং ====================
@bot.message_handler(
    func=lambda message: message.from_user.id in user_states
    or message.text
    and message.text.startswith("/")
)
def handle_text_inputs(message):
  user_id = message.from_user.id
  text = message.text

  if user_id == ADMIN_ID:
    if text.startswith("/setbkash"):
      num = text.split(" ", 1)[1]
      set_setting("bkash_num", num)
      bot.reply_to(message, f"✅ বিকাশ নম্বর আপডেট করা হয়েছে: {num}")
      return
    elif text.startswith("/setnagad"):
      num = text.split(" ", 1)[1]
      set_setting("nagad_num", num)
      bot.reply_to(message, f"✅ নগদ নম্বর আপডেট করা হয়েছে: {num}")
      return
    elif text.startswith("/setbinance"):
      uid = text.split(" ", 1)[1]
      set_setting("binance_uid", uid)
      bot.reply_to(message, f"✅ বাইন্যান্স UID আপডেট করা হয়েছে: {uid}")
      return

  if user_id in user_states:
    state = user_states[user_id]

    if state["step"] == "waiting_amount":
      try:
        amount_usd = float(text)
        amount_bdt = amount_usd * 128
        method = state["method"]
        acc_num = get_setting(f"{method.lower()}_num", "01XXXXXXXXX")

        state["amount_usd"] = amount_usd
        state["amount_bdt"] = amount_bdt
        state["step"] = "waiting_trx"

        bot.send_message(
            message.chat.id,
            f"📥 **পেমেন্ট নির্দেশিকা ({method}):**\n\nঅ্যাকাউন্ট: `{acc_num}`\nপরিমাণ:"
            f" **${amount_usd} USD** (৳{amount_bdt} BDT)\n\nটাকা পাঠিয়ে"
            " ট্রানজেকশন আইডি বা স্ক্রিনশট সেন্ড করুন:",
            parse_mode="Markdown",
        )
      except ValueError:
        bot.reply_to(message, "❌ সঠিক সংখ্যা লিখুন (যেমন: 5)")

    elif state["step"] == "custom_balance" and user_id == ADMIN_ID:
      try:
        add_amount = float(text)
        target_user = state["target_user"]
        users_collection.update_one(
            {"user_id": target_user}, {"$inc": {"balance": add_amount}}
        )
        bot.reply_to(
            message,
            f"✅ সফলভাবে ইউজার (`{target_user}`)-এর অ্যাকাউন্টে ${add_amount}"
            " যোগ করা হয়েছে!",
            parse_mode="Markdown",
        )
        user_states.pop(user_id, None)
      except ValueError:
        bot.reply_to(message, "❌ সঠিক সংখ্যা লিখুন।")


if __name__ == "__main__":
  print("🤖 বট সফলভাবে রান হচ্ছে...")
  bot.infinity_polling()
      
