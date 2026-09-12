const TelegramBot = require('node-telegram-bot-api');
const axios = require('axios');
const fs = require('fs');

// Railway-এর Environment Variable থেকে সরাসরি বটের টোকেন নেবে অথবা আপনি এখানে টোকেন বসাতে পারেন
const TOKEN = process.env.BOT_TOKEN || "YOUR_TELEGRAM_BOT_TOKEN";
const bot = new TelegramBot(TOKEN, { polling: true });

const DB_FILE = 'database.json';

// ডাটাবেজ লোড করার ফাংশন
function loadDatabase() {
    if (!fs.existsSync(DB_FILE)) {
        return {};
    }
    try {
        return JSON.parse(fs.readFileSync(DB_FILE, 'utf8'));
    } catch (e) {
        return {};
    }
}

// ডাটাবেজ সেভ করার ফাংশন
function saveDatabase(data) {
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
}

// /start কমান্ড
bot.onText(/\/start/, (msg) => {
    const chatId = msg.chat.id;
    const welcomeText = `স্বাগতম! Railway-এর এই বটের মাধ্যমে একসাথে অনেকগুলো USA নম্বর এবং ওটিপি লিংক যোগ করতে পারবেন।\n\n` +
        `📌 **একসাথে বহু নম্বর যোগ করার নিয়ম:**\n` +
        `\`\/addmany\` লিখে নিচে এভাবে নম্বর ও লিংক দিন (প্রতি লাইনে ১টি):\n\n` +
        `\`/addmany\`\n` +
        `+17123826531 https://yourdomain.com/api/sms/link1\n` +
        `+15551112222 https://yourdomain.com/api/sms/link2\n\n` +
        `📋 সব নম্বর দেখতে লিখুন: \`/numbers\``;
    
    bot.sendMessage(chatId, welcomeText, { parse_mode: 'Markdown' });
});

// /addmany কমান্ড (একসাথে ৫০টা বা তার বেশি নম্বর যোগ করতে)
bot.onText(/\/addmany([\s\S]*)/, (msg, match) => {
    const chatId = msg.chat.id.toString();
    const rawText = match[1];
    
    if (!rawText || !rawText.trim()) {
        bot.sendMessage(chatId, "⚠️ সঠিক ফরম্যাটে নম্বর ও লিংক দিন।\nউদাহরণ:\n`/addmany\n+17123826531 https://example.com/api/1`", { parse_mode: 'Markdown' });
        return;
    }

    const lines = rawText.trim().split('\n');
    let count = 0;
    
    let db = loadDatabase();
    if (!db[chatId]) {
        db[chatId] = [];
    }

    lines.forEach(line => {
        line = line.trim();
        if (!line) return;

        const parts = line.split(/\s+/);
        if (parts.length >= 2) {
            const number = parts[0];
            const apiUrl = parts.slice(1).join(' '); // লিংকের ভেতরে স্পেস থাকলে হ্যান্ডেল করার জন্য
            
            db[chatId].push({
                number: number,
                api_url: apiUrl
            });
            count++;
        }
    });

    saveDatabase(db);

    if (count > 0) {
        bot.sendMessage(chatId, `✅ সফলভাবে **${count}টি** নম্বর একসাথে সেভ করা হয়েছে!\nলিস্ট দেখতে \`/numbers\` লিখুন।`, { parse_mode: 'Markdown' });
    } else {
        bot.sendMessage(chatId, "⚠️ কোনো নম্বর বা লিংক খুঁজে পাওয়া যায়নি। দয়া করে সঠিক ফরম্যাটে লিখুন।");
    }
});

// /numbers কমান্ড (সব নম্বর ইনলাইন বাটন আকারে দেখার জন্য)
bot.onText(/\/numbers/, (msg) => {
    const chatId = msg.chat.id.toString();
    const db = loadDatabase();

    if (!db[chatId] || db[chatId].length === 0) {
        bot.sendMessage(chatId, "❌ আপনার কোনো নম্বর সেভ করা নেই। `/addmany` দিয়ে নম্বর যোগ করুন।");
        return;
    }

    const keyboard = [];
    db[chatId].forEach((item, index) => {
        keyboard.push([{
            text: `🇺🇸 ${item.number} (OTP চেক)`,
            callback_data: `check_${chatId}_${index}`
        }]);
    });

    bot.sendMessage(chatId, "আপনার সেভ করা নম্বরগুলোর লিস্ট নিচে দেওয়া হলো। ওটিপি চেক করতে বাটনে ক্লিক করুন:", {
        reply_markup: {
            inline_keyboard: keyboard
        }
    });
});

// ইনলাইন বাটনে ক্লিক করলে ওটিপি চেক করার লজিক
bot.on('callback_query', async (query) => {
    const chatId = query.message.chat.id.toString();
    const data = query.data;

    if (data.startsWith('check_')) {
        const parts = data.split('_');
        const targetChatId = parts[1];
        const index = parseInt(parts[2]);

        const db = loadDatabase();
        if (!db[targetChatId] || !db[targetChatId][index]) {
            bot.answerCallbackQuery(query.id, { text: "নম্ব তথ্য পাওয়া যায়নি!" });
            return;
        }

        const item = db[targetChatId][index];
        bot.answerCallbackQuery(query.id, { text: `Checking ${item.number}...` });

        try {
            // প্রতিটি নম্বরের নিজস্ব আলাদা লিংকে রিকোয়েস্ট পাঠানো হচ্ছে
            const response = await axios.get(item.api_url, { timeout: 10000 });
            const code = typeof response.data === 'string' ? response.data.trim() : JSON.stringify(response.data).trim();

            // ওটিপি কোড (৩ থেকে ১০ ডিজিটের সংখ্যা) এসেছে কি না চেক করা
            if (/^\d{3,10}$/.test(code)) {
                bot.sendMessage(chatId, `🎉 **OTP Received!**\nনম্বর: \`${item.number}\`\nকোড: \`${code}\``, { parse_mode: 'Markdown' });
            } else {
                bot.sendMessage(chatId, `⏳ **${item.number}** নম্বরে এখনও কোনো ওটিপি আসেনি!\n(Current Status: ${code || 'Empty'})`, { parse_mode: 'Markdown' });
            }
        } catch (error) {
            bot.sendMessage(chatId, `❌ **${item.number}** এর লিংক থেকে ডাটা ফেচ করতে সমস্যা হচ্ছে। লিংকটি চেক করুন।`, { parse_mode: 'Markdown' });
        }
    }
});

console.log("Bot is running successfully on Railway...");
