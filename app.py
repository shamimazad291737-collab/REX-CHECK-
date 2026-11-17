import concurrent.futures
import logging
import re
import time
import urllib.request
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# আপনার টেলিগ্রাম বটের টোকেন এখানে বসাবেন
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def check_single_otp(phone, url):
  start_time = time.time()
  try:
    base_parts = url.split("/sms/")
    api_url = base_parts[0] + "/api/sms/" + base_parts[1]
  except Exception:
    return phone, None, False

  # ৫ সেকেন্ড পর্যন্ত ওটিপির জন্য ট্রাই করবে
  while time.time() - start_time < 5:
    try:
      req = urllib.request.Request(
          api_url, headers={"User-Agent": "Mozilla/5.0"}
      )
      with urllib.request.urlopen(req, timeout=3) as response:
        content = response.read().decode("utf-8").strip()
        match = re.search(r"\b\d{5,6}\b", content)
        if match:
          return phone, match.group(0), True
    except Exception:
      pass
    time.sleep(1)

  return phone, None, False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  keyboard = [["📂 How to Use", "⚡ Status Checker"]]
  reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

  welcome_text = (
      "👋 **স্বাগতম! REX OTP Checker বোটে।**\n\n"
      "দয়া করে আপনার `.txt` ফাইল আপলোড করুন অথবা নম্বর ও লিংকের তালিকা একসাথে চ্যাটে পেস্ট করুন।"
  )
  await update.message.reply_text(
      welcome_text, parse_mode="Markdown", reply_markup=reply_markup
  )


async def handle_document_or_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
  message = update.message
  raw_text = ""

  if message.text == "📂 How to Use":
    await message.reply_text(
        "ℹ️ **ব্যবহারের নিয়ম:**\n"
        "ফাইল বা টেক্সটে নিচের ফরম্যাটে ডাটা দিতে হবে:\n\n"
        "`+13082573334 http://169.58.215.134:11111/sms/...`",
        parse_mode="Markdown",
    )
    return
  elif message.text == "⚡ StatusChecker":
    await message.reply_text("⚡ চেকার প্রস্তুত! আপনার ডেটা সেন্ড করুন।")
    return

  # যদি ইউজার ফাইল (.txt) আপলোড করে
  if message.document:
    if not message.document.file_name.endswith(".txt"):
      await message.reply_text(
          "❌ দয়া করে শুধুমাত্র `.txt` ফাইল আপলোড করুন।"
      )
      return

    file = await message.document.get_file()
    file_bytes = await file.download_as_bytearray()
    raw_text = file_bytes.decode("utf-8", errors="ignore")

  # যদি ইউজার সরাসরি টেক্সট পেস্ট করে
  elif message.text:
    raw_text = message.text

  if not raw_text.strip():
    return

  # টেক্সট থেকে নম্বর এবং লিংক আলাদা করা
  pattern = r"(\+\d+)\s+(http[^\s]+)"
  matches = re.findall(pattern, raw_text)

  if not matches:
    await message.reply_text(
        "❌ ফরম্যাট সঠিক নয়!\nসঠিক ফরম্যাট:\n`+13082573334 http://169.58.215.134:11111/...`",
        parse_mode="Markdown",
    )
    return

  total_links = len(matches)
  progress_msg = await message.reply_text(
      f"⏳ মোট `{total_links}` টি নম্বর চেক করা হচ্ছে, একটু অপেক্ষা করুন..."
  )

  received_count = 0
  failed_count = 0
  results_output = []

  # মাল্টিথ্রেডিং দিয়ে একসাথে সব চেক করা
  with concurrent.futures.ThreadPoolExecutor(
      max_workers=min(10, total_links)
  ) as executor:
    futures = [
        executor.submit(check_single_otp, phone, url) for phone, url in matches
    ]

    for i, future in enumerate(
        concurrent.futures.as_completed(futures), start=1
    ):
      phone, otp, success = future.result()
      if success:
        results_output.append(f"{i}. `📱 {phone}` ➔ ✅ **{otp}**")
        received_count += 1
      else:
        results_output.append(f"{i}. `📱 {phone}` ➔ ❌ নাই")
        failed_count += 1

  # ফাইনাল রিপোর্ট পাঠানো
  report = (
      f"📊 **OTP Check Results:**\n\n" + "\n".join(results_output) + f"\n\n"
  )
  report += f"====================\n"
  report += f"✅ পাওয়া গেছে: `{received_count}` টি\n"
  report += f"❌ পাওয়া যায়নি: `{failed_count}` টি\n"
  report += f"📦 মোট চেক: `{total_links}` টি"

  await progress_msg.edit_text(report, parse_mode="Markdown")


def main():
  app = ApplicationBuilder().token(TOKEN).build()

  app.add_handler(
      MessageHandler(filters.COMMAND & filters.Regex("^/start$"), start_command)
  )
  app.add_handler(
      MessageHandler(
          filters.Document.ALL | filters.TEXT & ~filters.COMMAND,
          handle_document_or_text,
      )
  )

  print("🤖 Telegram Bot সফলভাবে রান হচ্ছে...")
  app.run_polling()


if __name__ == "__main__":
  main()
