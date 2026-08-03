import logging
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from config import Config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        self.bot = None
        
        self.start_video = None
        self.welcome_video = None
        self.leave_video = None
        
        self.MAX_STORAGE_MB = 480
        self.TARGET_STORAGE_MB = 250
        self.AVG_MSG_SIZE_BYTES = 500
    
    async def connect(self):
        try:
            self.client = AsyncIOMotorClient(
                Config.MONGODB_URI,
                tls=True,
                serverSelectionTimeoutMS=5000
            )
            await self.client.admin.command('ping')
            self.db = self.client['chat_bot_db']
            
            # Collections
            self.messages = self.db.messages
            self.emoji_history = self.db.emoji_history
            self.stickers = self.db.stickers
            self.photos = self.db.photos
            self.videos = self.db.videos
            self.documents = self.db.documents
            self.audios = self.db.audios
            self.welcome_settings = self.db.welcome_settings
            self.start_settings = self.db.start_settings
            self.leave_settings = self.db.leave_settings
            self.group_admins = self.db.group_admins
            self.link_settings = self.db.link_settings
            self.reaction_emojis = self.db.reaction_emojis
            self.reports = self.db.reports
            self.qa_system = self.db.qa_system
            
            # Indexes
            await self.messages.create_index("timestamp")
            await self.messages.create_index("user_id")
            await self.messages.create_index("usage_count")
            
            await self.load_settings()
            logger.info("✅ MongoDB Connected")
            
        except ConnectionFailure:
            logger.error("❌ MongoDB Connection Failed")
            raise
    
    async def load_settings(self):
        doc = await self.start_settings.find_one({"_id": "start_video"})
        self.start_video = doc.get('data') if doc else None
        
        doc = await self.welcome_settings.find_one({"_id": "welcome_video"})
        self.welcome_video = doc.get('data') if doc else None
        
        doc = await self.leave_settings.find_one({"_id": "leave_video"})
        self.leave_video = doc.get('data') if doc else None
    
    # ===== MESSAGES =====
    async def save_message(self, user_id, message, msg_type="text"):
        if not message:
            return
        clean_msg = message.strip()
        if len(clean_msg) > 1000:
            clean_msg = clean_msg[:1000]
        await self.messages.insert_one({
            "user_id": user_id,
            "message": clean_msg,
            "message_type": msg_type,
            "timestamp": datetime.now(),
            "is_active": True,
            "usage_count": 0
        })
    
    async def get_random_message(self):
        pipeline = [{"$match": {"is_active": True}}, {"$sample": {"size": 1}}]
        result = await self.messages.aggregate(pipeline).to_list(length=1)
        return result[0] if result else None
    
    # ===== EMOJI =====
    async def save_emoji(self, user_id, emoji):
        await self.emoji_history.insert_one({
            "user_id": user_id,
            "emoji": emoji,
            "timestamp": datetime.now()
        })
    
    async def get_random_emoji(self):
        emojis = await self.emoji_history.distinct("emoji")
        import random
        return random.choice(emojis) if emojis else None
    
    # ===== STICKER =====
    async def save_sticker(self, file_id, emoji=""):
        await self.stickers.insert_one({
            "file_id": file_id,
            "emoji": emoji,
            "timestamp": datetime.now()
        })
    
    async def get_random_sticker(self):
        stickers = await self.stickers.aggregate([{"$sample": {"size": 1}}]).to_list(length=1)
        return stickers[0]['file_id'] if stickers else None
    
    async def get_all_stickers(self):
        return await self.stickers.count_documents({})
    
    async def delete_sticker(self, file_id):
        await self.stickers.delete_one({"file_id": file_id})
    
    async def clear_all_stickers(self):
        await self.stickers.delete_many({})
    
    # ===== PHOTO =====
    async def save_photo(self, file_id, caption=""):
        await self.photos.insert_one({
            "file_id": file_id,
            "caption": caption,
            "timestamp": datetime.now()
        })
    
    async def get_random_photo(self):
        photos = await self.photos.aggregate([{"$sample": {"size": 1}}]).to_list(length=1)
        return photos[0]['file_id'] if photos else None
    
    async def get_all_photos(self):
        return await self.photos.count_documents({})
    
    async def clear_all_photos(self):
        await self.photos.delete_many({})
    
    # ===== VIDEO =====
    async def save_video(self, file_id, caption=""):
        await self.videos.insert_one({
            "file_id": file_id,
            "caption": caption,
            "timestamp": datetime.now()
        })
    
    async def get_random_video(self):
        videos = await self.videos.aggregate([{"$sample": {"size": 1}}]).to_list(length=1)
        return videos[0]['file_id'] if videos else None
    
    async def get_all_videos(self):
        return await self.videos.count_documents({})
    
    async def clear_all_videos(self):
        await self.videos.delete_many({})
    
    # ===== AUDIO =====
    async def save_audio(self, file_id, caption=""):
        await self.audios.insert_one({
            "file_id": file_id,
            "caption": caption,
            "timestamp": datetime.now()
        })
    
    async def get_random_audio(self):
        audios = await self.audios.aggregate([{"$sample": {"size": 1}}]).to_list(length=1)
        return audios[0]['file_id'] if audios else None
    
    async def get_all_audios(self):
        return await self.audios.count_documents({})
    
    async def clear_all_audios(self):
        await self.audios.delete_many({})
    
    # ===== VIDEO SETTINGS =====
    async def set_start_video(self, file_id, caption=""):
        self.start_video = {"file_id": file_id, "caption": caption}
        await self.start_settings.update_one(
            {"_id": "start_video"},
            {"$set": {"data": self.start_video}},
            upsert=True
        )
    
    async def delete_start_video(self):
        self.start_video = None
        await self.start_settings.delete_one({"_id": "start_video"})
    
    async def set_welcome_video(self, file_id, caption=""):
        self.welcome_video = {"file_id": file_id, "caption": caption}
        await self.welcome_settings.update_one(
            {"_id": "welcome_video"},
            {"$set": {"data": self.welcome_video}},
            upsert=True
        )
    
    async def delete_welcome_video(self):
        self.welcome_video = None
        await self.welcome_settings.delete_one({"_id": "welcome_video"})
    
    async def set_leave_video(self, file_id, caption=""):
        self.leave_video = {"file_id": file_id, "caption": caption}
        await self.leave_settings.update_one(
            {"_id": "leave_video"},
            {"$set": {"data": self.leave_video}},
            upsert=True
        )
    
    async def delete_leave_video(self):
        self.leave_video = None
        await self.leave_settings.delete_one({"_id": "leave_video"})
    
    # ===== GROUP ADMINS =====
    async def get_group_admins(self, chat_id):
        doc = await self.group_admins.find_one({"chat_id": chat_id})
        return doc.get('admins', []) if doc else []
    
    async def save_group_admins(self, chat_id, admin_ids):
        await self.group_admins.update_one(
            {"chat_id": chat_id},
            {"$set": {"admins": admin_ids}},
            upsert=True
        )
    
    async def add_group_admin(self, chat_id, admin_id):
        await self.group_admins.update_one(
            {"chat_id": chat_id},
            {"$addToSet": {"admins": admin_id}},
            upsert=True
        )
    
    async def remove_group_admin(self, chat_id, admin_id):
        await self.group_admins.update_one(
            {"chat_id": chat_id},
            {"$pull": {"admins": admin_id}}
        )
    
    # ===== LINK SETTINGS =====
    async def get_link_settings(self, chat_id):
        doc = await self.link_settings.find_one({"chat_id": chat_id})
        if doc:
            return doc.get('settings', {})
        return {"delete_links": True, "warn_users": True, "allowed_domains": []}
    
    async def save_link_settings(self, chat_id, settings):
        await self.link_settings.update_one(
            {"chat_id": chat_id},
            {"$set": {"settings": settings}},
            upsert=True
        )
    
    async def add_allowed_domain(self, chat_id, domain):
        settings = await self.get_link_settings(chat_id)
        if domain not in settings.get('allowed_domains', []):
            settings['allowed_domains'].append(domain)
            await self.save_link_settings(chat_id, settings)
    
    async def remove_allowed_domain(self, chat_id, domain):
        settings = await self.get_link_settings(chat_id)
        if domain in settings.get('allowed_domains', []):
            settings['allowed_domains'].remove(domain)
            await self.save_link_settings(chat_id, settings)
    
    # ===== REACTION EMOJIS =====
    async def get_reaction_emojis(self):
        doc = await self.reaction_emojis.find_one({"_id": "reaction_emojis"})
        if doc:
            return doc.get('emojis', ['🧸', '😪', '🌹', '🥵', '😂', '😅', '🤣', '😎', '😭', '💩', '☠', '🐹', '🦁', '🍨', '🍧', '🎁', '🎀'])
        return ['🧸', '😪', '🌹', '🥵', '😂', '😅', '🤣', '😎', '😭', '💩', '☠', '🐹', '🦁', '🍨', '🍧', '🎁', '🎀']
    
    async def add_reaction_emoji(self, emoji):
        await self.reaction_emojis.update_one(
            {"_id": "reaction_emojis"},
            {"$addToSet": {"emojis": emoji}},
            upsert=True
        )
    
    async def remove_reaction_emoji(self, emoji):
        await self.reaction_emojis.update_one(
            {"_id": "reaction_emojis"},
            {"$pull": {"emojis": emoji}}
        )
    
    # ===== TEACH SYSTEM =====
    async def save_qa(self, question, answer, user_id):
        await self.qa_system.update_one(
            {"question": question.lower().strip()},
            {
                "$set": {
                    "question": question.strip(),
                    "answer": answer.strip(),
                    "user_id": user_id,
                    "timestamp": datetime.now(),
                    "usage_count": 0
                }
            },
            upsert=True
        )
    
    async def get_answer(self, question):
        result = await self.qa_system.find_one({
            "question": {"$regex": f"^{question.strip()}$", "$options": "i"}
        })
        if result:
            await self.qa_system.update_one(
                {"_id": result['_id']},
                {"$inc": {"usage_count": 1}}
            )
            return result['answer']
        
        results = await self.qa_system.find({}).to_list(length=100)
        for r in results:
            if r['question'].lower() in question.lower() or question.lower() in r['question'].lower():
                return r['answer']
        return None
    
    async def get_all_qa(self):
        return await self.qa_system.find({}).to_list(length=1000)
    
    async def delete_qa(self, question):
        result = await self.qa_system.delete_one({
            "question": {"$regex": f"^{question.strip()}$", "$options": "i"}
        })
        return result.deleted_count > 0
    
    async def clear_all_qa(self):
        await self.qa_system.delete_many({})
    
    async def get_qa_count(self):
        return await self.qa_system.count_documents({})
    
    # ===== BAN/MUTE =====
    async def ban_user(self, chat_id, user_id, reason=""):
        await self.db.banned_users.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$set": {"reason": reason, "timestamp": datetime.now(), "is_banned": True}},
            upsert=True
        )
    
    async def unban_user(self, chat_id, user_id):
        await self.db.banned_users.delete_one({"chat_id": chat_id, "user_id": user_id})
    
    async def is_user_banned(self, chat_id, user_id):
        doc = await self.db.banned_users.find_one({"chat_id": chat_id, "user_id": user_id})
        return doc is not None
    
    async def mute_user(self, chat_id, user_id, duration=60, reason=""):
        until = datetime.now() + timedelta(minutes=duration)
        await self.db.muted_users.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$set": {"until": until, "reason": reason, "timestamp": datetime.now()}},
            upsert=True
        )
    
    async def unmute_user(self, chat_id, user_id):
        await self.db.muted_users.delete_one({"chat_id": chat_id, "user_id": user_id})
    
    async def is_user_muted(self, chat_id, user_id):
        doc = await self.db.muted_users.find_one({"chat_id": chat_id, "user_id": user_id})
        if doc:
            if doc['until'] < datetime.now():
                await self.db.muted_users.delete_one({"_id": doc['_id']})
                return False
            return True
        return False
    
    # ===== STATS =====
    async def get_today_stats(self):
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        count = await self.messages.count_documents({"timestamp": {"$gte": today, "$lt": tomorrow}})
        user_stats = await self.messages.aggregate([
            {"$match": {"timestamp": {"$gte": today, "$lt": tomorrow}}},
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]).to_list(length=10)
        return {"total": count, "users": user_stats}
    
    async def get_week_stats(self):
        week_ago = datetime.now() - timedelta(days=7)
        count = await self.messages.count_documents({"timestamp": {"$gte": week_ago}})
        daily_stats = await self.messages.aggregate([
            {"$match": {"timestamp": {"$gte": week_ago}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]).to_list(length=7)
        return {"total": count, "daily": daily_stats}
    
    async def get_month_stats(self):
        month_ago = datetime.now() - timedelta(days=30)
        count = await self.messages.count_documents({"timestamp": {"$gte": month_ago}})
        return {"total": count, "days": 30}
    
    async def get_all_stats(self):
        total = await self.messages.count_documents({})
        used = await self.messages.count_documents({"usage_count": {"$gt": 0}})
        unused = await self.messages.count_documents({"usage_count": 0})
        return {"total": total, "used": used, "unused": unused}
    
    # ===== AUTO CLEAN =====
    async def check_and_clean_if_full(self):
        total = await self.messages.count_documents({})
        estimated_mb = (total * self.AVG_MSG_SIZE_BYTES) / 1024 / 1024
        
        if estimated_mb >= self.MAX_STORAGE_MB:
            target_total = (self.TARGET_STORAGE_MB * 1024 * 1024) / self.AVG_MSG_SIZE_BYTES
            to_delete = int(total - target_total)
            
            if to_delete > 0:
                oldest = await self.messages.find({
                    "usage_count": {"$lt": 3}
                }).sort("timestamp", 1).limit(to_delete).to_list(length=to_delete)
                
                if oldest:
                    ids = [doc['_id'] for doc in oldest]
                    result = await self.messages.delete_many({"_id": {"$in": ids}})
                    logger.info(f"🗑️ နေရာလွတ်ရှင်းလင်း: {result.deleted_count} ကြောင်းဖျက်ပြီး")
                    return True
        return False
