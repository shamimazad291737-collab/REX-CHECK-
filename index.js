require('dotenv').config();
const { Telegraf } = require('telegraf');
const axios = require('axios');

const bot = new Telegraf(process.env.BOT_TOKEN);

bot.start((ctx) => {
    ctx.reply('স্বাগতম! ওটিপি চেক করার জন্য একটি `.txt` ফাইল আপলোড করুন, যার প্রতি লাইনে একটি করে লিংক বা API ইউআরএল থাকবে।');
});

// যখন ইউজার কোনো ডকুমেন্ট বা ফাইল আপলোড করবে
bot.on('document', async (ctx) => {
    const document = ctx.message.document;

    // চেক করা ফাইলটি txt ফরম্যাটের কি না
    if (!document.file_name.endsWith('.txt')) {
        return ctx.reply('❌ দয়া করে শুধুমাত্র `.txt` ফরম্যাটের ফাইল আপলোড করুন।');
    }

    const processingMsg = await ctx.reply('⏳ ফাইল প্রসেস করা হচ্ছে এবং লিংকগুলো চেক করা হচ্ছে, দয়া করে অপেক্ষা করুন...');

    try {
        // টেলিগ্রাম সার্ভার থেকে ফাইল ডাউনলোড লিংক নেওয়া
        const fileLink = await bot.telegram.getFileLink(document.file_id);
        const response = await axios.get(fileLink.href);
        const fileContent = response.data;

        // লাইন বাই লাইন লিংক আলাদা করা এবং খালি লাইন ফিল্টার করা
        const links = fileContent.split(/\r?\n/).map(line => line.trim()).filter(line => line.length > 0);

        if (links.length === 0) {
            await bot.telegram.editMessageText(ctx.chat.id, processingMsg.message_id, null, '❌ ফাইলটি ফাঁকা বা কোনো লিংক পাওয়া যায়নি।');
            return;
        }

        await bot.telegram.editMessageText(ctx.chat.id, processingMsg.message_id, null, `🔍 মোট ${links.length} টি লিংক পাওয়া গেছে। চেকিং চলছে...`);

        let successResults = [];
        let failedResults = [];

        // একসাথে সব লিংক চেক করার জন্য লুপ (Promise.all ব্যবহার করা হয়েছে দ্রুততার জন্য)
        await Promise.all(links.map(async (url) => {
            // যদি লিংক ফরম্যাট ঠিক না থাকে
            if (!url.startsWith('http://') && !url.startsWith('https://')) {
                failedResults.push(`❌ ${url} (ভুল ফরম্যাট)`);
                return;
            }

            try {
                // আপনার দেওয়া সোর্স কোডের লজিক অনুযায়ী ফেচ করা
                const res = await axios.get(url, { 
                    headers: { 'Cache-Control': 'no-store' },
                    timeout: 8000 
                });
                
                const text = String(res.data).trim();

                // ওটিপি বা ডিজিট ম্যাচ করলে (৩ থেকে ১০ ডিজিট)
                if (/^\d{3,10}$/.test(text)) {
                    successResults.push(`✅ **OTP Found:** \`${text}\`\n🔗 Link: ${url}`);
                } else {
                    failedResults.push(`⏳ Waiting / No Code yet\n🔗 Link: ${url}`);
                }
            } catch (err) {
                failedResults.push(`❌ Dead/Error\n🔗 Link: ${url}`);
            }
        }));

        // ফাইনাল রেজাল্ট সাজিয়ে পাঠানো
        let report = `📊 **চেকিং রিপোর্ট (Total: ${links.length})**\n\n`;
        
        if (successResults.length > 0) {
            report += `🎯 **সফল লিংকসমূহ (OTP পাওয়া গেছে):**\n` + successResults.join('\n\n') + `\n\n-------------------\n\n`;
        } else {
            report += `🎯 **সফল লিংকসমূহ:** কোনো ওটিপি পাওয়া যায়নি।\n\n-------------------\n\n`;
        }

        if (failedResults.length > 0) {
            report += `⚠️ **বাকি লিংকসমূহ (অপেক্ষমাণ/ডেড):**\n` + failedResults.join('\n\n');
        }

        // টেলিগ্রাম মেসেজ বড় হলে স্লিপ করে পাঠানো যেতে পারে, তবে ছোট ফাইলের জন্য একবারে পাঠানো যাবে
        if (report.length > 4000) {
            await ctx.reply('⚠️ রেজাল্ট অনেক বড়, তাই শুধু সফল ওটিপিগুলো নিচে দেওয়া হলো:');
            if (successResults.length > 0) {
                await ctx.reply(successResults.join('\n\n'), { parse_mode: 'Markdown' });
            } else {
                await ctx.reply('কোনো ওটিপি পাওয়া যায়নি।');
            }
        } else {
            await ctx.reply(report, { parse_mode: 'Markdown' });
        }

    } catch (error) {
        console.error(error);
        await ctx.reply(`❌ প্রসেসিং করার সময় একটি সমস্যা হয়েছে: ${error.message}`);
    }
});

bot.launch();
console.log('Bot is running successfully...');

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));