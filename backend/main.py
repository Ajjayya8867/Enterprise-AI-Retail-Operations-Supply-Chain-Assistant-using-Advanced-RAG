import os
import shutil
import csv
import json
import datetime
import bcrypt
import jwt
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

# Import database and engines
from database import init_db, get_db, User, ChatMessage, AuditLog, Product, Inventory, Supplier, PurchaseOrder, Shipment
from rag_engine import AdvancedRAGEngine
from agent_engine import AgenticRetailCopilot

app = FastAPI(title="Enterprise Retail Operations RAG & Analytics API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Initialize engines
rag_engine = AdvancedRAGEngine(data_dir=DATA_DIR)
agent_copilot = AgenticRetailCopilot(data_dir=DATA_DIR, rag_engine=rag_engine)

# JWT Setup
SECRET_KEY = "SUPER_SECRET_RETAIL_KEY"
ALGORITHM = "HS256"

# Create Database tables on startup
@app.on_event("startup")
def startup_event():
    init_db()

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str

class ChatRequest(BaseModel):
    message: str
    session_id: str
    filters: Optional[dict] = None
    api_key: Optional[str] = None

class ReportDownloadRequest(BaseModel):
    content: str
    filename: str

# Helper functions
def get_user_from_token(token: str = Header(None)) -> Optional[dict]:
    if not token or not token.startswith("Bearer "):
        return None
    try:
        jwt_token = token.split(" ")[1]
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None

def verify_role(required_roles: List[str], current_user: dict):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication credentials missing.")
    if current_user.get("role") not in required_roles and current_user.get("role") != "Administrator":
        raise HTTPException(status_code=403, detail="Unauthorized role access.")

# Authenticated user fetcher for dependency injection
def get_current_user(token: str = Header(None)) -> dict:
    user = get_user_from_token(token)
    if not user:
        # For seamless demo testing we can return a default user if headers aren't ready yet,
        # but in production we enforce. Let's return Guest Manager if unauthenticated.
        return {"username": "guest_manager", "role": "Store Manager"}
    return user

# AUTH ENDPOINTS
@app.post("/api/auth/register")
def register_user(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check if exists
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
        
    hashed = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    new_user = User(username=request.username, password_hash=hashed, role=request.role)
    db.add(new_user)
    db.commit()
    return {"status": "success", "message": "User registered successfully"}

@app.post("/api/auth/login")
def login_user(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password")
        
    try:
        is_valid = bcrypt.checkpw(request.password.encode('utf-8'), user.password_hash.encode('utf-8'))
    except Exception:
        is_valid = False
        
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid username or password")
        
    # Generate JWT token
    expire = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    payload = {"sub": user.username, "role": user.role, "exp": expire}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    return {
        "status": "success",
        "token": token,
        "username": user.username,
        "role": user.role
    }

@app.get("/api/auth/me")
def get_me(user: dict = Depends(get_current_user)):
    return user

# DOCUMENT ENDPOINTS
@app.get("/api/documents")
def get_documents():
    """Returns a list of all active files and details."""
    if not os.path.exists(DATA_DIR):
        return []
        
    docs = []
    for filename in os.listdir(DATA_DIR):
        if filename.startswith('.') or not os.path.isfile(os.path.join(DATA_DIR, filename)):
            continue
            
        file_path = os.path.join(DATA_DIR, filename)
        file_size = os.path.getsize(file_path)
        
        # Calculate chunks for this file
        chunks_count = sum(1 for c in rag_engine.chunks if c["metadata"]["source"] == filename)
        
        docs.append({
            "name": filename,
            "size": f"{file_size / 1024:.2f} KB",
            "chunks": chunks_count,
            "path": file_path
        })
    return docs

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...), 
    user: dict = Depends(get_current_user)
):
    """Handles file uploads, saves them, and triggers re-indexing."""
    # RBAC: Only admin, category manager, procurement manager can upload
    verify_role(["Administrator", "Category Manager", "Procurement Manager"], user)
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
        
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ['.txt', '.pdf', '.csv', '.docx', '.xlsx']:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload .txt, .pdf, .csv, .docx, or .xlsx")
        
    file_path = os.path.join(DATA_DIR, file.filename)
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        rag_engine.reindex_all()
        return {"status": "success", "message": f"Successfully indexed {file.filename}"}
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"File saving failed: {e}")

@app.post("/api/documents/sample/{filename}")
def load_sample_document(filename: str, user: dict = Depends(get_current_user)):
    """Loads a preset sample document (like a PDF SLA or warehouse SOP) directly into data dir."""
    verify_role(["Administrator", "Category Manager", "Procurement Manager"], user)
    sample_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_documents")
    src = os.path.join(sample_dir, filename)
    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail=f"Sample file {filename} not found.")
        
    dest = os.path.join(DATA_DIR, filename)
    try:
        shutil.copy(src, dest)
        rag_engine.reindex_all()
        return {"status": "success", "message": f"Successfully loaded and indexed sample: {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to copy sample file: {e}")

@app.delete("/api/documents/{filename}")
def delete_document(filename: str, user: dict = Depends(get_current_user)):
    """Deletes a document and triggers re-indexing."""
    # RBAC: Only Admin can delete
    verify_role(["Administrator"], user)
    
    file_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        os.remove(file_path)
        rag_engine.reindex_all()
        return {"status": "success", "message": f"Deleted {filename} and re-indexed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File deletion failed: {e}")

# CHAT ENDPOINT
@app.post("/api/chat")
def chat_query(
    request: ChatRequest, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Chat endpoint supporting conversation memory routing and system logging."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Empty query message")
        
    if request.api_key:
        rag_engine.set_api_key(request.api_key)
        
    start_time = datetime.datetime.utcnow()
    username = user.get("username", "guest")
    role = user.get("role", "Store Manager")
    
    # 1. Retrieve Conversation History for Memory
    history_rows = db.query(ChatMessage).filter(
        ChatMessage.session_id == request.session_id
    ).order_by(ChatMessage.timestamp.asc()).all()
    
    history_messages = [{"role": msg.role, "content": msg.content} for msg in history_rows]
    
    # Save User message to database
    user_msg = ChatMessage(
        session_id=request.session_id,
        username=username,
        role="user",
        content=request.message
    )
    db.add(user_msg)
    db.commit()
    
    intent = "RAG Search"
    sql_executed = None
    error_msg = None
    
    try:
        # 2. Process query via agent copilot
        answer, citations, trace, intent = agent_copilot.process_query(
            request.message,
            history_messages=history_messages,
            filters=request.filters
        )
        
        if intent == "SQL" and "sql" in trace:
            # Extract executed SQL from trace if available
            sql_executed = trace.get("sparse_results", [{}])[0].get("chunk_text", "").replace("SQL Query Executed: ", "")
            
        # Save Assistant response to database
        assistant_msg = ChatMessage(
            session_id=request.session_id,
            username=username,
            role="assistant",
            content=answer,
            citations=json.dumps(citations),
            trace=json.dumps(trace)
        )
        db.add(assistant_msg)
        db.commit()
        
        status = "SUCCESS"
        
    except Exception as e:
        status = "ERROR"
        error_msg = str(e)
        answer = f"❌ An error occurred in the agent engine: {e}"
        citations = []
        trace = {}
        
    # Calculate latency
    latency = int((datetime.datetime.utcnow() - start_time).total_seconds() * 1000)
    
    # 3. Log to Audit Table
    audit_log = AuditLog(
        username=username,
        user_role=role,
        query=request.message,
        intent=intent,
        execution_sql=sql_executed,
        latency_ms=latency,
        status=status,
        error_message=error_msg
    )
    db.add(audit_log)
    db.commit()
    
    return {
        "answer": answer,
        "citations": citations,
        "trace": trace
    }

# HISTORIC CHAT LIST
@app.get("/api/chat/history/{session_id}")
def get_chat_history(session_id: str, db: Session = Depends(get_db)):
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp.asc()).all()
    history = []
    for msg in messages:
        cits = json.loads(msg.citations) if msg.citations else []
        trc = json.loads(msg.trace) if msg.trace else None
        history.append({
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "citations": cits,
            "trace": trc,
            "timestamp": msg.timestamp
        })
    return history

# PRODUCT SEARCH ENDPOINT
@app.get("/api/products/search")
def search_products(query: str = "", db: Session = Depends(get_db)):
    """SQL-driven product and inventory search."""
    sql = """
        SELECT p.sku, p.name, p.category, p.price, p.unit, s.name as supplier_name,
               SUM(CASE WHEN i.location_type = 'Warehouse' THEN i.current_stock ELSE 0 END) as warehouse_stock,
               SUM(CASE WHEN i.location_type = 'Store' THEN i.current_stock ELSE 0 END) as store_stock
        FROM products p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        LEFT JOIN inventory i ON p.sku = i.product_sku
        WHERE p.name LIKE :q OR p.sku LIKE :q OR p.category LIKE :q
        GROUP BY p.sku;
    """
    result = db.execute(text(sql), {"q": f"%{query}%"})
    headers = list(result.keys())
    rows = [dict(zip(headers, row)) for row in result.fetchall()]
    return rows

# SYSTEM AUDIT LOGS ENDPOINT
@app.get("/api/admin/logs")
def get_admin_logs(
    db: Session = Depends(get_db), 
    user: dict = Depends(get_current_user)
):
    """Returns the last 100 execution audit logs."""
    verify_role(["Administrator"], user)
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
    return logs

# KPI METRICS ENDPOINT
@app.get("/api/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Calculates operational stats directly from SQL tables."""
    # 1. Total Inventory
    tot_inv_result = db.execute(text("SELECT SUM(current_stock) FROM inventory")).scalar() or 0
    
    # 2. Low Stock SKUs Count
    low_stock_result = db.execute(text("SELECT COUNT(DISTINCT product_sku) FROM inventory WHERE current_stock <= reorder_threshold")).scalar() or 0
    
    # 3. Active / Delayed POs
    delayed_pos = db.execute(text("SELECT COUNT(DISTINCT po_number) FROM purchase_orders WHERE status = 'Delayed'")).scalar() or 0
    pending_pos = db.execute(text("SELECT COUNT(DISTINCT po_number) FROM purchase_orders WHERE status = 'Pending' OR status = 'Shipped'")).scalar() or 0
    
    # 4. OTIF Delivery Rate
    tot_deliv = db.execute(text("SELECT COUNT(*) FROM shipments WHERE status = 'Delivered'")).scalar() or 0
    late_deliv = db.execute(text("SELECT COUNT(*) FROM shipments WHERE status = 'Delivered' AND (notes LIKE '%late%' OR notes LIKE '%delay%')")).scalar() or 0
    otif = 100.0
    if tot_deliv > 0:
        otif = round(((tot_deliv - late_deliv) / tot_deliv) * 100, 1)
        
    # 5. Inventory Chart Data (Limit to top 8 items)
    chart_sql = """
        SELECT p.name, SUM(i.current_stock) as stock, SUM(i.reorder_threshold) as threshold
        FROM products p
        JOIN inventory i ON p.sku = i.product_sku
        GROUP BY p.sku LIMIT 8;
    """
    chart_res = db.execute(text(chart_sql)).fetchall()
    inv_labels = [row[0][:15] + "..." if len(row[0]) > 15 else row[0] for row in chart_res]
    inv_stock = [row[1] for row in chart_res]
    inv_threshold = [row[2] for row in chart_res]
    
    # 6. Shipping Chart Data
    ship_counts = [
        db.execute(text("SELECT COUNT(*) FROM shipments WHERE status = 'Delivered' AND NOT (notes LIKE '%late%' OR notes LIKE '%delay%')")).scalar() or 0,
        db.execute(text("SELECT COUNT(*) FROM shipments WHERE status = 'Delivered' AND (notes LIKE '%late%' OR notes LIKE '%delay%')")).scalar() or 0,
        db.execute(text("SELECT COUNT(*) FROM shipments WHERE status = 'In Transit'")).scalar() or 0,
        db.execute(text("SELECT COUNT(*) FROM shipments WHERE status = 'Delayed'")).scalar() or 0
    ]
    
    # Retrieve low stock table alerts to show in dashboard
    low_stock_table_sql = """
        SELECT p.sku, p.name, i.location_name, i.current_stock, i.reorder_threshold, s.name as supplier
        FROM inventory i
        JOIN products p ON i.product_sku = p.sku
        JOIN suppliers s ON p.supplier_id = s.id
        WHERE i.current_stock <= i.reorder_threshold
        LIMIT 6;
    """
    low_stock_rows = [dict(zip(["sku", "name", "location", "stock", "threshold", "supplier"], row)) 
                      for row in db.execute(text(low_stock_table_sql)).fetchall()]

    return {
        "total_inventory_items": tot_inv_result,
        "low_stock_sku_count": low_stock_result,
        "pending_shipments": pending_pos,
        "delayed_shipments": delayed_pos,
        "otif_delivery_rate": otif,
        "inventory_chart": {
            "labels": inv_labels,
            "stock": inv_stock,
            "threshold": inv_threshold
        },
        "shipping_chart": {
            "labels": ["Delivered On-Time", "Delivered Late", "In Transit", "Delayed"],
            "counts": ship_counts
        },
        "low_stock_table": low_stock_rows
    }

# REPORT DOWNLOAD ENDPOINT
@app.post("/api/reports/download")
def download_report(request: ReportDownloadRequest):
    """Exposes an endpoint to stream generated markdown content as an attachment."""
    def iter_content():
        yield request.content.encode('utf-8')
        
    return StreamingResponse(
        iter_content(),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={request.filename}"}
    )

# Ingest Pydantic Models
class ApiIngestRequest(BaseModel):
    url: str
    target_table: str
    mapping: Optional[dict] = None

class OpenSourceIngestRequest(BaseModel):
    url: str
    filename: Optional[str] = None
    title: Optional[str] = None

# MOCK ENDPOINTS FOR OFFLINE TESTING AND PRESETS
@app.get("/api/mock/shipments")
def get_mock_shipments():
    """Provides a local mock API that simulates an external shipping logistics endpoint."""
    return {
        "shipments": [
            {
                "tracking_number": "TRK-NEXUS-901",
                "po_number": "PO-1002",
                "carrier": "SwiftCargo Express",
                "status": "Delayed",
                "origin": "Port of Los Angeles DC",
                "destination": "Store 210",
                "estimated_delivery": (datetime.datetime.utcnow() + datetime.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),
                "notes": "Severe customs queue at port entrance. Delivery SLA delayed by 3 days."
            },
            {
                "tracking_number": "TRK-NEXUS-902",
                "po_number": "PO-1003",
                "carrier": "VoltRail Logistics",
                "status": "In Transit",
                "origin": "VoltBright Manufacturing Hub",
                "destination": "Warehouse West",
                "estimated_delivery": (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                "notes": "On-schedule. Moving through midwest corridor."
            },
            {
                "tracking_number": "TRK-NEXUS-903",
                "po_number": "PO-1004",
                "carrier": "FedEx Freight",
                "status": "Delivered",
                "origin": "ScanTech Corp Facility",
                "destination": "Warehouse East",
                "estimated_delivery": (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                "notes": "Delivered on-time. Recieved by J. Doe."
            }
        ]
    }

@app.get("/api/mock/opensource/walmart")
def get_mock_opensource_walmart():
    """Provides a local mock open source dataset representing Walmart product catalogs and returns it as a CSV."""
    from fastapi.responses import Response
    csv_content = (
        "sku,product_name,category,price,unit,supplier_name,description\n"
        "WM-101,Equate Daily Fiber Supplement,Health & Wellness,12.97,bottle,PaperCo Supply,Walmart Health Brand daily fiber mix 100% natural psyllium husk.\n"
        "WM-102,Mainstays 20-Inch Box Fan,Home & Kitchen,21.84,unit,VoltBright,3-speed box fan with sleek white design and carry handle.\n"
        "WM-103,Great Value Organic Honey,Consumables,5.48,bottle,PaperCo Supply,Grade A USDA certified organic honey net wt 12 oz.\n"
        "WM-104,Onn 32-Inch LED Roku Smart TV,Electronics,98.00,unit,ScanTech Corp,720p HD resolution smart television with built-in Roku streaming channel.\n"
        "WM-105,Hyper Tough 20V Cordless Drill,Hardware,29.97,unit,IronClad Parts,Includes 20V Max lithium-ion battery charger and double ended driver bit.\n"
    )
    return Response(content=csv_content, media_type="text/csv")

# PRESETS API
@app.get("/api/ingest/presets")
def get_ingest_presets():
    return {
        "api_presets": [
            {
                "name": "DummyJSON Product Catalog (External)",
                "url": "https://dummyjson.com/products?limit=10",
                "target_table": "products",
                "mapping": {
                    "sku": "id",
                    "name": "title",
                    "price": "price",
                    "category": "category"
                }
            },
            {
                "name": "Nexus Mock Logistics Shipments API (Local)",
                "url": "http://localhost:8000/api/mock/shipments",
                "target_table": "shipments",
                "mapping": {
                    "tracking_number": "tracking_number",
                    "po_number": "po_number",
                    "carrier": "carrier",
                    "status": "status",
                    "origin": "origin",
                    "destination": "destination",
                    "notes": "notes"
                }
            }
        ],
        "opensource_presets": [
            {
                "name": "Walmart Brand Catalog (Local Preset)",
                "url": "http://localhost:8000/api/mock/opensource/walmart",
                "filename": "walmart_brand_catalog.csv",
                "title": "Walmart Brand Product Catalog"
            },
            {
                "name": "GitHub Retail Store Policy Additions (External)",
                "url": "https://raw.githubusercontent.com/saurabhgup/walmart-dataset/master/walmart.csv",
                "filename": "github_walmart_retail.csv",
                "title": "GitHub Walmart Retail Dataset"
            }
        ]
    }

# API INGESTION ENDPOINT
@app.post("/api/ingest/api")
def ingest_from_api(request: ApiIngestRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    verify_role(["Administrator", "Category Manager", "Procurement Manager"], user)
    try:
        if "api/mock/shipments" in request.url or "localhost:8000/api/mock/shipments" in request.url:
            data = get_mock_shipments()
        else:
            res = requests.get(request.url, timeout=15)
            res.raise_for_status()
            data = res.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch data from API endpoint: {e}")

    # Inspect JSON structure
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        # Look for the first value that is a list
        for k, v in data.items():
            if isinstance(v, list):
                items = v
                break
        if not items:
            items = [data] # Treat single dict as list of one

    if not items:
        raise HTTPException(status_code=422, detail="No iterable lists found in the API JSON response.")

    mapping = request.mapping or {}
    success_count = 0
    errors = []
    ingested_texts = []

    if request.target_table == "products":
        for i, item in enumerate(items):
            try:
                # Resolve mapping fields
                raw_id = item.get(mapping.get("sku", "id")) or item.get("id") or item.get("sku")
                if not raw_id:
                    raw_id = f"API-{i+1}"
                sku = str(raw_id)
                if not sku.startswith("WM-") and not sku.startswith("API-"):
                    sku = f"API-{sku}"
                
                name = item.get(mapping.get("name", "title")) or item.get("name") or item.get("title") or f"API Product {sku}"
                category = item.get(mapping.get("category", "category")) or item.get("category") or "General"
                price = float(item.get(mapping.get("price", "price")) or item.get("price") or 10.0)
                unit = item.get(mapping.get("unit", "unit")) or item.get("unit") or "unit"
                supplier_id = int(item.get(mapping.get("supplier_id", "supplier_id")) or item.get("supplier_id") or 1)

                # Upsert Product
                prod = db.query(Product).filter(Product.sku == sku).first()
                if not prod:
                    prod = Product(sku=sku, name=name, category=category, price=price, unit=unit, supplier_id=supplier_id)
                    db.add(prod)
                else:
                    prod.name = name
                    prod.category = category
                    prod.price = price
                    prod.unit = unit
                    prod.supplier_id = supplier_id
                
                # Check if we have inventory row, if not create one
                inv = db.query(Inventory).filter(Inventory.product_sku == sku).first()
                if not inv:
                    inv = Inventory(
                        product_sku=sku,
                        location_type="Warehouse",
                        location_name="Warehouse East",
                        current_stock=50,
                        reorder_threshold=15,
                        status="OK"
                    )
                    db.add(inv)

                success_count += 1
                ingested_texts.append(f"Product SKU {sku}: {name} ({category}), unit price ${price:.2f}, supplied by supplier ID {supplier_id}.")
            except Exception as e:
                errors.append(f"Item #{i+1}: {e}")

        # Index to RAG as well! Write to file
        if ingested_texts:
            rag_file_path = os.path.join(DATA_DIR, "api_ingested_products.txt")
            mode = "a" if os.path.exists(rag_file_path) else "w"
            with open(rag_file_path, mode, encoding="utf-8") as f:
                f.write("\n" + "\n".join(ingested_texts) + "\n")
            rag_engine.reindex_all()

    elif request.target_table == "shipments":
        for i, item in enumerate(items):
            try:
                tracking = item.get(mapping.get("tracking_number", "tracking_number")) or item.get("tracking_number") or f"TRK-{i+1}"
                po = item.get(mapping.get("po_number", "po_number")) or item.get("po_number") or "PO-1002"
                carrier = item.get(mapping.get("carrier", "carrier")) or item.get("carrier") or "SwiftCargo"
                status = item.get(mapping.get("status", "status")) or item.get("status") or "In Transit"
                origin = item.get(mapping.get("origin", "origin")) or item.get("origin") or "Factory Hub"
                destination = item.get(mapping.get("destination", "destination")) or item.get("destination") or "Warehouse East"
                notes = item.get(mapping.get("notes", "notes")) or item.get("notes") or ""

                ship = db.query(Shipment).filter(Shipment.tracking_number == tracking).first()
                if not ship:
                    ship = Shipment(
                        tracking_number=tracking, po_number=po, carrier=carrier, 
                        status=status, origin=origin, destination=destination, notes=notes
                    )
                    db.add(ship)
                else:
                    ship.po_number = po
                    ship.carrier = carrier
                    ship.status = status
                    ship.origin = origin
                    ship.destination = destination
                    ship.notes = notes
                
                success_count += 1
                ingested_texts.append(f"Shipment {tracking} for PO {po} via carrier {carrier} from {origin} to {destination} is {status}. Notes: {notes}")
            except Exception as e:
                errors.append(f"Item #{i+1}: {e}")

        # Index to RAG as well! Write to file
        if ingested_texts:
            rag_file_path = os.path.join(DATA_DIR, "api_ingested_shipments.txt")
            mode = "a" if os.path.exists(rag_file_path) else "w"
            with open(rag_file_path, mode, encoding="utf-8") as f:
                f.write("\n" + "\n".join(ingested_texts) + "\n")
            rag_engine.reindex_all()

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported target table: {request.target_table}")

    db.commit()
    return {
        "status": "success",
        "message": f"Successfully ingested {success_count} records into {request.target_table}.",
        "errors": errors
    }

# OPEN SOURCE DATASET INGESTION ENDPOINT
@app.post("/api/ingest/opensource")
def ingest_opensource_dataset(request: OpenSourceIngestRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    verify_role(["Administrator", "Category Manager", "Procurement Manager"], user)
    
    filename = request.filename or "opensource_dataset.csv"
    if not filename.endswith(('.csv', '.json', '.txt')):
        filename += ".csv"
        
    file_path = os.path.join(DATA_DIR, filename)
    
    # Download content
    try:
        res = requests.get(request.url, timeout=20)
        res.raise_for_status()
        content = res.text
    except Exception as e:
        # Fallback to local preset generation if network fails or URL is offline
        if "mock/opensource/walmart" in request.url:
            content = (
                "sku,product_name,category,price,unit,supplier_name,description\n"
                "WM-101,Equate Daily Fiber Supplement,Health & Wellness,12.97,bottle,PaperCo Supply,Walmart Health Brand daily fiber mix 100% natural psyllium husk.\n"
                "WM-102,Mainstays 20-Inch Box Fan,Home & Kitchen,21.84,unit,VoltBright,3-speed box fan with sleek white design.\n"
                "WM-103,Great Value Organic Honey,Consumables,5.48,bottle,PaperCo Supply,Grade A USDA certified organic honey.\n"
                "WM-104,Onn 32-Inch LED Roku Smart TV,Electronics,98.00,unit,ScanTech Corp,720p HD resolution smart television.\n"
            )
        else:
            raise HTTPException(status_code=400, detail=f"Failed to fetch dataset from public URL: {e}")
            
    # Save file to RAG DATA_DIR
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write dataset file: {e}")
        
    # Process structured content into SQLite DB if it contains tabular product columns
    parsed_records = 0
    errors = []
    try:
        if filename.endswith('.csv'):
            import io
            f_in = io.StringIO(content)
            reader = csv.DictReader(f_in)
            
            # Map common headers to SQLite Product table
            headers = reader.fieldnames or []
            sku_col = next((h for h in headers if h.lower() in ['sku', 'id', 'product_id']), None)
            name_col = next((h for h in headers if h.lower() in ['name', 'product_name', 'title']), None)
            price_col = next((h for h in headers if h.lower() in ['price', 'cost']), None)
            cat_col = next((h for h in headers if h.lower() in ['category', 'dept', 'department']), None)
            
            if sku_col and name_col:
                for row_idx, row in enumerate(reader):
                    try:
                        sku = str(row.get(sku_col)).strip()
                        name = str(row.get(name_col)).strip()
                        if not sku or not name:
                            continue
                            
                        # Format sku
                        if not sku.startswith("WM-") and not sku.startswith("API-"):
                            sku = f"WM-{sku}"
                            
                        category = str(row.get(cat_col, 'General')).strip()
                        price_str = row.get(price_col, '10.00').replace('$', '').strip()
                        price = float(price_str) if price_str else 10.00
                        
                        # Upsert Product
                        prod = db.query(Product).filter(Product.sku == sku).first()
                        if not prod:
                            prod = Product(sku=sku, name=name, category=category, price=price, unit="unit", supplier_id=1)
                            db.add(prod)
                        else:
                            prod.name = name
                            prod.category = category
                            prod.price = price
                        
                        # Inventory check
                        inv = db.query(Inventory).filter(Inventory.product_sku == sku).first()
                        if not inv:
                            inv = Inventory(
                                product_sku=sku,
                                location_type="Warehouse",
                                location_name="Warehouse East",
                                current_stock=100,
                                reorder_threshold=20,
                                status="OK"
                            )
                            db.add(inv)
                            
                        parsed_records += 1
                    except Exception as ex:
                        errors.append(f"Row {row_idx+1}: {ex}")
                db.commit()
    except Exception as e:
        print(f"Error parsing Open Source CSV structure: {e}")
        
    # Reindex RAG
    try:
        rag_engine.reindex_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dataset saved, but RAG indexing failed: {e}")
        
    msg = f"Successfully downloaded and indexed '{filename}' for RAG search."
    if parsed_records > 0:
        msg += f" Imported {parsed_records} structured products into SQL database."
        
    return {
        "status": "success",
        "message": msg,
        "filename": filename,
        "parsed_records": parsed_records,
        "errors": errors
    }

# UPDATE GEMINI API KEY
@app.post("/api/config/key")
def update_key(payload: dict):
    key = payload.get("api_key", "").strip()
    rag_engine.set_api_key(key)
    return {"status": "success", "message": "API key updated successfully", "has_key": bool(key)}
