from datetime import datetime
import os
from bson.objectid import ObjectId
from flask import Flask, request
from pymongo import MongoClient
import telebot
from telebot.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# Flask app initialization for Render/Railway Port Binding
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot is running perfectly with MongoDB!"


# Environment Variables
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
SUPPORT_USERNAME = os.environ.get("SUPPORT_USERNAME", "@YourSupportAdmin")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")

bot = telebot.TeleBot(TOKEN)

# MongoDB Database Connection & Collections
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["telegram_otp_bot"]

users_col = db["users"]
stock_col = db["stock"]
vpn_stock_col = db["vpn_stock"]
vpn_orders_col = db["vpn_orders"]
orders_col = db["active_orders"]
settings_col = db["settings"]
user_states_col = db["user_states"]  # Database state collection
refund_logs_col = db["refund_logs"]  # Collection for Refund History
user_history_col = (
    db["user_history"]  # সমস্ত ইউজারের অ্যাক্টিভিটি/হিস্ট্রি কালেকশন
)


# Helper Functions for User States
def get_user_state(user_id):
  doc = user_states_col.find_one({"user_id": user_id})
  return doc.get("state") if doc else None


def set_user_state(user_id, state):
  user_states_col.update_one(
      {"user_id": user_id}, {"$set": {"state": state}}, upsert=True
  )


def delete_user_state(user_id):
  user_states_col.delete_one({"user_id": user_id})


# Helper Function to Log User Activity/History
def log_user_history(user_id, username, action, details=""):
  history_data = {
      "user_id": user_id,
      "username": username,
      "action": action,
      "details": details,
      "timestamp": datetime.utcnow(),
  }
  user_history_col.insert_one(history_data)


def get_setting(key, default_val):
  setting = settings_col.find_one({"key": key})
  return setting["value"] if setting else default_val


def set_setting(key, val):
  settings_col.update_one({"key": key}, {"$set": {"value": val}}, upsert=True)


# ==================== মেইন রিপ্লাই কিবোর্ড ====================
def main_menu_markup(user_id):
  markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  markup.add(
      KeyboardButton("🛍️ বাই নাম্বার"),
      KeyboardButton("👤 আমার প্রোফাইল"),
      KeyboardButton("💰 ডিপোজিট"),
      KeyboardButton("📜 আমার হিস্টরি"),
      KeyboardButton("🛠️ সাপোর্ট"),
  )
  if int(user_id) == int(ADMIN_ID):
    markup.add(KeyboardButton("⚙️ অ্যাডমিন প্যানেল"))
  return markup


# ==================== /start কমান্ড ====================
@bot.message_handler(commands=["start"])
def send_welcome(message):
  user_id = message.from_user.id
  name = message.from_user.first_name
  username = message.from_user.username or "No Username"

  log_user_history(user_id, username, "START_BOT", "User started the bot")

  user = users_col.find_one({"user_id": user_id})
  if user and user.get("is_banned", 0) == 1:
    bot.reply_to(message, "⚠️ আপনি এই বট থেকে ব্লক বা ব্যান হয়েছেন!")
    return

  if not user:
    users_col.insert_one({
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
  username = message.from_user.username or "No Username"
  text = message.text
  delete_user_state(user_id)

  if text == "🛍️ বাই নাম্বার":
    log_user_history(user_id, username, "CLICK_MENU", "Opened Buy Number menu")
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
    log_user_history(user_id, username, "CLICK_MENU", "Checked Profile")
    user = users_col.find_one({"user_id": user_id})
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
    log_user_history(user_id, username, "CLICK_MENU", "Opened Deposit menu")
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
    log_user_history(user_id, username, "CLICK_MENU", "Checked Purchase History")
    history = list(orders_col.find({"user_id": user_id}).limit(10))
    if not history:
      bot.send_message(message.chat.id, "📜 আপনার কোনো ক্রয়ের হিস্টরি নেই।")
    else:
      h_text = "📜 **আপনার সাম্প্রতিক কেনাকাটার ইতিহাস:**\n\n"
      for h in history:
        h_text += (
            f"• নাম্বার: `{h.get('number','N/A')}` | OTP:"
            f" {h.get('otp','Pending')}\n"
        )
      bot.send_message(message.chat.id, h_text, parse_mode="Markdown")

  elif text == "🛠️ সাপোর্ট":
    log_user_history(user_id, username, "CLICK_MENU", "Opened Support")
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "🛠️ লাইভ সাপোর্টে যোগাযোগ করুন",
            url=f"https://t.me/{SUPPORT_USERNAME.replace('@','')}",
        )
    )
    bot.send_message(
        message.chat.id,
        "🛠️ কোনো সমস্যা বা সাহায্যের জন্য নিচের লিংকে যোগাযোগ করুন:",
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif text == "⚙️ অ্যাডমিন প্যানেল" and int(user_id) == int(ADMIN_ID):
    log_user_history(
        user_id, username, "ADMIN_ACTION", "Opened Admin Control Panel"
    )
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
  username = call.from_user.username or "No Username"

  if call.data.startswith("dep_"):
    method = call.data.split("_")[1].upper()
    set_user_state(user_id, f"waiting_amount_{method}")
    bot.send_message(
        call.message.chat.id,
        f"💵 আপনি **{method}** সিলেক্ট করেছেন।\nকত ডলার ($) ডিপোজিট করতে চান তার পরিমাণ সংখ্যায় লিখুন (যেমন: 5 বা 10):",
        parse_mode="Markdown",
    )
    bot.answer_callback_query(call.id)

  elif call.data == "buy_single":
    num_data = stock_col.find_one({"is_sold": False})
    if not num_data:
      bot.answer_callback_query(
          call.id,
          "❌ দুঃখিত, বর্তমানে কোনো সিঙ্গেল নাম্বার স্টকে নেই!",
          show_alert=True,
      )
      return

    user = users_col.find_one({"user_id": user_id})
    price_usd = 0.5
    if user["balance"] < price_usd:
      bot.answer_callback_query(
          call.id,
          f"❌ পর্যাপ্ত ব্যালেন্স নেই! প্রয়োজন: ${price_usd} USD",
          show_alert=True,
      )
      return

    users_col.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": -price_usd, "numbers_bought": 1}},
    )
    stock_col.update_one(
        {"_id": num_data["_id"]},
        {"$set": {"is_sold": True, "buyer_id": user_id}},
    )

    log_user_history(
        user_id,
        username,
        "BUY_NUMBER",
        f"Bought number: {num_data.get('number')}",
    )

    p_id = orders_col.insert_one({
        "user_id": user_id,
        "number": num_data.get("number"),
        "otp": "Pending",
        "type": "Single",
        "timestamp": datetime.utcnow(),
    }).inserted_id

    msg = (
        f"✅ **সফলভাবে নাম্বার ক্রয় করা হয়েছে!**\n\n"
        f"📱 নাম্বার: `{num_data.get('number')}`\n\n"
    )
    bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

  elif call.data == "adm_all_history" and int(user_id) == int(ADMIN_ID):
    # MongoDB থেকে সকল ইউজারের সাম্প্রতিক হিস্টরি ফেচ করা
    all_history = list(
        user_history_col.find({}).sort("timestamp", -1).limit(15)
    )
    if not all_history:
      bot.answer_callback_query(call.id, "কোনো হিস্টরি নেই!")
      return

    text = "📊 **সকল ইউজারের সাম্প্রতিক অ্যাক্টিভিটি হিস্টরি:**\n\n"
    for h in all_history:
      t_str = h.get("timestamp", datetime.utcnow()).strftime("%d-%m %H:%M")
      text += (
          f"• `{h.get('user_id')}` (@{h.get('username')}):"
          f" **{h.get('action')}** | _{h.get('details')}_ [{t_str}]\n"
      )

    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, parse_mode="Markdown"
    )

  elif call.data == "adm_set_payment" and int(user_id) == int(ADMIN_ID):
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

  elif call.data == "adm_users" and int(user_id) == int(ADMIN_ID):
    users = list(users_col.find({}).limit(20))
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
        "👥 **সকল ইউজারের তালিকা:** (ডিটেইলস দেখতে ক্লিক করুন)",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif call.data.startswith("adm_u_detail_") and int(user_id) == int(ADMIN_ID):
    target_id = int(call.data.split("_")[3])
    u_data = users_col.find_one({"user_id": target_id})
    user_acts = list(
        user_history_col.find({"user_id": target_id})
        .sort("timestamp", -1)
        .limit(10)
    )

    detail = (
        f"👤 **ইউজার ডিটেইলস:**\n"
        f"• আইডি: `{target_id}`\n"
        f"• নাম: {u_data.get('name')}\n"
        f"• ব্যালেন্স: ${u_data.get('balance',0):.2f} USD\n"
        f"• মোট কেনা নাম্বার: {u_data.get('numbers_bought',0)} টি\n\n"
        f"📜 **সর্বশেষ অ্যাক্টিভিটি:**\n"
    )
    for act in user_acts:
      detail += (
          f"• {act.get('action')}: {act.get('details')} ("
          f"{act.get('timestamp').strftime('%H:%M')})\n"
      )

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "💵 ব্যালেন্স যোগ করুন", callback_data=f"adm_addbal_{target_id}"
        )
    )
    bot.edit_message_text(
        detail,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif call.data.startswith("adm_addbal_") and int(user_id) == int(ADMIN_ID):
    target_id = int(call.data.split("_")[2])
    set_user_state(user_id, f"custom_balance_{target_id}")
    bot.send_message(
        call.message.chat.id,
        f"💵 ইউজার (`{target_id}`)-কে কত ডলার ($) যোগ করতে চান তার পরিমাণ লিখুন:",
        parse_mode="Markdown",
    )


# ==================== টেক্সট ইনপুট ও স্টেট প্রসেসিং ====================
@bot.message_handler(
    func=lambda message: True, content_types=["text", "photo"]
)
def handle_all_messages(message):
  user_id = message.from_user.id
  username = message.from_user.username or "No Username"
  text = message.text or ""

  # অ্যাডমিন কমান্ড হ্যান্ডলিং
  if int(user_id) == int(ADMIN_ID):
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

  current_state = get_user_state(user_id)
  if current_state:
    if current_state.startswith("waiting_amount_"):
      method = current_state.split("_")[2]
      try:
        amount_usd = float(text)
        amount_bdt = amount_usd * 128
        acc_num = get_setting(f"{method.lower()}_num", "01XXXXXXXXX")

        set_user_state(user_id, f"waiting_trx_{method}_{amount_usd}")
        bot.send_message(
            message.chat.id,
            f"📥 **পেমেন্ট নির্দেশিকা ({method}):**\n\nঅ্যাকাউন্ট: `{acc_num}`\nপরিমাণ:"
            f" **${amount_usd} USD** (৳{amount_bdt} BDT)\n\nটাকা পাঠিয়ে"
            " ট্রানজেকশন আইডি বা স্ক্রিনশট সেন্ড করুন:",
            parse_mode="Markdown",
        )
      except ValueError:
        bot.reply_to(message, "❌ সঠিক সংখ্যা লিখুন (যেমন: 5)")

    elif current_state.startswith("waiting_trx_"):
      parts = current_state.split("_")
      method = parts[2]
      amount_usd = float(parts[3])
      log_user_history(
          user_id,
          username,
          "DEPOSIT_REQUEST",
          f"Requested deposit {amount_usd}$ via {method}",
      )
      bot.reply_to(
          message,
          "✅ আপনার ডিপোজিট রিকোয়েস্ট সাবমিট হয়েছে! অ্যাডমিন চেক করে ব্যালেন্স"
          " যোগ করে দেবেন।",
      )
      delete_user_state(user_id)

    elif current_state.startswith("custom_balance_") and int(user_id) == int(
        ADMIN_ID
    ):
      target_user = int(current_state.split("_")[2])
      try:
        add_amount = float(text)
        users_col.update_one(
            {"user_id": target_user}, {"$inc": {"balance": add_amount}}
        )
        log_user_history(
            ADMIN_ID,
            username,
            "ADMIN_BALANCE_ADD",
            f"Added {add_amount}$ to user {target_user}",
        )
        bot.reply_to(
            message,
            f"✅ সফলভাবে ইউজার (`{target_user}`)-এর অ্যাকাউন্টে ${add_amount}"
            " যোগ করা হয়েছে!",
            parse_mode="Markdown",
        )
        delete_user_state(user_id)
      except ValueError:
        bot.reply_to(message, "❌ সঠিক সংখ্যা লিখুন।")


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  print(f"🤖 বট সফলভাবে পোর্ট {port}-এ রান হচ্ছে...")
  bot.remove_webhook()
  app.run(host="0.0.0.0", port=port)
      
