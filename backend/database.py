import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# SQLite DB Path
DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "retail_copilot.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # Admin, Store Manager, Category Manager, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

class Product(Base):
    __tablename__ = "products"
    sku = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    unit = Column(String, default="unit")
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    
    supplier = relationship("Supplier", back_populates="products")

class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    product_sku = Column(String, ForeignKey("products.sku"), nullable=False)
    location_type = Column(String, nullable=False)  # Store, Warehouse
    location_name = Column(String, nullable=False)  # e.g. Warehouse A, Store 210, Store 105
    current_stock = Column(Integer, nullable=False)
    reorder_threshold = Column(Integer, nullable=False)
    status = Column(String, nullable=False)  # OK, LOW STOCK, OUT OF STOCK

class SalesTransaction(Base):
    __tablename__ = "sales_transactions"
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, index=True, nullable=False)
    product_sku = Column(String, ForeignKey("products.sku"), nullable=False)
    quantity = Column(Integer, nullable=False)
    store_name = Column(String, nullable=False)  # e.g. Store 210, Store 105
    price_per_unit = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_returned = Column(Boolean, default=False)
    return_reason = Column(String, nullable=True)

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    po_number = Column(String, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    product_sku = Column(String, ForeignKey("products.sku"), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String, nullable=False)  # Pending, Shipped, Delivered, Delayed
    order_date = Column(DateTime, default=datetime.utcnow)
    expected_delivery = Column(DateTime)
    notes = Column(Text, nullable=True)
    
    supplier = relationship("Supplier")

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    contact_person = Column(String)
    email = Column(String)
    phone = Column(String)
    sla_lead_time_days = Column(Integer, default=7)
    performance_score = Column(Float, default=100.0)  # On-time delivery % rating
    
    products = relationship("Product", back_populates="supplier")

class CustomerFeedback(Base):
    __tablename__ = "customer_feedback"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String)
    product_sku = Column(String, ForeignKey("products.sku"), nullable=False)
    rating = Column(Integer)  # 1 to 5 stars
    feedback_text = Column(Text)
    sentiment = Column(String)  # Positive, Neutral, Negative
    timestamp = Column(DateTime, default=datetime.utcnow)

class Promotion(Base):
    __tablename__ = "promotions"
    id = Column(Integer, primary_key=True, index=True)
    campaign_name = Column(String, nullable=False)
    discount_rate = Column(Float, nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    policy_version = Column(String)  # e.g. "V3", "V5"
    rules_text = Column(Text)

class Shipment(Base):
    __tablename__ = "shipments"
    id = Column(Integer, primary_key=True, index=True)
    tracking_number = Column(String, unique=True, index=True, nullable=False)
    po_number = Column(String, ForeignKey("purchase_orders.po_number"), nullable=False)
    carrier = Column(String, nullable=False)  # SwiftCargo, FedEx, etc.
    status = Column(String, nullable=False)  # In Transit, Delivered, Delayed, Cancelled
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    estimated_delivery = Column(DateTime)
    actual_delivery = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    username = Column(String, nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    citations = Column(Text, nullable=True)  # JSON-encoded array
    trace = Column(Text, nullable=True)  # JSON-encoded trace
    timestamp = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    user_role = Column(String, nullable=False)
    query = Column(Text, nullable=False)
    intent = Column(String)  # RAG Search, SQL Analytics, Report Generator
    execution_sql = Column(Text, nullable=True)
    latency_ms = Column(Integer)
    status = Column(String)  # SUCCESS, ERROR
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
