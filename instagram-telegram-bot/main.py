import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from instagrapi import Client
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "🤖 Instagram Login Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

user_sessions = {}

class InstagramBot:
    def __init__(self):
        self.client = None
        self.is_logged_in = False
        self.username = None
        self.login_data = {}
    
    def login_with_email(self, email, password):
        """Login to Instagram using email"""
        try:
            self.client = Client()
            self.client.login(email, password)
            self.is_logged_in = True
            self.username = self.client.username
            return True, f"✅ Successfully logged in as @{self.username}!"
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Login failed for {email}: {error_msg}")
            
            # Check if 2FA is required
            if "challenge" in error_msg.lower() or "two factor" in error_msg.lower():
                return "2FA", "🔐 Two-Factor Authentication required. Please enter your 6-digit verification code:"
            elif "check your email" in error_msg.lower():
                return "wait", "📧 Instagram sent a verification email. Please check your email and try again."
            else:
                return False, f"❌ Login failed: {error_msg}"
    
    def verify_2fa(self, code):
        """Verify 2FA code"""
        try:
            self.client.login(username=self.client.username, password=self.client.password)
            self.client.login_flow()
            return True, "✅ 2FA verified! Successfully logged in!"
        except Exception as e:
            return False, f"❌ 2FA verification failed: {str(e)}"
    
    def check_login(self):
        return self.is_logged_in
    
    def logout(self):
        if self.client:
            try:
                self.client.logout()
            except:
                pass
        self.is_logged_in = False
        self.username = None
        self.client = None

def get_user_bot(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = InstagramBot()
    return user_sessions[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    bot = get_user_bot(user_id)
    
    if bot.check_login():
        keyboard = [
            [InlineKeyboardButton("🚪 Logout", callback_data='logout')],
            [InlineKeyboardButton("🔄 Check Status", callback_data='status')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"👋 Hello {user.first_name}!\n"
            f"✅ You are already logged in as @{bot.username}\n\n"
            f"What would you like to do?",
            reply_markup=reply_markup
        )
    else:
        keyboard = [
            [InlineKeyboardButton("🔐 Login with Email", callback_data='login_email')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"👋 Hello {user.first_name}!\n\n"
            f"🔐 Click below to login to Instagram with your email:\n\n"
            f"⚠️ Your credentials are used only for this session",
            reply_markup=reply_markup
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    bot = get_user_bot(user_id)
    
    if query.data == 'login_email':
        await query.edit_message_text(
            "🔐 **Enter your Instagram credentials**\n\n"
            "Send your **email** and **password** in this format:\n"
            "`email:password`\n\n"
            "Example: `myemail@gmail.com:MyPass123`\n\n"
            "⚠️ Your credentials will NOT be stored permanently\n"
            "⚠️ They are used only for this session",
            parse_mode='Markdown'
        )
        context.user_data['action'] = 'login_email'
    
    elif query.data == 'login_username':
        await query.edit_message_text(
            "🔐 **Enter your Instagram credentials**\n\n"
            "Send your **username** and **password** in this format:\n"
            "`username:password`\n\n"
            "⚠️ Your credentials will NOT be stored permanently\n"
            "⚠️ They are used only for this session",
            parse_mode='Markdown'
        )
        context.user_data['action'] = 'login_username'
    
    elif query.data == 'status':
        if bot.check_login():
            await query.edit_message_text(
                f"✅ **You are logged in**\n\n"
                f"👤 Username: @{bot.username}\n"
                f"🔐 Session: Active\n\n"
                f"Use /start to see options"
            )
        else:
            await query.edit_message_text(
                "❌ **You are not logged in**\n\n"
                "Use /start to login"
            )
    
    elif query.data == 'logout':
        bot.logout()
        keyboard = [[InlineKeyboardButton("🔐 Login Again", callback_data='login_email')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🚪 **Successfully logged out!**\n\n"
            "Your session has been ended.",
            reply_markup=reply_markup
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot = get_user_bot(user_id)
    
    action = context.user_data.get('action')
    
    if action == 'login_email':
        try:
            text = update.message.text
            if ':' not in text:
                await update.message.reply_text(
                    "❌ **Invalid format!**\n\n"
                    "Please use:\n"
                    "`email:password`\n\n"
                    "Example: `myemail@gmail.com:MyPass123`",
                    parse_mode='Markdown'
                )
                return
            
            email, password = text.split(':', 1)
            email = email.strip()
            password = password.strip()
            
            if not email or not password:
                await update.message.reply_text(
                    "❌ **Email or password cannot be empty!**\n\n"
                    "Please send again in format:\n"
                    "`email:password`",
                    parse_mode='Markdown'
                )
                return
            
            await update.message.reply_text("⏳ Logging in to Instagram...")
            result, message = bot.login_with_email(email, password)
            
            if result == True:
                keyboard = [
                    [InlineKeyboardButton("🚪 Logout", callback_data='logout')],
                    [InlineKeyboardButton("🔄 Check Status", callback_data='status')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"{message}\n\n"
                    f"What would you like to do next?",
                    reply_markup=reply_markup
                )
                context.user_data.pop('action', None)
            
            elif result == "2FA":
                await update.message.reply_text(
                    f"{message}\n\n"
                    "Please send your 6-digit verification code:"
                )
                context.user_data['action'] = '2fa_verify'
            
            elif result == "wait":
                await update.message.reply_text(
                    f"{message}\n\n"
                    "Once you've verified in your email, try logging in again."
                )
                context.user_data.pop('action', None)
            
            else:
                keyboard = [[InlineKeyboardButton("🔐 Try Again", callback_data='login_email')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"{message}\n\n"
                    f"Would you like to try again?",
                    reply_markup=reply_markup
                )
                context.user_data.pop('action', None)
            
        except Exception as e:
            logger.error(f"Error in login: {e}")
            await update.message.reply_text(
                f"❌ **An error occurred:** {str(e)}\n\n"
                "Please try again with /start"
            )
            context.user_data.pop('action', None)
    
    elif action == '2fa_verify':
        try:
            code = update.message.text.strip()
            if len(code) != 6 or not code.isdigit():
                await update.message.reply_text(
                    "❌ **Invalid code!**\n\n"
                    "Please send a valid 6-digit verification code.\n"
                    "Example: `123456`",
                    parse_mode='Markdown'
                )
                return
            
            await update.message.reply_text("⏳ Verifying 2FA code...")
            success, message = bot.verify_2fa(code)
            
            if success:
                keyboard = [
                    [InlineKeyboardButton("🚪 Logout", callback_data='logout')],
                    [InlineKeyboardButton("🔄 Check Status", callback_data='status')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"{message}\n\n"
                    f"What would you like to do next?",
                    reply_markup=reply_markup
                )
            else:
                keyboard = [[InlineKeyboardButton("🔐 Try Again", callback_data='login_email')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"{message}\n\n"
                    f"Please try logging in again.",
                    reply_markup=reply_markup
                )
            
            context.user_data.pop('action', None)
            
        except Exception as e:
            logger.error(f"Error in 2FA: {e}")
            await update.message.reply_text(
                f"❌ **An error occurred:** {str(e)}\n\n"
                "Please try again with /start"
            )
            context.user_data.pop('action', None)
    
    else:
        await update.message.reply_text(
            "🤖 I only handle Instagram login.\n\n"
            "Use /start to begin."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Instagram Login Bot**\n\n"
        "This bot handles Instagram login with email or username.\n\n"
        "Commands:\n"
        "/start - Start the bot and login\n"
        "/help - Show this help message\n\n"
        "⚠️ Your credentials are NOT stored permanently",
        parse_mode='Markdown'
    )

def main():
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN not found in environment variables!")
        print("Please add it to Replit Secrets.")
        return
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Instagram Login Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    keep_alive()
    main()
