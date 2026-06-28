import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import init_db, SessionLocal, User, Product, Inventory, SalesTransaction, PurchaseOrder, Supplier, CustomerFeedback, Promotion, Shipment

def seed_data():
    print("Initializing Database...")
    init_db()
    
    db = SessionLocal()
    try:
        # Check if database is already seeded
        if db.query(User).first():
            print("Database already contains data. Skipping seeding.")
            return

        # 1. Seed Users (Roles: Admin, Store Manager, Supply Chain Analyst, Category Manager, Procurement Manager)
        print("Seeding Users...")
        # Since we use passlib, we hash the password 'password123'
        import bcrypt
        hashed_pwd = bcrypt.hashpw("password123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
        users = [
            User(username="admin", password_hash=hashed_pwd, role="Administrator"),
            User(username="store_manager", password_hash=hashed_pwd, role="Store Manager"),
            User(username="analyst", password_hash=hashed_pwd, role="Supply Chain Analyst"),
            User(username="planner", password_hash=hashed_pwd, role="Inventory Planner"),
            User(username="category_mgr", password_hash=hashed_pwd, role="Category Manager"),
            User(username="procurement_mgr", password_hash=hashed_pwd, role="Procurement Manager"),
        ]
        db.add_all(users)
        
        # 2. Seed Suppliers
        print("Seeding Suppliers...")
        suppliers = [
            Supplier(id=1, name="VoltBright", contact_person="John Volt", email="john@voltbright.com", phone="555-0101", sla_lead_time_days=5, performance_score=95.5),
            Supplier(id=2, name="IronClad Parts", contact_person="Sarah Iron", email="sarah@ironclad.com", phone="555-0102", sla_lead_time_days=10, performance_score=82.0),
            Supplier(id=3, name="ScanTech Corp", contact_person="Alan Scanner", email="alan@scantech.com", phone="555-0103", sla_lead_time_days=6, performance_score=98.2),
            Supplier(id=4, name="PaperCo Supply", contact_person="Pam Paper", email="pam@paperco.com", phone="555-0104", sla_lead_time_days=3, performance_score=89.4),
            Supplier(id=5, name="TraceTags Inc", contact_person="Tom Tag", email="tom@tracetags.com", phone="555-0105", sla_lead_time_days=8, performance_score=75.0),
            Supplier(id=6, name="Supplier XYZ", contact_person="Zoe Xavier", email="zoe@supplierxyz.com", phone="555-0199", sla_lead_time_days=15, performance_score=62.5),
        ]
        db.add_all(suppliers)
        db.commit() # Commit suppliers so products can reference them
        
        # 3. Seed Products
        print("Seeding Products...")
        products = [
            Product(sku="P100", name="Barcode Scanner Pro", category="Electronics", price=149.99, unit="unit", supplier_id=3), # ScanTech
            Product(sku="PROD-X", name="Product X (Paper Organizer)", category="Office Equipment", price=45.00, unit="box", supplier_id=4), # PaperCo
            Product(sku="PROD-ABC", name="Product ABC (Label Printer)", category="Logistics Tools", price=299.99, unit="unit", supplier_id=1), # VoltBright
            Product(sku="PROD-Y", name="Product Y (Rugged Tablet)", category="Electronics", price=489.99, unit="unit", supplier_id=2), # IronClad
            Product(sku="PROD-101", name="Thermal Receipt Roll", category="Consumables", price=1.50, unit="roll", supplier_id=4), # PaperCo
            Product(sku="PROD-102", name="Pallet Jack Heavy Duty", category="Warehouse Equip", price=350.00, unit="unit", supplier_id=2), # IronClad
            Product(sku="PROD-103", name="Wireless Gateway Hub", category="Electronics", price=199.99, unit="unit", supplier_id=6), # Supplier XYZ
        ]
        db.add_all(products)
        db.commit()
        
        # 4. Seed Inventory Status across Stores and Warehouses
        print("Seeding Inventory...")
        inventory_items = [
            # P100 barcode scanner (low stock across all locations)
            Inventory(product_sku="P100", location_type="Store", location_name="Store 210", current_stock=2, reorder_threshold=15, status="LOW STOCK"),
            Inventory(product_sku="P100", location_type="Store", location_name="Store 105", current_stock=1, reorder_threshold=10, status="LOW STOCK"),
            Inventory(product_sku="P100", location_type="Warehouse", location_name="Warehouse East", current_stock=5, reorder_threshold=30, status="LOW STOCK"),
            Inventory(product_sku="P100", location_type="Warehouse", location_name="Warehouse West", current_stock=1, reorder_threshold=30, status="LOW STOCK"),
            
            # Product X availability (available across multiple warehouses)
            Inventory(product_sku="PROD-X", location_type="Warehouse", location_name="Warehouse East", current_stock=120, reorder_threshold=50, status="OK"),
            Inventory(product_sku="PROD-X", location_type="Warehouse", location_name="Warehouse West", current_stock=85, reorder_threshold=50, status="OK"),
            Inventory(product_sku="PROD-X", location_type="Store", location_name="Store 210", current_stock=45, reorder_threshold=20, status="OK"),
            Inventory(product_sku="PROD-X", location_type="Store", location_name="Store 105", current_stock=8, reorder_threshold=20, status="LOW STOCK"),
            
            # Product ABC
            Inventory(product_sku="PROD-ABC", location_type="Warehouse", location_name="Warehouse East", current_stock=60, reorder_threshold=20, status="OK"),
            Inventory(product_sku="PROD-ABC", location_type="Store", location_name="Store 210", current_stock=2, reorder_threshold=5, status="LOW STOCK"),
            
            # Product Y
            Inventory(product_sku="PROD-Y", location_type="Warehouse", location_name="Warehouse East", current_stock=14, reorder_threshold=10, status="OK"),
            Inventory(product_sku="PROD-Y", location_type="Store", location_name="Store 105", current_stock=1, reorder_threshold=5, status="LOW STOCK"),
            
            # Consumables
            Inventory(product_sku="PROD-101", location_type="Warehouse", location_name="Warehouse East", current_stock=1500, reorder_threshold=500, status="OK"),
            Inventory(product_sku="PROD-101", location_type="Store", location_name="Store 210", current_stock=12, reorder_threshold=50, status="LOW STOCK"), # store 210 needs replenishment
            Inventory(product_sku="PROD-101", location_type="Store", location_name="Store 105", current_stock=250, reorder_threshold=100, status="OK"),
            
            # Gateway Hub (Supplier XYZ)
            Inventory(product_sku="PROD-103", location_type="Warehouse", location_name="Warehouse West", current_stock=4, reorder_threshold=15, status="LOW STOCK"),
        ]
        db.add_all(inventory_items)
        
        # 5. Seed Sales Transactions (past 30 days)
        print("Seeding Sales Transactions...")
        now = datetime.utcnow()
        transactions = []
        
        # High sales volume for P100 causing the out-of-stock scenario
        for day in range(30, 0, -2):
            txn_time = now - timedelta(days=day)
            transactions.append(SalesTransaction(
                transaction_id=f"TXN-100{day}",
                product_sku="P100",
                quantity=4,
                store_name="Store 210",
                price_per_unit=149.99,
                total_amount=599.96,
                timestamp=txn_time
            ))
            transactions.append(SalesTransaction(
                transaction_id=f"TXN-101{day}",
                product_sku="P100",
                quantity=3,
                store_name="Store 105",
                price_per_unit=149.99,
                total_amount=449.97,
                timestamp=txn_time
            ))
            
        # Sales and Returns for Product Y (to show return rate)
        for day in range(25, 0, -3):
            txn_time = now - timedelta(days=day)
            # Normal sales
            transactions.append(SalesTransaction(
                transaction_id=f"TXN-200{day}",
                product_sku="PROD-Y",
                quantity=1,
                store_name="Store 105",
                price_per_unit=489.99,
                total_amount=489.99,
                timestamp=txn_time
            ))
            # Returned sales
            if day in [25, 16, 7]:
                transactions.append(SalesTransaction(
                    transaction_id=f"TXN-200{day}-R",
                    product_sku="PROD-Y",
                    quantity=1,
                    store_name="Store 105",
                    price_per_unit=489.99,
                    total_amount=489.99,
                    timestamp=txn_time - timedelta(hours=5),
                    is_returned=True,
                    return_reason="Screen defects / device freezing"
                ))
                
        # Other normal sales for Store 105 to help compile a report
        for day in range(5, 0, -1):
            txn_time = now - timedelta(days=day)
            transactions.append(SalesTransaction(
                transaction_id=f"TXN-300{day}",
                product_sku="PROD-101",
                quantity=20,
                store_name="Store 105",
                price_per_unit=1.50,
                total_amount=30.00,
                timestamp=txn_time
            ))
            transactions.append(SalesTransaction(
                transaction_id=f"TXN-301{day}",
                product_sku="PROD-X",
                quantity=2,
                store_name="Store 105",
                price_per_unit=45.00,
                total_amount=90.00,
                timestamp=txn_time
            ))
            
        db.add_all(transactions)
        
        # 6. Seed Purchase Orders & Shipments
        print("Seeding Purchase Orders & Shipments...")
        pos = [
            # PO for P100 which is delayed (helps explain out of stock)
            PurchaseOrder(
                po_number="PO-9001",
                supplier_id=3, # ScanTech
                product_sku="P100",
                quantity=100,
                status="Delayed",
                order_date=now - timedelta(days=20),
                expected_delivery=now - timedelta(days=5),
                notes="Delayed due to critical component shortages at factory level."
            ),
            # PO for Product ABC (Delivered)
            PurchaseOrder(
                po_number="PO-9002",
                supplier_id=1, # VoltBright
                product_sku="PROD-ABC",
                quantity=50,
                status="Delivered",
                order_date=now - timedelta(days=10),
                expected_delivery=now - timedelta(days=3),
                notes="Delivered on time."
            ),
            # Delayed POs for Supplier XYZ
            PurchaseOrder(
                po_number="PO-9501",
                supplier_id=6, # Supplier XYZ
                product_sku="PROD-103", # Gateway Hub
                quantity=40,
                status="Delayed",
                order_date=now - timedelta(days=25),
                expected_delivery=now - timedelta(days=10),
                notes="Customs holding and clearance delay."
            ),
            PurchaseOrder(
                po_number="PO-9502",
                supplier_id=6, # Supplier XYZ
                product_sku="PROD-103",
                quantity=20,
                status="Delayed",
                order_date=now - timedelta(days=18),
                expected_delivery=now - timedelta(days=4),
                notes="Logistics carrier capacity bottleneck."
            ),
        ]
        db.add_all(pos)
        db.commit()
        
        # Seed Shipments corresponding to POs
        shipments = [
            Shipment(
                tracking_number="TRK-SCAN-01",
                po_number="PO-9001",
                carrier="SwiftCargo",
                status="Delayed",
                origin="Chicago Hub",
                destination="Warehouse East",
                estimated_delivery=now - timedelta(days=5),
                notes="Shipment stuck at hub due to transit weather delays."
            ),
            Shipment(
                tracking_number="TRK-VOLT-02",
                po_number="PO-9002",
                carrier="BlueStreak Logistics",
                status="Delivered",
                origin="Detroit Warehouse",
                destination="Warehouse East",
                estimated_delivery=now - timedelta(days=3),
                actual_delivery=now - timedelta(days=3),
                notes="Delivered in good condition."
            ),
            Shipment(
                tracking_number="TRK-XYZ-01",
                po_number="PO-9501",
                carrier="FedEx Freight",
                status="Delayed",
                origin="Seattle Port",
                destination="Warehouse West",
                estimated_delivery=now - timedelta(days=10),
                notes="Shipment delayed at customs inspection."
            ),
            Shipment(
                tracking_number="TRK-XYZ-02",
                po_number="PO-9502",
                carrier="FedEx Freight",
                status="Delayed",
                origin="Seattle Port",
                destination="Warehouse West",
                estimated_delivery=now - timedelta(days=4),
                notes="Pending carrier pickup."
            )
        ]
        db.add_all(shipments)
        
        # 7. Seed Customer Feedback (Customer complaints related to Product Y)
        print("Seeding Customer Feedback...")
        feedback = [
            CustomerFeedback(customer_name="Alice Smith", product_sku="PROD-Y", rating=1, feedback_text="Rugged Tablet screen cracked on first light drop. Definitely not military grade as advertised.", sentiment="Negative", timestamp=now - timedelta(days=20)),
            CustomerFeedback(customer_name="Bob Jones", product_sku="PROD-Y", rating=2, feedback_text="Operating system keeps freezing during barcode scanning. Very frustrating.", sentiment="Negative", timestamp=now - timedelta(days=15)),
            CustomerFeedback(customer_name="Charlie Brown", product_sku="PROD-Y", rating=1, feedback_text="Battery swelling issues after 1 week of usage. Returning immediately.", sentiment="Negative", timestamp=now - timedelta(days=6)),
            CustomerFeedback(customer_name="David Davis", product_sku="P100", rating=5, feedback_text="Excellent scan response time. The store staff love this model.", sentiment="Positive", timestamp=now - timedelta(days=12)),
            CustomerFeedback(customer_name="Eva Elves", product_sku="PROD-X", rating=4, feedback_text="Decent paper organizer, holds a lot of documents.", sentiment="Positive", timestamp=now - timedelta(days=10)),
        ]
        db.add_all(feedback)
        
        # 8. Seed Promotions
        print("Seeding Promotions...")
        promotions = [
            Promotion(campaign_name="Electronics Expo", discount_rate=10.0, start_date=now - timedelta(days=30), end_date=now + timedelta(days=5), policy_version="V3", rules_text="10% discount on all scanner products. Applies to P100 and PROD-ABC. Policy V3 rules apply: returns must be made within 14 days and require original receipt."),
            Promotion(campaign_name="Warehouse Liquidation", discount_rate=20.0, start_date=now - timedelta(days=5), end_date=now + timedelta(days=10), policy_version="V5", rules_text="20% off office supplies. Policy V5 rules apply: strictly no cash refunds; returns are issued only as store credit. Promotion rules apply to all locations including online checkout."),
        ]
        db.add_all(promotions)
        
        db.commit()
        print("Database seeded successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
