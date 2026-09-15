import os
from bson.objectid import ObjectId
from pymongo import MongoClient
import telebot
from telebot.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)

# এনভায়রনমেন্ট ভেরিয়েবল বা কনফিগারেশন
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
MONGO_URI = os.getenv("MONGO_URI", "YOUR_MONGO_URI_HERE")

bot = telebot.TeleBot(TOKEN)

# মঙ্গোডিবি কানেকশন
client = MongoClient(MONGO_URI)
db = client["telegram_number_bot"]
users_collection = db["users"]
numbers_collection = db["numbers"]  # আপলোড করা নাম্বারের স্টক
settings_collection = db["settings"]  # অ্যাডমিন থেকে টেক্সট বা সেটিংস এডিট করার জন্য
transactions_collection = db["transactions"]


# ডিফল্ট সেটিংস ইনিশিয়ালাইজ করা (যদি না থাকে)
def get_setting(key, default_val):
  setting = settings_collection.find_one({"key": key})
  return setting["value"] if setting else default_val


def set_setting(key, val):
  settings_collection.update_one(
      {"key": key}, {"$set": {"value": val}}, upsert=True
  )


# ==================== /start কমান্ড ====================
@bot.message_handler(commands=["start"])
def send_welcome(message):
  user_id = message.from_user.id
  username = message.from_user.username or "No Username"
  name = message.from_user.first_name

  # ইউজার চেক বা রেজিস্ট্রেশন
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

  markup = InlineKeyboardMarkup(row_width=2)
  markup.add(
      InlineKeyboardButton("🛍️ বাই নাম্বার", callback_data="buy_number_menu"),
      InlineKeyboardButton("👤 আমার প্রোফাইল", callback_data="my_profile"),
      InlineKeyboardButton("💰 ডিপোজিট", callback_data="deposit_menu"),
      InlineKeyboardButton("📜 আমার হিস্টরি", callback_data="my_history"),
      InlineKeyboardButton("🛠️ সাপোর্ট", callback_data="support"),
  )

  if user_id == ADMIN_ID:
    markup.add(InlineKeyboardButton("⚙️ অ্যাডমিন প্যানেল", callback_data="admin_panel"))

  welcome_text = get_setting(
      "welcome_text",
      "✨ **স্বাগতম!** আপনার প্রয়োজনীয় অপশনটি নিচের মেনু থেকে বেছে নিন:",
  )
  bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")


# ==================== বাটন কলব্যাক হ্যান্ডলার ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
  user_id = call.from_user.id

  # ১. বাই নাম্বার মেনু
  if call.data == "buy_number_menu":
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🛒 বাই সিঙ্গেল নাম্বার", callback_data="buy_single"),
        InlineKeyboardButton("🛒 বাই মাল্টিপল নাম্বার", callback_data="buy_multi"),
        InlineKeyboardButton("🔙 ফিরে যান", callback_data="main_menu"),
    )
    bot.edit_message_text(
        "📦 **নাম্বার ক্রয়ের অপশন:**\nদয়া করে আপনার পছন্দের ক্যাটাগরি সিলেক্ট করুন:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )

  # ২. সিঙ্গেল নাম্বার বাই
  elif call.data == "buy_single":
    # স্টক থেকে একটি নাম্বার বের করা (লজিক: numbers_collection থেকে আনসোল্ড নাম্বার নেওয়া)
    num_data = numbers_collection.find_one({"is_sold": False})
    if not num_data:
      bot.answer_callback_query(call.id, "❌ দুঃখিত, বর্তমানে কোনো নাম্বার স্টকে নেই!", show_alert=True)
      return

    # ইউজার ব্যালেন্স চেক (ধরে নিলাম সিঙ্গেল নাম্বারের দাম নির্দিষ্ট বা ব্যালেন্স আছে)
    user = users_collection.find_one({"user_id": user_id})
    price = 50.0  # উদাহরণস্বরূপ দাম
    if user["balance"] < price:
      bot.answer_callback_query(
          call.id, f"❌ আপনার পর্যাপ্ত ব্যালেন্স নেই! প্রয়োজন: ৳{price}", show_alert=True
      )
      return

    # ব্যালেন্স কাটুন এবং নাম্বার সোল্ড করুন
    users_collection.update_one(
        {"user_id": user_id},
        {
            "$inc": {
                "balance": -price,
                "numbers_bought": 1,
            }
        },
    )
    numbers_collection.update_one(
        {"_id": num_data["_id"]}, {"$set": {"is_sold": True, "buyer_id": user_id}}
    )

    # ইউজারের হিস্টরিতে যুক্ত করা
    db["purchase_history"].insert_one({
        "user_id": user_id,
        "number": num_data["number"],
        "link": num_data.get("link", "N/A"),
        "otp": "Pending",
        "type": "Single",
    })

    # ইউজারকে নাম্বার পাঠানো
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🔄 চেক ওটিপি", callback_data=f"check_otp_{num_data['_id']}")
    )
    markup.add(InlineKeyboardButton("🏠 মূল মেনু", callback_data="main_menu"))

    msg = (
        f"✅ **সফলভাবে নাম্বার ক্রয় করা হয়েছে!**\n\n"
        f"📱 নাম্বার: `{num_data['number']}`\n"
        f"🔗 লিংক: {num_data.get('link', 'N/A')}\n\n"
        f"ওটিপি দেখতে নিচে 'চেক ওটিপি' বাটনে ক্লিক করুন।"
    )
    bot.edit_message_text(
        msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown"
    )

  # ৩. মাল্টিপল নাম্বার বাই
  elif call.data == "buy_multi":
    bot.answer_callback_query(call.id, "🛠️ মাল্টিপল নাম্বার সিস্টেম শীঘ্রই চালু হচ্ছে!", show_alert=True)

  # ৪. প্রোফাইল
  elif call.data == "my_profile":
    user = users_collection.find_one({"user_id": user_id})
    if not user:
      bot.answer_callback_query(call.id, "❌ ইউজার ডাটা পাওয়া যায়নি। /start লিখুন।")
      return

    profile_text = (
        f"👤 **আপনার প্রফাইল বিবরণী:**\n\n"
        f"🆔 ইউজার আইডি: `{user_id}`\n"
        f"📛 নাম: {user.get('name', 'N/A')}\n"
        f"💰 কারেন্ট ব্যালেন্স: ৳{user.get('balance', 0.0)}\n"
        f"💵 মোট ডিপোজিট: ৳{user.get('total_deposit', 0.0)}\n"
        f"🛒 মোট কেনা নাম্বার: {user.get('numbers_bought', 0)} টি"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 ফিরে যান", callback_data="main_menu"))
    bot.edit_message_text(
        profile_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown"
    )

  # ৫. ডিপোজিট মেনু
  elif call.data == "deposit_menu":
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("💳 বিকাশ", callback_data="dep_bkash"),
        InlineKeyboardButton("📱 নগদ", callback_data="dep_nagad"),
        InlineKeyboardButton("🪙 বাইন্যান্স", callback_data="dep_binance"),
    )
    markup.add(InlineKeyboardButton("🔙 ফিরে যান", callback_data="main_menu"))
    bot.edit_message_text(
        "💰 **পেমেন্ট মেথড সিলেক্ট করুন:**\nনিচের মাধ্যমগুলোর যেকোনো একটির মাধ্যমে ব্যালেন্স অ্যাড করতে পারেন:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif call.data.startswith("dep_"):
    method = call.data.split("_")[1].upper()
    bot.answer_callback_query(
        call.id, f"আপনার {method} পেমেন্ট রিকোয়েস্ট প্রসেস করা হচ্ছে। অ্যাডমিনের সাথে যোগাযোগ করুন।"
    )

  # ৬. আমার হিস্টরি
  elif call.data == "my_history":
    history = list(db["purchase_history"].find({"user_id": user_id}).limit(5))
    if not history:
      text = "📜 আপনার কোনো ক্রয়ের হিস্টরি নেই।"
    else:
      text = "📜 **আপনার সাম্প্রতিক কেনাকাটার ইতিহাস:**\n\n"
      for h in history:
        text += f"• নাম্বার: `{h['number']}` | স্ট্যাটাস: {h['otp']}\n"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 ফিরে যান", callback_data="main_menu"))
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown"
    )

  # ৭. সাপোর্ট
  elif call.data == "support":
    support_username = get_setting("support_username", "@YourSupportAdmin")
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛠️ লাইভ সাপোর্টে যোগাযোগ করুন", url=f"https://t.me/{support_username.replace('@','')}"))
    markup.add(InlineKeyboardButton("🔙 ফিরে যান", callback_data="main_menu"))
    bot.edit_message_text(
        "🛠️ কোনো সমস্যা হলে নিচের লিংকে ক্লিক করে সরাসরি সাপোর্টে যোগাযোগ করুন:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )

  # ৮. মেইন মেনু ব্যাক
  elif call.data == "main_menu":
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🛍️ বাই নাম্বার", callback_data="buy_number_menu"),
        InlineKeyboardButton("👤 আমার প্রোফাইল", callback_data="my_profile"),
        InlineKeyboardButton("💰 ডিপোজিট", callback_data="deposit_menu"),
        InlineKeyboardButton("📜 আমার হিস্টরি", callback_data="my_history"),
        InlineKeyboardButton("🛠️ সাপোর্ট", callback_data="support"),
    )
    if user_id == ADMIN_ID:
      markup.add(InlineKeyboardButton("⚙️ অ্যাডমিন প্যানেল", callback_data="admin_panel"))

    welcome_text = get_setting("welcome_text", "✨ **স্বাগতম!** অপশন সিলেক্ট করুন:")
    bot.edit_message_text(
        welcome_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown"
    )

  # ৯. অ্যাডমিন প্যানেল
  elif call.data == "admin_panel" and user_id == ADMIN_ID:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("👥 ইউজার ম্যানেজমেন্ট", callback_data="adm_users"),
        InlineKeyboardButton("📁 নাম্বার ফাইল আপলোড", callback_data="adm_upload"),
        InlineKeyboardButton("✏️ টেক্সট/সেটিংস এডিট", callback_data="adm_settings"),
        InlineKeyboardButton("🔙 মূল মেনু", callback_data="main_menu"),
    )
    bot.edit_message_text(
        "⚙️ **অ্যাডমিন কন্ট্রোল প্যানেল:**\nনিচ থেকে অপশন বেছে নিন:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )

  # ১০. অ্যাডমিন: ইউজার ম্যানেজমেন্ট (অ্যাক্টিভ ও ইনঅ্যাক্টিভ)
  elif call.data == "adm_users" and user_id == ADMIN_ID:
    active_users = users_collection.count_documents({"numbers_bought": {"$gt": 0}})
    inactive_users = users_collection.count_documents({"numbers_bought": 0})
    total_users = users_collection.count_documents({})

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(f"🟢 অ্যাক্টিভ বায়ার ({active_users})", callback_data="adm_active_list"),
        InlineKeyboardButton(f"⚪ ইনঅ্যাক্টিভ ইউজার ({inactive_users})", callback_data="adm_inactive_list"),
        InlineKeyboardButton("🔙 অ্যাডমিন প্যানেল", callback_data="admin_panel"),
    )
    bot.edit_message_text(
        f"👥 **ইউজার ম্যানেজমেন্ট পরিসংখ্যান:**\n\nমোট ইউজার: {total_users}\nঅ্যাক্টিভ বায়ার: {active_users}\nইনঅ্যাক্টিভ: {inactive_users}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif call.data == "adm_active_list" and user_id == ADMIN_ID:
    users = list(users_collection.find({"numbers_bought": {"$gt": 0}}).limit(10))
    text = "🟢 **অ্যাক্টিভ বায়ার তালিকা:**\n\n"
    markup = InlineKeyboardMarkup(row_width=1)
    for u in users:
      markup.add(InlineKeyboardButton(f"👤 {u.get('name','User')} (ID: {u['user_id']})", callback_data=f"adm_user_detail_{u['user_id']}"))
    markup.add(InlineKeyboardButton("🔙 ফিরে যান", callback_data="adm_users"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

  elif call.data.startswith("adm_user_detail_") and user_id == ADMIN_ID:
    target_id = int(call.data.split("_")[-1])
    u_data = users_collection.find_one({"user_id": target_id})
    purchases = list(db["purchase_history"].find({"user_id": target_id}))

    detail = (
        f"👤 **ইউজার ডিটেইলস:**\n"
        f"• আইডি: `{target_id}`\n"
        f"• নাম: {u_data.get('name')}\n"
        f"• ব্যালেন্স: ৳{u_data.get('balance')}\n"
        f"• কেনা নাম্বার সংখ্যা: {u_data.get('numbers_bought')}\n\n"
        f"**নাম্বার হিস্টরি ও লিংক:**\n"
    )
    for p in purchases:
      detail += f" - `{p['number']}` | Link: {p['link']} | OTP: {p['otp']}\n"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💵 ব্যালেন্স অ্যাড/রিফান্ড", callback_data=f"adm_refund_{target_id}"))
    markup.add(InlineKeyboardButton("🔙 ফিরে যান", callback_data="adm_users"))
    bot.edit_message_text(detail, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")


# ==================== ফাইল আপলোড হ্যান্ডলার (অ্যাডমিন) ====================
@bot.message_handler(content_types=["document"])
def handle_file_upload(message):
  if message.from_user.id != ADMIN_ID:
    return

  # ফাইল ডাউনলোড ও প্রসেস করা (যেমন: number, link ফরম্যাটের টেক্সট ফাইল)
  file_info = bot.get_file(message.document.file_id)
  downloaded_file = bot.download_file(file_info.file_path)

  file_path = "uploaded_numbers.txt"
  with open(file_path, "wb") as f:
    f.write(downloaded_file)

  count = 0
  with open(file_path, "r", encoding="utf-8") as f:
    for line in f:
      parts = line.strip().split(",")
      if len(parts) >= 1:
        number = parts[0].strip()
        link = parts[1].strip() if len(parts) > 1 else "N/A"
        numbers_collection.insert_one({
            "number": number,
            "link": link,
            "is_sold": False,
            "buyer_id": None,
        })
        count += 1

  bot.reply_to(message, f"✅ সফলভাবে {count} টি নাম্বার ডাটাবেজে যুক্ত করা হয়েছে!")


# বট রান করার জন্য
if __name__ == "__main__":
  print("🤖 বট সফলভাবে রান হচ্ছে...")
  bot.infinity_polling()
    
