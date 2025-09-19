import logging
import asyncio
import re
import socket

import paramiko
from telegram import Update, ForceReply, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)
from telegram.constants import ParseMode

# --- پیکربندی اولیه لاگ ---
# این بخش لاگ‌ها را طوری تنظیم می‌کند که اطلاعات مفیدی در کنسول نمایش داده شود
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- تعریف مراحل مکالمه ---
# این متغیرها به ربات کمک می‌کنند تا بفهمد در کدام مرحله از گفتگو با کاربر قرار دارد
GET_CREDENTIALS, CONFIRM_INSTALL = range(2)

# --- توکن ربات ---
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# توکن ربات تلگرام خود را در این قسمت داخل "" قرار دهید
BOT_TOKEN = "6070230026:AAHa-zsV_MZa5J3XMcHEKFVZcp-17sQa"
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

# --- متون و پیام‌های ربات ---
MESSAGES = {
    "start": "سلام {user_mention} عزیز! 👋\nبرای شروع نصب پنل، لطفا اطلاعات سرور را با فرمت زیر برای من ارسال کن:\n`host user password`\n\n⚠️ **توجه:** اطلاعات شما بعد از ارسال، برای امنیت بیشتر از چت حذف خواهد شد.",
    "invalid_format": "❌ فرمت اطلاعات ورودی نامعتبر است.\nلطفاً اطلاعات را با فرمت دقیق: `host user password` ارسال کنید.",
    "security_warning": (
        "⚠️ **هشدار امنیتی بسیار مهم** ⚠️\n\n"
        "شما در حال استفاده از اطلاعات حساس سرور خود (نام کاربری و رمز عبور) هستید.\n"
        "این ربات این اطلاعات را *فقط* برای فرآیند نصب استفاده کرده و در حافظه نگه نمی‌دارد.\n\n"
        "🔴 **مسئولیت هرگونه سوءاستفاده از این اطلاعات بر عهده شماست.** 🔴\n\n"
        "برای تأیید و ادامه فرآیند نصب، عبارت دقیق زیر را ارسال کنید:\n`CONFIRM INSTALL`"
    ),
    "confirmation_received": "✅ تأیید دریافت شد. در حال آماده‌سازی برای نصب پنل... لطفاً صبور باشید. 🚀",
    "installation_success": "🎉 نصب پنل با موفقیت به پایان رسید!",
    "installation_failed": "😥 متاسفانه نصب پنل با شکست مواجه شد.\nلطفاً لاگ‌های سرور و اطلاعات ورودی را بررسی کنید. جزئیات خطا در زیر ارسال می‌شود.",
    "details_sent": "✨ جزئیات پنل با موفقیت استخراج و ارسال شد.",
    "server_info_not_found": "خطا: اطلاعات سرور پیدا نشد. 😟 لطفاً فرآیند را با /start مجدداً شروع کنید.",
    "invalid_confirmation": "😕 تأیید نامعتبر است. برای ادامه `CONFIRM INSTALL` را ارسال کنید یا برای لغو /cancel را بزنید.",
    "operation_cancelled": "🚫 عملیات توسط شما لغو شد.",
    "error_auth": "🚫 **خطای احراز هویت!**\nنام کاربری یا رمز عبور اشتباه است. لطفاً با /start مجدد تلاش کنید.",
    "error_connection": "🔌 **خطای اتصال!**\nامکان اتصال به هاست `{host}` وجود ندارد. لطفاً آدرس هاست و وضعیت فایروال را بررسی کنید.",
    "error_ssh": "⚙️ **خطای SSH!**\nیک مشکل در ارتباط SSH رخ داده است: {error}",
    "error_generic": "😟 یک خطای پیش‌بینی نشده رخ داد: {error}",
}

# --- تابع اصلی نصب (مسدود کننده) ---
def install_panel_and_get_details(host, user, password):
    """
    به سرور متصل شده، پنل را نصب کرده و اطلاعات آن را برمی‌گرداند.
    این یک تابع مسدود کننده (blocking) است و باید در یک ترد جداگانه اجرا شود.
    """
    client = None
    output = ""
    error_output = ""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        logger.info(f"Connecting to {host}...")
        client.connect(hostname=host, username=user, password=password, timeout=30)
        logger.info("Connection successful.")

        install_command = "bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)"
        logger.info(f"Executing command: {install_command}")
        
        # get_pty=True برای اجرای دستوراتی که نیاز به ترمینال تعاملی دارند مفید است
        stdin, stdout, stderr = client.exec_command(install_command, get_pty=True)

        # خواندن خروجی به صورت زنده
        for line in iter(stdout.readline, ""):
            logger.info(line.strip())
            output += line

        exit_status = stdout.channel.recv_exit_status()
        logger.info(f"Command finished with exit status: {exit_status}")

        error_output = stderr.read().decode('utf-8', errors='ignore')
        if error_output:
            logger.error(f"Installation stderr: {error_output}")
        
        if exit_status != 0:
            logger.error("Installation script failed.")
            raise Exception(f"اسکریپت نصب با خطا مواجه شد.\nخروجی خطا:\n{error_output}")


        # استخراج اطلاعات پنل با استفاده از re
        # این الگوها کمی انعطاف‌پذیرتر نوشته شده‌اند تا با تغییرات جزئی در خروجی هم کار کنند
        details_pattern = re.compile(
            r".*Username:\s*(\S+)\s*\n"
            r".*Password:\s*(\S+)\s*\n"
            r".*Port:\s*(\d+)\s*\n"
            r".*Access URL:\s*(http[s]?://\S+)",
            re.DOTALL | re.IGNORECASE
        )
        match = details_pattern.search(output)

        if match:
            username, pwd, port, url = match.groups()
            details = (
                f"###############################################\n"
                f"مشخصات پنل نصب شده:\n"
                f"-----------------------------------------------\n"
                f"نام کاربری: {username}\n"
                f"رمز عبور: {pwd}\n"
                f"پورت: {port}\n"
                f"آدرس دسترسی: {url}\n"
                f"###############################################"
            )
            return {"success": True, "data": details}
        else:
            logger.warning("Could not extract panel details from the output.")
            return {"success": False, "error": "امکان استخراج جزئیات پنل از خروجی اسکریپت وجود نداشت.", "log": output}

    # مدیریت خطاهای خاص برای ارائه بازخورد بهتر
    except paramiko.AuthenticationException:
        logger.error(f"Authentication failed for {user}@{host}")
        return {"success": False, "error": MESSAGES["error_auth"]}
    except (socket.timeout, paramiko.SSHException) as e:
        logger.error(f"Connection error to {host}: {e}")
        return {"success": False, "error": MESSAGES["error_connection"].format(host=host)}
    except Exception as e:
        logger.error(f"An exception occurred: {e}")
        full_log = f"--- Error Log ---\n{error_output}\n\n--- Full Log ---\n{output}"
        return {"success": False, "error": str(e), "log": full_log}
    finally:
        if client and client.get_transport() and client.get_transport().is_active():
            client.close()
            logger.info("Connection closed.")


# --- توابع ربات (Handlers) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """شروع مکالمه و درخواست اطلاعات سرور"""
    user = update.effective_user
    await update.message.reply_html(
        MESSAGES["start"].format(user_mention=user.mention_html()),
        reply_markup=ForceReply(selective=True),
    )
    return GET_CREDENTIALS


async def handle_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ذخیره اطلاعات سرور و درخواست تایید"""
    credentials_text = update.message.text
    
    # برای امنیت، پیام حاوی اطلاعات حساس را بلافاصله حذف می‌کنیم
    try:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
        logger.info("User credentials message deleted successfully.")
    except Exception as e:
        logger.warning(f"Could not delete message: {e}")

    credentials = credentials_text.strip().split()
    if len(credentials) == 3:
        host, user, password = credentials
        context.user_data['credentials'] = {'host': host, 'user': user, 'password': password}
        await update.message.reply_text(MESSAGES["security_warning"], parse_mode=ParseMode.MARKDOWN)
        return CONFIRM_INSTALL
    else:
        await update.message.reply_text(MESSAGES["invalid_format"])
        # پایان مکالمه در صورت فرمت اشتباه
        return ConversationHandler.END


async def confirm_install(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """تایید و شروع فرآیند نصب"""
    if update.message.text.strip().upper() == "CONFIRM INSTALL":
        credentials = context.user_data.get('credentials')
        if not credentials:
            await update.message.reply_text(MESSAGES["server_info_not_found"])
            return ConversationHandler.END

        await update.message.reply_text(MESSAGES["confirmation_received"])

        # اجرای تابع مسدود کننده در یک ترد جداگانه تا ربات قفل نشود
        result = await asyncio.to_thread(
            install_panel_and_get_details,
            credentials['host'],
            credentials['user'],
            credentials['password']
        )

        if result["success"]:
            await update.message.reply_text(MESSAGES["installation_success"])
            # استفاده از تگ code برای نمایش بهتر
            await update.message.reply_text(f"<code>{result['data']}</code>", parse_mode=ParseMode.HTML)
            await update.message.reply_text(MESSAGES["details_sent"])
        else:
            error_message = result.get("error", "یک خطای نامشخص رخ داد.")
            await update.message.reply_text(MESSAGES["installation_failed"])
            # ارسال پیام خطا به کاربر
            await update.message.reply_text(f"<b>جزئیات خطا:</b>\n{error_message}", parse_mode=ParseMode.HTML)
            
            # اگر لاگ کامل وجود داشت، آن را هم ارسال می‌کنیم
            if "log" in result and result["log"]:
                 # ارسال لاگ در یک تگ pre برای حفظ فرمت
                log_text = result['log']
                # برای جلوگیری از طولانی شدن بیش از حد پیام، آن را کوتاه می‌کنیم
                if len(log_text) > 3500:
                    log_text = "... (بخش پایانی لاگ) ...\n" + log_text[-3500:]
                await update.message.reply_text(f"<b>خروجی کامل اسکریپت:</b>\n<pre>{log_text}</pre>", parse_mode=ParseMode.HTML)
        
        # پاک کردن اطلاعات حساس پس از اتمام کار
        if 'credentials' in context.user_data:
            del context.user_data['credentials']
        return ConversationHandler.END

    else:
        await update.message.reply_text(MESSAGES["invalid_confirmation"])
        return CONFIRM_INSTALL


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """لغو و پایان مکالمه"""
    user = update.effective_user
    await update.message.reply_text(
        MESSAGES["operation_cancelled"].format(user_mention=user.mention_html()),
        reply_markup=ReplyKeyboardRemove(),  # حذف کیبورد اجباری
    )
    if 'credentials' in context.user_data:
        del context.user_data['credentials']
    return ConversationHandler.END


def main() -> None:
    """راه اندازی ربات"""
    if not BOT_TOKEN or "YOUR_BOT_TOKEN" in BOT_TOKEN:
        logger.error("توکن ربات تنظیم نشده است! لطفاً توکن ربات خود را در متغیر BOT_TOKEN قرار دهید.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # تعریف ConversationHandler برای مدیریت مکالمه چند مرحله‌ای
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_CREDENTIALS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_credentials)],
            CONFIRM_INSTALL: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_install)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True, # مکالمه برای هر کاربر مجزا خواهد بود
        conversation_timeout=600 # مکالمه بعد از ۱۰ دقیقه عدم فعالیت، لغو می‌شود
    )

    application.add_handler(conv_handler)
    logger.info("Bot started. Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
