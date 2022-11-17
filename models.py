from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Rooms(Base):
    __tablename__ = 'rooms'
    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)


class Users(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    room_id = Column(Integer, ForeignKey("rooms.id"))
    wish_string = Column(String)


class Pairs(Base):
    __tablename__ = 'pairs'
    giver_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    taker_id = Column(Integer, ForeignKey("users.id"))
