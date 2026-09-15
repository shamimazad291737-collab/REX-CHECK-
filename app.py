from datetime import datetime
import os
from pymongo import MongoClient
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

# এনভায়রনমেন্ট ভেরিয়েবল থেকে কনফিগারেশন লোড করা
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
MONGO_URI = os.getenv("MONGO_URI")

# MongoDB কানেকশন
client = MongoClient(MONGO_URI)
db = client["telegram_otp_bot"]
users_collection = db["users"]
stock_collection = db["stock"]
history_collection = db["history"]

bot = telebot.TeleBot(TOKEN)


# স্টার্ট কমান্ড ও ইউজার রেজিস্ট্রেশন
@bot.message_handler(commands=["start"])
def send_welcome(message):
  user_id = message.from_user.id

  # ইউজার ব্যান বা রেজিস্টার্ড চেক
  user = users_collection.find_one({"user_id": user_id})
  if user and user.get("is_banned", 0) == 1:
    bot.reply_to(message, "⚠️ আপনি এই বট থেকে ব্লক বা ব্যান হয়েছেন!")
    return

  if not user:
    users_collection.insert_one({"user_id": user_id, "is_banned": 0})

  markup = InlineKeyboardMarkup()
  markup.row(
      InlineKeyboardButton("🛒 বাই সিঙ্গেল নাম্বার", callback_data="buy_single"),
      InlineKeyboardButton("🛒 বাই মাল্টিপল নাম্বার", callback_data="buy_multi"),
  )
  markup.row(
      InlineKeyboardButton("👤 আমার হিস্টরি", callback_data="my_history"),
      InlineKeyboardButton("🛠️ সাপোর্ট", callback_data="support"),
  )

  if user_id == ADMIN_ID:
    markup.row(
        InlineKeyboardButton("⚙️ এডমিন প্যানেল", callback_data="admin_panel")
    )

  bot.send_message(
      message.chat.id,
      "✨ স্বাগতম! আপনার প্রয়োজনীয় অপশনটি নিচে থেকে বেছে নিন:",
      reply_markup=markup,
  )


# সাপোর্ট বাটন
@bot.callback_query_handler(func=lambda call: call.data == "support")
def support_callback(call):
  bot.answer_callback_query(call.id)
  bot.send_message(
      call.message.chat.id,
      "📞 কোনো সমস্যা হলে আমাদের সাপোর্ট এডমিনের সাথে যোগাযোগ করুন: @YourUsername",
  )


# ইউজার হিস্টরি (MongoDB থেকে ফেচ করা)
@bot.callback_query_handler(func=lambda call: call.data == "my_history")
def history_callback(call):
  user_id = call.from_user.id
  rows = list(history_collection.find({"user_id": user_id}))

  if not rows:
    bot.answer_callback_query(call.id, "আপনার কোনো ক্রয়ের হিস্টরি নেই!")
    return

  text = "📜 **আপনার নাম্বার ক্রয়ের হিস্টরি:**\n\n"
  for r in rows:
    text += (
        f"📱 নাম্বার: `{r['number']}`\n🔗 লিংক:"
        f" {r['otp_link']}\n📅 তারিখ: {r['date']}\n-------------------\n"
    )

  bot.send_message(call.message.chat.id, text, parse_mode="Markdown")


# বাই সিঙ্গেল নাম্বার হ্যান্ডলার
@bot.callback_query_handler(func=lambda call: call.data == "buy_single")
def buy_single_callback(call):
  process_purchase(call.message.chat.id, call.from_user.id, 1, call.id)


# বাই মাল্টিপল নাম্বার প্রম্পট
@bot.callback_query_handler(func=lambda call: call.data == "buy_multi")
def buy_multi_prompt(call):
  markup = InlineKeyboardMarkup()
  markup.row(
      InlineKeyboardButton("২ টি", callback_data="get_2"),
      InlineKeyboardButton("৩ টি", callback_data="get_3"),
      InlineKeyboardButton("৫ টি", callback_data="get_5"),
  )
  bot.edit_message_text(
      "📦 কয়টি নাম্বার কিনতে চান তা সিলেক্ট করুন:",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
  )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("get_")
    and call.data != "get_stock"
)
def buy_multi_process(call):
  count = int(call.data.split("_")[1])
  process_purchase(call.message.chat.id, call.from_user.id, count, call.id)


# নাম্বার প্রসেসিং ও স্টক থেকে কাটার ফাংশন (MongoDB)
def process_purchase(chat_id, user_id, quantity, call_id):
  items = list(stock_collection.limit(quantity))

  if len(items) < quantity:
    bot.answer_callback_query(
        call_id,
        f"দুঃখিত, বর্তমানে পর্যাপ্ত স্টক নেই! (মজুদ আছে: {len(items)} টি)",
    )
    return

  current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  response_text = "✅ **আপনার অর্ডার সফল হয়েছে!**\n\n"
  markup = InlineKeyboardMarkup()

  for item in items:
    stock_id = item["_id"]
    number = item["number"]
    otp_link = item["otp_link"]

    stock_collection.delete_one({"_id": stock_id})
    history_collection.insert_one({
        "user_id": user_id,
        "number": number,
        "otp_link": otp_link,
        "date": current_date,
    })

    response_text += (
        f"📱 নাম্বার: `{number}`\n🔗 ওটিপি লিংক: {otp_link}\n-------------------\n"
    )
    markup.add(InlineKeyboardButton(f"🔄 চেক ওটিপি ({number})", url=otp_link))

  bot.send_message(
      chat_id, response_text, parse_mode="Markdown", reply_markup=markup
  )


# এডমিন প্যানেল হ্যান্ডলার
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel_callback(call):
  if call.from_user.id != ADMIN_ID:
    bot.answer_callback_query(call.id, "আপনার এই প্যানেলে প্রবেশাধিকার নেই!")
    return

  markup = InlineKeyboardMarkup()
  markup.row(
      InlineKeyboardButton("👥 ইউজার ম্যানেজমেন্ট", callback_data="admin_users"),
      InlineKeyboardButton(
          "📁 ফাইল আপলোড (TXT)", callback_data="admin_upload"
      ),
  )

  bot.send_message(
      call.message.chat.id,
      "⚙️ **এডমিন কন্ট্রোল প্যানেল**",
      reply_markup=markup,
      parse_mode="Markdown",
  )


@bot.callback_query_handler(func=lambda call: call.data == "admin_upload")
def admin_upload_prompt(call):
  bot.send_message(
      call.message.chat.id,
      "📁 দয়া করে একটি `.txt` ফাইল পাঠান যার প্রতি লাইনে ফরম্যাট হবে:"
      " `number|otp_link`",
  )


@bot.message_handler(
    content_types=["document"],
    func=lambda message: message.from_user.id == ADMIN_ID,
)
def handle_txt_file(message):
  if not message.document.file_name.endswith(".txt"):
    bot.reply_to(message, "দয়া করে শুধুমাত্র `.txt` ফাইল আপলোড করুন!")
    return

  file_info = bot.get_file(message.document.file_id)
  downloaded_file = bot.download_file(file_info.file_path)

  lines = downloaded_file.decode("utf-8").splitlines()
  count = 0
  for line in lines:
    if "|" in line:
      num, link = line.strip().split("|", 1)
      stock_collection.insert_one(
          {"number": num.strip(), "otp_link": link.strip()}
      )
      count += 1

  bot.reply_to(
      message,
      f"✅ সফলভাবে {count} টি নাম্বার স্টক-এ যুক্ত করা হয়েছে!",
  )


@bot.callback_query_handler(func=lambda call: call.data == "admin_users")
def admin_users_list(call):
  users = list(users_collection.find())
  text = "👥 **ইউজার লিস্ট ও স্ট্যাটাস:**\n\n"
  markup = InlineKeyboardMarkup()
  for u in users:
    status = "🔴 ব্যানড" if u.get("is_banned", 0) == 1 else "🟢 একটিভ"
    if u.get("is_banned", 0) == 0:
      markup.add(
          InlineKeyboardButton(
              f"ব্যান করুন: {u['user_id']}",
              callback_data=f"ban_{u['user_id']}",
          )
      )
    text += f"ID: `{u['user_id']}` - {status}\n"

  bot.send_message(
      call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith("ban_"))
def ban_user(call):
  if call.from_user.id != ADMIN_ID:
    return
  target_user_id = int(call.data.split("_")[1])

  users_collection.update_one(
      {"user_id": target_user_id}, {"$set": {"is_banned": 1}}
  )

  bot.answer_callback_query(call.id, f"ইউজার {target_user_id} কে ব্যান করা হয়েছে!")
  bot.edit_message_text(
      f"✅ ইউজার `{target_user_id}` সফলভাবে ব্যান করা হয়েছে।",
      call.message.chat.id,
      call.message.message_id,
      parse_mode="Markdown",
  )


if __name__ == "__main__":
  print("Bot with MongoDB is running...")
  bot.infinity_polling()
  
