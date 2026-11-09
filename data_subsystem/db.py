"""
db.py - Quản lý kết nối Cơ sở dữ liệu và Session SQLAlchemy
Hỗ trợ SQLite cục bộ (dev/test) và PostgreSQL (production).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from laptopmatch_dss.config.settings import DATABASE_URL

# Thiết lập connect_args riêng cho SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency cung cấp session DB cho FastAPI và các dịch vụ."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Khởi tạo bảng trong cơ sở dữ liệu nếu chưa tồn tại."""
    Base.metadata.create_all(bind=engine)
