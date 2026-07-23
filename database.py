import os
from sqlalchemy import create_engine, Column, Integer, String, Text, BigInteger, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True)
    name = Column(String(100))
    age = Column(Integer)
    bio = Column(Text)
    gender = Column(String(10))
    looking_for = Column(String(10))
    photo_file_id = Column(String(200))
    is_registered = Column(Boolean, default=False)

class Like(Base):
    __tablename__ = 'likes'
    id = Column(Integer, primary_key=True)
    from_user = Column(BigInteger)
    to_user = Column(BigInteger)
    is_matched = Column(Boolean, default=False)

# Render မှာ PostgreSQL သုံးမယ်၊ မရရင် SQLite ကို fallback လုပ်မယ်
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
else:
    engine = create_engine('sqlite:///dating.db')

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
