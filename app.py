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
    ReplyKeyboardRemove,
)

TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
MONGO_URI = os.getenv("MONGO_URI", "YOUR_MONGO_URI_HERE")

bot = telebot.TeleBot(TOKEN)

# মঙ্গোডিবি কানেকশন
client = MongoClient(MONGO_URI)
db = client["telegram_number_bot"]
users_collection = db["users"]
numbers_collection = db["numbers"]
settings_collection = db["settings"]
purchase_collection = db["purchase_history"]


def get_setting(key, default_val):
  setting = settings_collection.find_one({"key": key})
  return setting["value"] if setting else default_val


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
    markup.add(KeyboardButton("⚙️ অ্যাডমিন প্যানেল"))
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


# ==================== টেক্সট মেসেজ হ্যান্ডলার (নিচের বাটনের কাজ) ====================
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

  # ১. বাই নাম্বার মেনু
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

  # ২. প্রোফাইল
  elif text == "👤 আমার প্রোফাইল":
    user = users_collection.find_one({"user_id": user_id})
    if not user:
      bot.send_message(message.chat.id, "❌ ডাটা পাওয়া যায়নি। /start লিখুন।")
      return

    profile_text = (
        f"👤 **আপনার প্রোফাইল বিবরণী:**\n\n"
        f"🆔 ইউজার আইডি: `{user_id}`\n"
        f"📛 নাম: {user.get('name', 'N/A')}\n"
        f"💰 কারেন্ট ব্যালেন্স: ৳{user.get('balance', 0.0)}\n"
        f"💵 মোট ডিপোজিট: ৳{user.get('total_deposit', 0.0)}\n"
        f"🛒 মোট কেনা নাম্বার: {user.get('numbers_bought', 0)} টি"
    )
    bot.send_message(
        message.chat.id, profile_text, parse_mode="Markdown"
    )

  # ৩. ডিপোজিট
  elif text == "💰 ডিপোজিট":
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("💳 বিকাশ", callback_data="dep_bkash"),
        InlineKeyboardButton("📱 নগদ", callback_data="dep_nagad"),
        InlineKeyboardButton("🪙 বাইন্যান্স", callback_data="dep_binance"),
    )
    bot.send_message(
        message.chat.id,
        "💰 **পেমেন্ট মেথড সিলেক্ট করুন:**\nবিকাশ, নগদ বা বাইন্যান্সের মাধ্যমে পেমেন্ট করে অ্যাডমিনকে স্ক্রিনশট দিন।",
        reply_markup=markup,
        parse_mode="Markdown",
    )

  # ৪. হিস্টরি
  elif text == "📜 আমার হিস্টরি":
    history = list(purchase_collection.find({"user_id": user_id}).limit(10))
    if not history:
      bot.send_message(message.chat.id, "📜 আপনার কোনো ক্রয়ের হিস্টরি নেই।")
    else:
      h_text = "📜 **আপনার সাম্প্রতিক কেনাকাটার ইতিহাস:**\n\n"
      for h in history:
        h_text += f"• নাম্বার: `{h['number']}` | OTP: {h['otp']}\n"
      bot.send_message(message.chat.id, h_text, parse_mode="Markdown")

  # ৫. সাপোর্ট
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

  # ৬. অ্যাডমিন প্যানেল
  elif text == "⚙️ অ্যাডমিন প্যানেল" and user_id == ADMIN_ID:
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "👥 ইউজার ম্যানেজমেন্ট (Active/Inactive)",
            callback_data="adm_users",
        ),
        InlineKeyboardButton(
            "📁 নাম্বার ফাইল আপলোড নির্দেশনা", callback_data="adm_upload_help"
        ),
        InlineKeyboardButton(
            "⚙️ টেক্সট/সেটিংস এডিট", callback_data="adm_settings"
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

  # সিঙ্গেল নাম্বার কেনা
  if call.data == "buy_single":
    num_data = numbers_collection.find_one({"is_sold": False})
    if not num_data:
      bot.answer_callback_query(
          call.id,
          "❌ দুঃখিত, বর্তমানে কোনো সিঙ্গেল নাম্বার স্টকে নেই!",
          show_alert=True,
      )
      return

    user = users_collection.find_one({"user_id": user_id})
    price = 50.0  # ফিক্সড দাম (প্রয়োজনে পরিবর্তন করতে পারবেন)
    if user["balance"] < price:
      bot.answer_callback_query(
          call.id,
          f"❌ আপনার পর্যাপ্ত ব্যালেন্স নেই! প্রয়োজন: ৳{price}",
          show_alert=True,
      )
      return

    # ব্যালেন্স কাটা এবং নাম্বার আপডেট করা
    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": -price, "numbers_bought": 1}},
    )
    numbers_collection.update_one(
        {"_id": num_data["_id"]},
        {"$set": {"is_sold": True, "buyer_id": user_id}},
    )

    # পারচেজ হিস্টরি সেভ
    p_id = purchase_collection.insert_one({
        "user_id": user_id,
        "number": num_data["number"],
        "link": num_data.get("link", "N/A"),
        "otp": "Pending",
        "type": "Single",
    }).inserted_id

    # ইউজারকে নাম্বার পাঠানো (সাথে লিংক ও চেক ওটিপি বাটন)
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
    bot.send_message(call.message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

  elif call.data == "buy_multi":
    bot.answer_callback_query(
        call.id,
        "🛠️ মাল্টিপল নাম্বার সিস্টেম শীঘ্রই চালু হচ্ছে!",
        show_alert=True,
    )

  # ডিপোজিট অপশন ক্লিক
  elif call.data.startswith("dep_"):
    method = call.data.split("_")[1].upper()
    bot.answer_callback_query(
        call.id,
        f"আপনার {method} পেমেন্টের জন্য অ্যাডমিনের সাথে যোগাযোগ করুন।",
        show_alert=True,
    )

  # ওটিপি চেক বাটন
  elif call.data.startswith("chk_otp_"):
    p_id = call.data.split("_")[2]
    purchase = purchase_collection.find_one({"_id": ObjectId(p_id)})
    if purchase:
      bot.answer_callback_query(
          call.id,
          f"বর্তমান OTP স্ট্যাটাস: {purchase['otp']}",
          show_alert=True,
      )

  # অ্যাডমিন: ইউজার ম্যানেজমেন্ট
  elif call.data == "adm_users" and user_id == ADMIN_ID:
    active_count = users_collection.count_documents({"numbers_bought": {"$gt": 0}})
    inactive_count = users_collection.count_documents({"numbers_bought": 0})

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            f"🟢 অ্যাক্টিভ বায়ার তালিকা ({active_count})",
            callback_data="adm_active_list",
        ),
        InlineKeyboardButton(
            f"⚪ ইনঅ্যাক্টিভ ইউজার তালিকা ({inactive_count})",
            callback_data="adm_inactive_list",
        ),
    )
    bot.edit_message_text(
        "👥 **ইউজার ম্যানেজমেন্ট সেকশন:**\nকোন ক্যাটাগরির ইউজার দেখতে চান সিলেক্ট করুন:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif call.data == "adm_active_list" and user_id == ADMIN_ID:
    users = list(users_collection.find({"numbers_bought": {"$gt": 0}}).limit(20))
    markup = InlineKeyboardMarkup(row_width=1)
    for u in users:
      markup.add(
          InlineKeyboardButton(
              f"👤 {u.get('name')} (ID: {u['user_id']}) - কেনাকাটা: {u['numbers_bought']}",
              callback_data=f"adm_u_detail_{u['user_id']}",
          )
      )
    bot.edit_message_text(
        "🟢 **অ্যাক্টিভ বায়ারদের তালিকা:** (ডিটেইলস দেখতে নামের ওপর ক্লিক করুন)",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif call.data == "adm_inactive_list" and user_id == ADMIN_ID:
    users = list(users_collection.find({"numbers_bought": 0}).limit(20))
    markup = InlineKeyboardMarkup(row_width=1)
    for u in users:
      markup.add(
          InlineKeyboardButton(
              f"👤 {u.get('name')} (ID: {u['user_id']})",
              callback_data=f"adm_u_detail_{u['user_id']}",
          )
      )
    bot.edit_message_text(
        "⚪ **ইনঅ্যাক্টিভ ইউজারদের তালিকা:**",
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
        f"👤 **ইউজার প্রোফাইল বিবরণী:**\n"
        f"• আইডি: `{target_id}`\n"
        f"• নাম: {u_data.get('name')}\n"
        f"• কারেন্ট ব্যালেন্স: ৳{u_data.get('balance')}\n"
        f"• মোট কেনা নাম্বার: {u_data.get('numbers_bought')} টি\n\n"
        f"📜 **নাম্বার ও লিংক হিস্টরি:**\n"
    )
    for p in purchases:
      detail += f"📱 `{p['number']}` | Link: {p.get('link','N/A')} | OTP: {p['otp']}\n"

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "💵 ব্যালেন্স রিফান্ড/অ্যাড করুন",
            callback_data=f"adm_addbal_{target_id}",
        )
    )
    bot.edit_message_text(
        detail, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown"
    )

  elif call.data.startswith("adm_addbal_") and user_id == ADMIN_ID:
    target_id = int(call.data.split("_")[2])
    # ইউজারকে ১০০ টাকা ব্যালেন্স রিফান্ড বা অ্যাড করার উদাহরণ
    users_collection.update_one(
        {"user_id": target_id}, {"$inc": {"balance": 100.0}}
    )
    bot.answer_callback_query(
        call.id,
        f"✅ সফলভাবে ইউজার ({target_id})-এর অ্যাকাউন্টে ১০০ টাকা যোগ করা হয়েছে!",
        show_alert=True,
    )

  elif call.data == "adm_upload_help" and user_id == ADMIN_ID:
    bot.answer_callback_query(
        call.id,
        "বটে সরাসরি .txt ফাইল সেন্ড করুন। ফরম্যাট: নাম্বার,লিংক",
        show_alert=True,
    )


# ==================== ফাইল আপলোড হ্যান্ডলার (অ্যাডমিন স্টক আপলোড) ====================
@bot.message_handler(content_types=["document"])
def handle_file_upload(message):
  if message.from_user.id != ADMIN_ID:
    return

  file_info = bot.get_file(message.document.file_id)
  downloaded_file = bot.download_file(file_info.file_path)

  file_path = "temp_numbers.txt"
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

  bot.reply_to(
      message,
      f"✅ সফলভাবে স্টক ফাইলে থাকা {count} টি নাম্বার ডাটাবেজে যুক্ত করা হয়েছে!",
  )


if __name__ == "__main__":
  print("🤖 বট সফলভাবে রান হচ্ছে...")
  bot.infinity_polling()
    
