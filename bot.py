import logging
import asyncio
import re
import random
from datetime import datetime, timedelta
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from config import Config
from database import Database

# ==================== SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

db = Database()

# ==================== RATE LIMITER ====================
class RateLimiter:
    def __init__(self):
        self.user_limits = defaultdict(list)
        self.MAX_REQUESTS = 10
        self.TIME_WINDOW = 60
    
    def is_allowed(self, user_id):
        now = datetime.now().timestamp()
        self.user_limits[user_id] = [
            t for t in self.user_limits[user_id] 
            if now - t < self.TIME_WINDOW
        ]
        if len(self.user_limits[user_id]) >= self.MAX_REQUESTS:
            return False
        self.user_limits[user_id].append(now)
        return True

rate_limiter = RateLimiter()

# ==================== UTILITY FUNCTIONS ====================

def is_emoji_only(text):
    if not text:
        return False
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    cleaned = emoji_pattern.sub('', text).strip()
    return len(cleaned) == 0 and len(text) > 0

def get_user_info(user):
    bio = user.bio if user.bio else "မရှိပါ"
    return {
        "name": user.first_name or "Unknown",
        "user_id": user.id,
        "username": f"@{user.username}" if user.username else "No username",
        "bio": bio
    }

def get_start_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 Channel", url=Config.CHANNEL_LINK)],
        [InlineKeyboardButton("🤖 Group သို့ထည့်ရန်", url=Config.BOT_LINK)],
        [InlineKeyboardButton("🧸 Help Mya", callback_data="help_mya")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_welcome_keyboard(bot_username):
    keyboard = [
        [InlineKeyboardButton("➕ Group ထဲထည့်ရန်", url=f"https://t.me/{bot_username}?startgroup=start")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_public_help_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 Channel", url=Config.CHANNEL_LINK)],
        [InlineKeyboardButton("🛡️ Admin Help", callback_data="help_admin")],
        [InlineKeyboardButton("❌ ပိတ်ရန်", callback_data="help_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_help_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔨 Ban/Mute/Unmute", callback_data="admin_ban"),
         InlineKeyboardButton("🎬 Welcome Video", callback_data="admin_welcome")],
        [InlineKeyboardButton("🔗 Link စနစ်", callback_data="admin_link"),
         InlineKeyboardButton("👥 Admin စီမံ", callback_data="admin_manage")],
        [InlineKeyboardButton("🔙 နောက်သို့", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_owner_help_keyboard():
    keyboard = [
        [InlineKeyboardButton("👑 Owner Commands", callback_data="owner_commands"),
         InlineKeyboardButton("📚 Teach List", callback_data="owner_teachlist")],
        [InlineKeyboardButton("🎬 Video Settings", callback_data="owner_video"),
         InlineKeyboardButton("🏷️ Media Settings", callback_data="owner_media")],
        [InlineKeyboardButton("📊 Stats & Storage", callback_data="owner_stats"),
         InlineKeyboardButton("🧹 Clean Commands", callback_data="owner_clean")],
        [InlineKeyboardButton("🔙 နောက်သို့", callback_data="owner_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_delete_keyboard(message_id, user_id):
    keyboard = [
        [InlineKeyboardButton("🗑️ ဖျက်ရန်", callback_data=f"delete_{message_id}_{user_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def extract_links(text):
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+])+'
        r'|(?:www\.)[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+'
        r'|t\.me/[a-zA-Z0-9_]+'
        r'|telegram\.me/[a-zA-Z0-9_]+'
    )
    return url_pattern.findall(text)

def is_allowed_link(link, allowed_domains):
    if not allowed_domains:
        return False
    for domain in allowed_domains:
        if domain in link:
            return True
    return False

async def send_typing_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
    except:
        pass

async def is_group_admin(context, chat_id, user_id):
    try:
        chat_admins = await context.bot.get_chat_administrators(chat_id)
        admin_ids = [admin.user.id for admin in chat_admins]
        return user_id in admin_ids
    except:
        return False

# ==================== START ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_info = get_user_info(user)
        
        if db.start_video:
            try:
                video = db.start_video
                caption = video.get('caption', '') + "\n\n" + Config.START_TEXT.format(**user_info)
                await update.message.reply_video(
                    video=video['file_id'],
                    caption=caption,
                    reply_markup=get_start_keyboard()
                )
                return
            except Exception as e:
                logger.error(f"Start video error: {e}")
        
        await update.message.reply_text(
            Config.START_TEXT.format(**user_info),
            reply_markup=get_start_keyboard()
        )
    except Exception as e:
        logger.error(f"Start error: {e}")

# ==================== HELP ====================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        is_owner = (user_id == Config.OWNER_ID)
        is_admin = await is_group_admin(context, chat_id, user_id)
        
        if is_owner:
            role = "👑 Owner"
        elif is_admin:
            role = "🛡️ Admin"
        else:
            role = "👤 Member"
        
        help_text = (
            f"🧸 **အသုံးပြုပုံလမ်းညွှန်** 🧸\n\n"
            f"👤 {user.first_name}\n"
            f"📌 အဆင့်: **{role}**\n"
            f"🌷🌷🌷\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 **အမြန်အသုံးပြုနည်း**\n"
            f"• `/start` - Bot ကိုစတင်ရန်\n"
            f"• `/help` - လမ်းညွှန်ကြည့်ရန်\n"
            f"• `/report` - Admin ကိုအကြောင်းကြားရန်\n\n"
            f"💡 အောက်ပါခလုပ်များကိုနှိပ်ပြီး လေ့လာပါ။"
        )
        
        keyboard = get_public_help_keyboard()
        
        if is_owner:
            new_keyboard = [
                [InlineKeyboardButton("👑 Owner Help", callback_data="help_owner")]
            ]
            new_keyboard.extend(keyboard.inline_keyboard)
            keyboard.inline_keyboard = new_keyboard
        
        await update.message.reply_text(
            help_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Help error: {e}")

# ==================== HELP CALLBACK ====================
async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        data = query.data
        
        is_owner = (user_id == Config.OWNER_ID)
        is_admin = await is_group_admin(context, chat_id, user_id)
        
        # ===== HELP MYA =====
        if data == "help_mya":
            text = Config.HELP_MYA_TEXT + "\n\n"
            keyboard = []
            
            if is_owner:
                keyboard.append([InlineKeyboardButton("👑 Owner Help", callback_data="help_owner")])
            
            keyboard.append([InlineKeyboardButton("📢 Channel", url=Config.CHANNEL_LINK)])
            keyboard.append([InlineKeyboardButton("🛡️ Admin Help", callback_data="help_admin")])
            keyboard.append([InlineKeyboardButton("❌ ပိတ်ရန်", callback_data="help_close")])
            
            await query.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return
        
        # ===== PUBLIC HELP =====
        elif data == "help_faq":
            text = (
                "❓ **အမေးများတဲ့မေးခွန်းများ**\n\n"
                "**Q: Bot က ဘာတွေလုပ်ပေးလဲ?**\n"
                "A: Report ပို့တာ၊ Video/Sticker/Photo ပြန်ပို့တာ။\n\n"
                "**Q: Admin ကိုဘယ်လိုအကြောင်းကြားမလဲ?**\n"
                "A: `/report ပြဿနာ` လို့ရိုက်ပါ။\n\n"
                "**Q: Bot က စာတွေဘယ်လောက်သိမ်းလဲ?**\n"
                "A: 512 MB သိမ်းလို့ရတယ်။ ပြည့်ရင် အလိုအလျောက်ဖျက်တယ်။\n\n"
                "**Q: ဘယ်သူတွေသုံးလို့ရလဲ?**\n"
                "A: အားလုံးသုံးလို့ရတယ်။"
            )
        
        # ===== ADMIN HELP =====
        elif data == "help_admin":
            text = "🛡️ **Admin Help**\n\nGroup Admin တွေအတွက် သီးသန့်လမ်းညွှန်ပါ။"
            await query.message.edit_text(
                text,
                reply_markup=get_admin_help_keyboard()
            )
            return
        
        elif data == "admin_ban":
            text = (
                "🔨 **Ban / Mute / Unmute**\n\n"
                "📌 **သုံးနည်း**\n"
                "User ကို reply ထောက်ပြီး command ရိုက်ပါ။\n\n"
                "📌 **Commands**\n"
                "• `/ban [အကြောင်း]` - Ban\n"
                "• `/unban` - Unban\n"
                "• `/mute [မိနစ်]` - Mute\n"
                "• `/unmute` - Unmute"
            )
        elif data == "admin_welcome":
            text = (
                "🎬 **Welcome Video**\n\n"
                "📌 **Commands**\n"
                "• `/setwelcomevideo` (Reply) - သတ်မှတ်\n"
                "• `/deletewelcomevideo` - ဖျက်"
            )
        elif data == "admin_link":
            text = (
                "🔗 **Link စနစ်**\n\n"
                "📌 **Commands**\n"
                "• `/linkon` - ဖွင့်\n"
                "• `/linkoff` - ပိတ်\n"
                "• `/adddomain domain.com` - Domain ထည့်\n"
                "• `/removedomain domain.com` - Domain ဖယ်"
            )
        elif data == "admin_manage":
            text = (
                "👥 **Admin စီမံ**\n\n"
                "📌 **Commands**\n"
                "• `/addadmin` (Reply) - Admin ထည့်\n"
                "• `/removeadmin` (Reply) - Admin ဖယ်"
            )
        elif data == "admin_back":
            await query.message.edit_text(
                "🛡️ **Admin Help**\n\nအောက်ပါခလုပ်များကိုနှိပ်ပြီး လေ့လာပါ။",
                reply_markup=get_admin_help_keyboard()
            )
            return
        
        # ===== OWNER HELP =====
        elif data == "help_owner":
            if not is_owner:
                await query.message.edit_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
                return
            
            text = "👑 **Owner Help**\n\nBot Owner အတွက် သီးသန့်လမ်းညွှန်ပါ။"
            await query.message.edit_text(
                text,
                reply_markup=get_owner_help_keyboard()
            )
            return
        
        elif data == "owner_commands" and is_owner:
            text = (
                "👑 **Owner Commands**\n\n"
                "📌 **Video**\n"
                "• `/setstartvideo` (Reply) - Start Video\n"
                "• `/deletestartvideo` - ဖျက်\n"
                "• `/setleavevideo` (Reply) - Leave Video\n"
                "• `/deleteleavevideo` - ဖျက်\n\n"
                "📌 **Media**\n"
                "• Sticker/Photo ပို့ရင် အလိုအလျောက်သိမ်း\n"
                "• `/liststickers` - Sticker စာရင်း\n"
                "• `/clearstickers` - အကုန်ဖျက်\n\n"
                "📌 **Teach**\n"
                "• `/teach` (Reply) - စာသင်ပေး\n"
                "• `/listqa` - စာရင်း\n"
                "• `/deleteqa` - ဖျက်\n"
                "• `/clearqa` - အကုန်ဖျက်\n\n"
                "📌 **Stats**\n"
                "• `/todaystats` - ဒီနေ့\n"
                "• `/weekstats` - တစ်ပတ်\n"
                "• `/monthstats` - တစ်လ\n"
                "• `/allstats` - စုစုပေါင်း\n"
                "• `/storage` - Storage\n"
                "• `/forceclean` - နေရာရှင်း"
            )
        elif data == "owner_teachlist" and is_owner:
            qa_list = await db.get_all_qa()
            if not qa_list:
                text = "📚 သင်ပေးထားတာမရှိသေးပါဘူး။"
            else:
                text = "📚 **သင်ပေးထားတဲ့စာရင်း**\n\n"
                for i, q in enumerate(qa_list[:30], 1):
                    text += f"{i}. {q['question'][:40]}...\n"
                if len(qa_list) > 30:
                    text += f"\n... နောက်ထပ် {len(qa_list) - 30} ခုရှိပါသေးတယ်။"
                text += f"\n\n📊 စုစုပေါင်း: {len(qa_list)} ခု"
        elif data == "owner_video" and is_owner:
            text = (
                f"🎬 **Video Settings**\n\n"
                f"• Start Video: {'✅ ရှိ' if db.start_video else '❌ မရှိ'}\n"
                f"• Welcome Video: {'✅ ရှိ' if db.welcome_video else '❌ မရှိ'}\n"
                f"• Leave Video: {'✅ ရှိ' if db.leave_video else '❌ မရှိ'}"
            )
        elif data == "owner_media" and is_owner:
            stickers = await db.get_all_stickers()
            photos = await db.get_all_photos()
            text = (
                f"🏷️ **Media Settings**\n\n"
                f"• Sticker: {stickers} ခု\n"
                f"• Photo: {photos} ခု"
            )
        elif data == "owner_stats" and is_owner:
            stats = await db.get_all_stats()
            total = await db.messages.count_documents({})
            estimated_mb = (total * 500) / 1024 / 1024
            text = (
                f"📊 **Stats & Storage**\n\n"
                f"📝 စာ: {stats['total']:,} ကြောင်း\n"
                f"💾 နေရာ: {estimated_mb:.2f} MB / 512 MB"
            )
        elif data == "owner_clean" and is_owner:
            text = (
                "🧹 **Clean Commands**\n\n"
                "• `/forceclean` - နေရာရှင်း\n"
                "• `/clearmessages` - အကုန်ဖျက်\n"
                "• `/cleanmessages` - သန့်ရှင်းပေး"
            )
        elif data == "owner_back" and is_owner:
            await query.message.edit_text(
                "👑 **Owner Help**\n\nအောက်ပါခလုပ်များကိုနှိပ်ပြီး လေ့လာပါ။",
                reply_markup=get_owner_help_keyboard()
            )
            return
        
        elif data == "help_close":
            await query.message.delete()
            return
        
        else:
            text = "အချက်အလက်မရှိပါ။"
        
        await query.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 နောက်သို့", callback_data="help_back")]
            ])
        )
    except Exception as e:
        logger.error(f"Help callback error: {e}")

# ==================== HELP BACK ====================
async def help_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        is_owner = (user_id == Config.OWNER_ID)
        
        keyboard = get_public_help_keyboard()
        
        if is_owner:
            new_keyboard = [
                [InlineKeyboardButton("👑 Owner Help", callback_data="help_owner")]
            ]
            new_keyboard.extend(keyboard.inline_keyboard)
            keyboard.inline_keyboard = new_keyboard
        
        await query.message.edit_text(
            "📌 **ဘာကိုလေ့လာချင်လဲ?**\n\n"
            "အောက်ပါခလုပ်များကိုနှိပ်ပြီး အသေးစိတ်ကြည့်ပါ။",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Help back error: {e}")

# ==================== TEACH ====================
async def teach_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text(
                "⚠️ အဖြေစာသားကို reply ထောက်ပြီး `/teach မေးခွန်း` လုပ်ပါ။"
            )
            return
        
        if not context.args:
            await update.message.reply_text("⚠️ မေးခွန်းထည့်ပါ။")
            return
        
        question = " ".join(context.args)
        answer = update.message.reply_to_message.text
        
        if not answer:
            await update.message.reply_text("⚠️ Reply ထောက်ထားတာက စာသားမဟုတ်ပါဘူး။")
            return
        
        await db.save_qa(question, answer, user_id)
        count = await db.get_qa_count()
        
        await update.message.reply_text(
            f"✅ **သင်ပြီးပါပြီ!**\n\n"
            f"📝 **မေးခွန်း:** {question}\n"
            f"📝 **အဖြေ:** {answer[:100]}{'...' if len(answer) > 100 else ''}\n\n"
            f"📊 စုစုပေါင်း: {count} ခု"
        )
    except Exception as e:
        logger.error(f"Teach error: {e}")

# ==================== REPORT ====================
async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        user = update.effective_user
        
        if not context.args:
            await update.message.reply_text("⚠️ /report [ပြဿနာ]")
            return
        
        issue = " ".join(context.args)
        admins = await db.get_group_admins(chat_id)
        
        if not admins:
            try:
                chat_admins = await context.bot.get_chat_administrators(chat_id)
                admins = [admin.user.id for admin in chat_admins]
                await db.save_group_admins(chat_id, admins)
            except:
                await update.message.reply_text("❌ Admin ရှာမတွေ့။")
                return
        
        admin_mentions = []
        for admin_id in admins[:5]:
            try:
                admin = await context.bot.get_chat(admin_id)
                if admin.username:
                    admin_mentions.append(f"@{admin.username}")
                else:
                    admin_mentions.append(f"[Admin](tg://user?id={admin_id})")
            except:
                admin_mentions.append(f"[Admin](tg://user?id={admin_id})")
        
        report_msg = (
            f"🚨 **အရေးပေါ်အကြောင်းကြားချက်** 🚨\n\n"
            f"👤 {user.first_name}\n"
            f"🆔 `{user_id}`\n"
            f"📝 {issue}\n\n"
            f"{' '.join(admin_mentions)}"
        )
        
        await update.message.reply_text(report_msg, parse_mode="Markdown")
        await update.message.reply_text("✅ Admin တွေဆီပို့ပြီး။")
    except Exception as e:
        logger.error(f"Report error: {e}")

# ==================== BAN/MUTE ====================
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if not await is_group_admin(context, chat_id, user_id):
            await update.message.reply_text("⛔ Admin သာသုံးလို့ရပါတယ်။")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("⚠️ User ကို reply ထောက်ပြီး /ban")
            return
        
        target = update.message.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else "အကြောင်းပြချက်မရှိ"
        
        await db.ban_user(chat_id, target.id, reason)
        await update.message.reply_text(f"✅ {target.first_name} ကို Ban လုပ်ပြီး။")
    except Exception as e:
        logger.error(f"Ban error: {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if not await is_group_admin(context, chat_id, user_id):
            await update.message.reply_text("⛔ Admin သာသုံးလို့ရပါတယ်။")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("⚠️ User ကို reply ထောက်ပြီး /unban")
            return
        
        target = update.message.reply_to_message.from_user
        await db.unban_user(chat_id, target.id)
        await update.message.reply_text(f"✅ {target.first_name} ကို Unban လုပ်ပြီး။")
    except Exception as e:
        logger.error(f"Unban error: {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if not await is_group_admin(context, chat_id, user_id):
            await update.message.reply_text("⛔ Admin သာသုံးလို့ရပါတယ်။")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("⚠️ User ကို reply ထောက်ပြီး /mute [မိနစ်]")
            return
        
        target = update.message.reply_to_message.from_user
        duration = 60
        if context.args:
            try:
                duration = int(context.args[0])
            except:
                pass
        
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "အကြောင်းပြချက်မရှိ"
        
        await db.mute_user(chat_id, target.id, duration, reason)
        await update.message.reply_text(f"✅ {target.first_name} ကို {duration} မိနစ် Mute လုပ်ပြီး။")
    except Exception as e:
        logger.error(f"Mute error: {e}")

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if not await is_group_admin(context, chat_id, user_id):
            await update.message.reply_text("⛔ Admin သာသုံးလို့ရပါတယ်။")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("⚠️ User ကို reply ထောက်ပြီး /unmute")
            return
        
        target = update.message.reply_to_message.from_user
        await db.unmute_user(chat_id, target.id)
        await update.message.reply_text(f"✅ {target.first_name} ကို Unmute လုပ်ပြီး။")
    except Exception as e:
        logger.error(f"Unmute error: {e}")

# ==================== VIDEO COMMANDS ====================
async def set_start_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("⚠️ Video ကို reply ထောက်ပြီး /setstartvideo")
            return
        
        video = update.message.reply_to_message.video
        if not video:
            await update.message.reply_text("⚠️ Video ကိုပဲ reply ထောက်ပေးပါ။")
            return
        
        caption = update.message.reply_to_message.caption or ""
        await db.set_start_video(video.file_id, caption)
        await update.message.reply_text("✅ Start Video သတ်မှတ်ပြီး။")
    except Exception as e:
        logger.error(f"Set start video error: {e}")

async def delete_start_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        await db.delete_start_video()
        await update.message.reply_text("✅ Start Video ဖျက်ပြီး။")
    except Exception as e:
        logger.error(f"Delete start video error: {e}")

async def set_welcome_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not await is_group_admin(context, chat_id, user_id):
            await update.message.reply_text("⛔ Admin သာသုံးလို့ရပါတယ်။")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("⚠️ Video ကို reply ထောက်ပြီး /setwelcomevideo")
            return
        
        video = update.message.reply_to_message.video
        if not video:
            await update.message.reply_text("⚠️ Video ကိုပဲ reply ထောက်ပေးပါ။")
            return
        
        caption = update.message.reply_to_message.caption or ""
        await db.set_welcome_video(video.file_id, caption)
        await update.message.reply_text("✅ Welcome Video သတ်မှတ်ပြီး။")
        await db.add_group_admin(chat_id, user_id)
    except Exception as e:
        logger.error(f"Set welcome video error: {e}")

async def delete_welcome_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not await is_group_admin(context, chat_id, user_id):
            await update.message.reply_text("⛔ Admin သာသုံးလို့ရပါတယ်။")
            return
        
        await db.delete_welcome_video()
        await update.message.reply_text("✅ Welcome Video ဖျက်ပြီး။")
    except Exception as e:
        logger.error(f"Delete welcome video error: {e}")

async def set_leave_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("⚠️ Video ကို reply ထောက်ပြီး /setleavevideo")
            return
        
        video = update.message.reply_to_message.video
        if not video:
            await update.message.reply_text("⚠️ Video ကိုပဲ reply ထောက်ပေးပါ။")
            return
        
        caption = update.message.reply_to_message.caption or ""
        await db.set_leave_video(video.file_id, caption)
        await update.message.reply_text("✅ Leave Video သတ်မှတ်ပြီး။")
    except Exception as e:
        logger.error(f"Set leave video error: {e}")

async def delete_leave_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        await db.delete_leave_video()
        await update.message.reply_text("✅ Leave Video ဖျက်ပြီး။")
    except Exception as e:
        logger.error(f"Delete leave video error: {e}")

# ==================== STICKER ====================
async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        sticker = update.message.sticker
        
        if user_id == Config.OWNER_ID:
            await db.save_sticker(sticker.file_id, sticker.emoji or "")
            count = await db.get_all_stickers()
            await update.message.reply_text(f"✅ Sticker သိမ်းပြီး! 📊 {count} ခုရှိပြီ။")
            return
        
        random_sticker = await db.get_random_sticker()
        if random_sticker:
            await update.message.reply_sticker(random_sticker)
        else:
            await update.message.reply_text("😅 Sticker မရှိသေးဘူး။")
    except Exception as e:
        logger.error(f"Sticker error: {e}")

async def list_stickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        count = await db.get_all_stickers()
        await update.message.reply_text(f"📊 Sticker: {count} ခု")
    except Exception as e:
        logger.error(f"List stickers error: {e}")

async def clear_stickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        await db.clear_all_stickers()
        await update.message.reply_text("🗑️ Sticker အကုန်ဖျက်ပြီး။")
    except Exception as e:
        logger.error(f"Clear stickers error: {e}")

# ==================== PHOTO ====================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        photo = update.message.photo[-1]
        
        if user_id == Config.OWNER_ID:
            caption = update.message.caption or ""
            await db.save_photo(photo.file_id, caption)
            count = await db.get_all_photos()
            await update.message.reply_text(f"✅ Photo သိမ်းပြီး! 📊 {count} ခုရှိပြီ။")
            return
        
        random_photo = await db.get_random_photo()
        if random_photo:
            await update.message.reply_photo(random_photo)
        else:
            await update.message.reply_text("📸 Photo မရှိသေးဘူး။")
    except Exception as e:
        logger.error(f"Photo error: {e}")

async def list_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        count = await db.get_all_photos()
        await update.message.reply_text(f"📊 Photo: {count} ခု")
    except Exception as e:
        logger.error(f"List photos error: {e}")

async def clear_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        await db.clear_all_photos()
        await update.message.reply_text("🗑️ Photo အကုန်ဖျက်ပြီး။")
    except Exception as e:
        logger.error(f"Clear photos error: {e}")

# ==================== EMOJI ====================
async def handle_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        emoji = update.message.text
        
        await db.save_emoji(user_id, emoji)
        
        random_emoji = await db.get_random_emoji()
        if random_emoji:
            await update.message.reply_text(random_emoji)
        else:
            await update.message.reply_text("😊")
    except Exception as e:
        logger.error(f"Emoji error: {e}")

# ==================== LINK DETECTION ====================
async def handle_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        message = update.message
        
        if not message.text:
            return
        
        links = extract_links(message.text)
        if not links:
            return
        
        is_admin = await is_group_admin(context, chat_id, user_id)
        if is_admin:
            return
        
        settings = await db.get_link_settings(chat_id)
        allowed_domains = settings.get('allowed_domains', [])
        blocked_links = [l for l in links if not is_allowed_link(l, allowed_domains)]
        
        if not blocked_links:
            return
        
        if settings.get('delete_links', True):
            await message.delete()
            await message.reply_text(
                f"🚫 **လင့်ပို့ခွင့်မရှိပါ**\n\n"
                f"👤 {message.from_user.first_name}"
            )
    except Exception as e:
        logger.error(f"Link detection error: {e}")

# ==================== GROUP MEMBERS ====================
async def handle_group_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        
        # Update admin list
        try:
            chat_admins = await context.bot.get_chat_administrators(chat_id)
            admin_ids = [admin.user.id for admin in chat_admins]
            await db.save_group_admins(chat_id, admin_ids)
        except:
            pass
        
        # New member
        if update.message.new_chat_members:
            for member in update.message.new_chat_members:
                if member.is_bot:
                    continue
                
                user_info = get_user_info(member)
                welcome_msg = Config.WELCOME_TEXT.format(**user_info)
                
                if db.welcome_video:
                    try:
                        video = db.welcome_video
                        caption = video.get('caption', '') + "\n\n" + welcome_msg
                        await update.message.reply_video(
                            video=video['file_id'],
                            caption=caption,
                            reply_markup=get_welcome_keyboard(context.bot.username)
                        )
                        return
                    except:
                        pass
                
                await update.message.reply_text(
                    welcome_msg,
                    reply_markup=get_welcome_keyboard(context.bot.username)
                )
        
        # Left member
        if update.message.left_chat_member:
            for member in update.message.left_chat_member:
                if member.is_bot:
                    continue
                
                user_info = get_user_info(member)
                leave_msg = Config.LEAVE_TEXT.format(**user_info)
                
                emojis = await db.get_reaction_emojis()
                random_emoji = random.choice(emojis) if emojis else "🧸"
                
                if db.leave_video:
                    try:
                        video = db.leave_video
                        caption = video.get('caption', '') + "\n\n" + leave_msg
                        await update.message.reply_video(
                            video=video['file_id'],
                            caption=caption,
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton(
                                    f"{random_emoji} Profile",
                                    url=f"tg://user?id={member.id}"
                                )
                            ]])
                        )
                        return
                    except:
                        pass
                
                await update.message.reply_text(
                    leave_msg,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            f"{random_emoji} Profile",
                            url=f"tg://user?id={member.id}"
                        )
                    ]])
                )
    except Exception as e:
        logger.error(f"Group members error: {e}")

# ==================== MESSAGE HANDLER ====================
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Check ban/mute
        if await db.is_user_banned(chat_id, user_id):
            await update.message.reply_text("⛔ သင်သည် Ban ခံထားရပါသည်။")
            return
        
        if await db.is_user_muted(chat_id, user_id):
            await update.message.reply_text("🔇 သင်သည် Mute ခံထားရပါသည်။")
            return
        
        # Typing
        await send_typing_action(update, context)
        
        # Rate limit
        if not rate_limiter.is_allowed(user_id):
            await update.message.reply_text("⏳ ခေတ္တခဏစောင့်ပါ။")
            return
        
        # Sticker
        if update.message.sticker:
            await handle_sticker(update, context)
            return
        
        # Photo
        if update.message.photo:
            await handle_photo(update, context)
            return
        
        # Video
        if update.message.video:
            video = update.message.video
            # Owner ဆိုရင် သိမ်း
            if user_id == Config.OWNER_ID:
                caption = update.message.caption or ""
                await db.save_video(video.file_id, caption)
                count = await db.get_all_videos()
                await update.message.reply_text(f"✅ Video သိမ်းပြီး! 📊 {count} ခုရှိပြီ။")
                return
            
            random_video = await db.get_random_video()
            if random_video:
                await update.message.reply_video(random_video)
            else:
                await update.message.reply_text("🎬 Video မရှိသေးဘူး။")
            return
        
        # Document
        if update.message.document:
            await update.message.reply_text("📄 Document")
            return
        
        # Audio/Voice
        if update.message.audio or update.message.voice:
            audio = update.message.audio or update.message.voice
            if user_id == Config.OWNER_ID:
                caption = update.message.caption or ""
                await db.save_audio(audio.file_id, caption)
                count = await db.get_all_audios()
                await update.message.reply_text(f"✅ Audio သိမ်းပြီး! 📊 {count} ခုရှိပြီ။")
                return
            
            random_audio = await db.get_random_audio()
            if random_audio:
                if update.message.audio:
                    await update.message.reply_audio(random_audio)
                else:
                    await update.message.reply_voice(random_audio)
            else:
                await update.message.reply_text("🎵 Audio မရှိသေးဘူး။")
            return
        
        # Text
        if update.message.text:
            # Check links
            await handle_links(update, context)
            
            user_message = update.message.text
            
            # Emoji
            if is_emoji_only(user_message):
                await handle_emoji(update, context)
                return
            
            # Teach System
            qa_answer = await db.get_answer(user_message)
            if qa_answer:
                await update.message.reply_text(qa_answer)
                return
            
            # Save message
            await db.save_message(user_id, user_message)
            
            # Random reply
            msg = await db.get_random_message()
            if msg:
                await update.message.reply_text(msg['message'] + " 😊")
            else:
                await update.message.reply_text(
                    "😅 စာမရှိသေးဘူး။\n\n"
                    "💡 Owner ကို ဆက်သွယ်ပါ။"
                )
    except Exception as e:
        logger.error(f"Message handler error: {e}")

# ==================== STATS ====================
async def today_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        stats = await db.get_today_stats()
        await update.message.reply_text(
            f"📊 **ဒီနေ့စာရင်း**\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"📝 စာ: {stats['total']} ကြောင်း"
        )
    except Exception as e:
        logger.error(f"Today stats error: {e}")

async def week_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        stats = await db.get_week_stats()
        await update.message.reply_text(
            f"📊 **ဒီတစ်ပတ်စာရင်း**\n"
            f"📆 {datetime.now().strftime('%Y-%m-%d')} ထိ\n\n"
            f"📝 စာ: {stats['total']} ကြောင်း"
        )
    except Exception as e:
        logger.error(f"Week stats error: {e}")

async def month_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        stats = await db.get_month_stats()
        await update.message.reply_text(
            f"📊 **ဒီတစ်လစာရင်း**\n"
            f"📆 {datetime.now().strftime('%Y-%m-%d')} ထိ\n\n"
            f"📝 စာ: {stats['total']} ကြောင်း\n"
            f"📊 ပျမ်းမျှ: {stats['total']/30:.0f} ကြောင်း/နေ့"
        )
    except Exception as e:
        logger.error(f"Month stats error: {e}")

async def all_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        stats = await db.get_all_stats()
        total_mb = (stats['total'] * 500) / 1024 / 1024
        
        await update.message.reply_text(
            f"📊 **စုစုပေါင်းစာရင်း**\n\n"
            f"📝 စာ: {stats['total']:,} ကြောင်း\n"
            f"✅ သုံးပြီး: {stats['used']:,} ကြောင်း\n"
            f"⏳ မသုံးရသေး: {stats['unused']:,} ကြောင်း\n"
            f"💾 နေရာ: {total_mb:.2f} MB"
        )
    except Exception as e:
        logger.error(f"All stats error: {e}")

async def storage_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        total = await db.messages.count_documents({})
        estimated_mb = (total * 500) / 1024 / 1024
        
        if estimated_mb < 300:
            status = "🟢 အန္တရာယ်ကင်း"
        elif estimated_mb < 400:
            status = "🟡 စောင့်ကြည့်ရမယ်"
        elif estimated_mb < 480:
            status = "🟠 နေရာကျပ်လာပြီ"
        else:
            status = "🔴 နေရာပြည့်တော့မယ်!"
        
        await update.message.reply_text(
            f"📊 **Storage Status**\n\n"
            f"📝 စာ: {total:,} ကြောင်း\n"
            f"💾 နေရာ: {estimated_mb:.2f} MB / 512 MB\n"
            f"📊 အခြေ: {status}"
        )
    except Exception as e:
        logger.error(f"Storage status error: {e}")

async def force_clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            await update.message.reply_text("⛔ Owner သာသုံးလို့ရပါတယ်။")
            return
        
        result = await db.messages.delete_many({
            "usage_count": {"$lt": 2},
            "timestamp": {"$lt": datetime.now() - timedelta(days=7)}
        })
        
        await update.message.reply_text(f"🧹 ဖျက်လိုက်တာ: {result.deleted_count} ကြောင်း")
    except Exception as e:
        logger.error(f"Force clean error: {e}")

# ==================== AUTO CLEAN LOOP ====================
async def auto_clean_loop():
    while True:
        try:
            await db.check_and_clean_if_full()
        except Exception as e:
            logger.error(f"Auto clean error: {e}")
        await asyncio.sleep(600)

# ==================== MAIN ====================
async def main():
    try:
        # Validate config
        Config.validate()
        
        # Connect to database
        await db.connect()
        
        # Create application
        app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        db.bot = app.bot
        
        # ===== Commands =====
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("teach", teach_command))
        app.add_handler(CommandHandler("report", report_command))
        
        app.add_handler(CommandHandler("ban", ban_command))
        app.add_handler(CommandHandler("unban", unban_command))
        app.add_handler(CommandHandler("mute", mute_command))
        app.add_handler(CommandHandler("unmute", unmute_command))
        
        app.add_handler(CommandHandler("setstartvideo", set_start_video))
        app.add_handler(CommandHandler("deletestartvideo", delete_start_video))
        app.add_handler(CommandHandler("setwelcomevideo", set_welcome_video))
        app.add_handler(CommandHandler("deletewelcomevideo", delete_welcome_video))
        app.add_handler(CommandHandler("setleavevideo", set_leave_video))
        app.add_handler(CommandHandler("deleteleavevideo", delete_leave_video))
        
        app.add_handler(CommandHandler("liststickers", list_stickers))
        app.add_handler(CommandHandler("clearstickers", clear_stickers))
        app.add_handler(CommandHandler("listphotos", list_photos))
        app.add_handler(CommandHandler("clearphotos", clear_photos))
        
        app.add_handler(CommandHandler("todaystats", today_stats))
        app.add_handler(CommandHandler("weekstats", week_stats))
        app.add_handler(CommandHandler("monthstats", month_stats))
        app.add_handler(CommandHandler("allstats", all_stats))
        app.add_handler(CommandHandler("storage", storage_status))
        app.add_handler(CommandHandler("forceclean", force_clean))
        
        # ===== Callbacks =====
        app.add_handler(CallbackQueryHandler(help_callback, pattern="^help_"))
        app.add_handler(CallbackQueryHandler(help_back, pattern="^help_back$"))
        
        # ===== Handlers =====
        app.add_handler(MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
            handle_group_members
        ))
        app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_messages))
        
        # ===== Background Tasks =====
        asyncio.create_task(auto_clean_loop())
        
        # ===== Start =====
        logger.info("🤖 Bot started!")
        
        # Webhook for Render
        await app.run_polling()
        
    except Exception as e:
        logger.error(f"Main error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
