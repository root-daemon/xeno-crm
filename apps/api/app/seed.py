CUSTOMERS = [
    {"id": "cus_001", "name": "Aarav Mehta", "phone": "+919810000001", "email": "aarav@example.com", "city": "Mumbai", "gender": "male", "loyalty_tier": "gold", "tags": ["sneakerhead"], "whatsapp_opt_in": True, "sms_opt_in": True, "email_opt_in": True, "rcs_opt_in": False, "last_active_days_ago": 4},
    {"id": "cus_002", "name": "Anaya Rao", "phone": "+919810000002", "email": "anaya@example.com", "city": "Bengaluru", "gender": "female", "loyalty_tier": "platinum", "tags": ["beauty", "premium"], "whatsapp_opt_in": True, "sms_opt_in": False, "email_opt_in": True, "rcs_opt_in": True, "last_active_days_ago": 2},
    {"id": "cus_003", "name": "Kabir Singh", "phone": "+919810000003", "email": "kabir@example.com", "city": "Delhi", "gender": "male", "loyalty_tier": "silver", "tags": ["coffee"], "whatsapp_opt_in": True, "sms_opt_in": True, "email_opt_in": False, "rcs_opt_in": False, "last_active_days_ago": 18},
    {"id": "cus_004", "name": "Mira Iyer", "phone": "+919810000004", "email": "mira@example.com", "city": "Chennai", "gender": "female", "loyalty_tier": "gold", "tags": ["ethnic", "sale"], "whatsapp_opt_in": True, "sms_opt_in": True, "email_opt_in": True, "rcs_opt_in": True, "last_active_days_ago": 9},
    {"id": "cus_005", "name": "Vivaan Kapoor", "phone": "+919810000005", "email": "vivaan@example.com", "city": "Mumbai", "gender": "male", "loyalty_tier": "bronze", "tags": ["new"], "whatsapp_opt_in": False, "sms_opt_in": True, "email_opt_in": True, "rcs_opt_in": False, "last_active_days_ago": 40},
    {"id": "cus_006", "name": "Ira Nair", "phone": "+919810000006", "email": "ira@example.com", "city": "Kochi", "gender": "female", "loyalty_tier": "silver", "tags": ["skincare"], "whatsapp_opt_in": True, "sms_opt_in": False, "email_opt_in": True, "rcs_opt_in": True, "last_active_days_ago": 13},
    {"id": "cus_007", "name": "Reyansh Shah", "phone": "+919810000007", "email": "reyansh@example.com", "city": "Ahmedabad", "gender": "male", "loyalty_tier": "gold", "tags": ["festive"], "whatsapp_opt_in": True, "sms_opt_in": True, "email_opt_in": True, "rcs_opt_in": True, "last_active_days_ago": 7},
    {"id": "cus_008", "name": "Diya Menon", "phone": "+919810000008", "email": "diya@example.com", "city": "Pune", "gender": "female", "loyalty_tier": "platinum", "tags": ["premium", "repeat"], "whatsapp_opt_in": True, "sms_opt_in": False, "email_opt_in": True, "rcs_opt_in": True, "last_active_days_ago": 1},
    {"id": "cus_009", "name": "Arjun Batra", "phone": "+919810000009", "email": "arjun@example.com", "city": "Delhi", "gender": "male", "loyalty_tier": "silver", "tags": ["lapsed"], "whatsapp_opt_in": True, "sms_opt_in": True, "email_opt_in": True, "rcs_opt_in": False, "last_active_days_ago": 65},
    {"id": "cus_010", "name": "Saanvi Gill", "phone": "+919810000010", "email": "saanvi@example.com", "city": "Jaipur", "gender": "female", "loyalty_tier": "gold", "tags": ["wedding"], "whatsapp_opt_in": True, "sms_opt_in": True, "email_opt_in": True, "rcs_opt_in": False, "last_active_days_ago": 5},
    {"id": "cus_011", "name": "Neil Dsouza", "phone": "+919810000011", "email": "neil@example.com", "city": "Goa", "gender": "male", "loyalty_tier": "bronze", "tags": ["coffee", "new"], "whatsapp_opt_in": True, "sms_opt_in": True, "email_opt_in": False, "rcs_opt_in": True, "last_active_days_ago": 22},
    {"id": "cus_012", "name": "Tara Bose", "phone": "+919810000012", "email": "tara@example.com", "city": "Kolkata", "gender": "female", "loyalty_tier": "silver", "tags": ["beauty", "lapsed"], "whatsapp_opt_in": False, "sms_opt_in": True, "email_opt_in": True, "rcs_opt_in": False, "last_active_days_ago": 74},
]

ORDERS = [
    {"id": "ord_001", "customer_id": "cus_001", "total": 4200, "items": ["white sneakers", "crew socks"], "channel": "store", "days_ago": 12},
    {"id": "ord_002", "customer_id": "cus_002", "total": 7800, "items": ["serum kit", "night cream"], "channel": "online", "days_ago": 16},
    {"id": "ord_003", "customer_id": "cus_003", "total": 950, "items": ["cold brew pack"], "channel": "online", "days_ago": 55},
    {"id": "ord_004", "customer_id": "cus_004", "total": 3600, "items": ["kurta set"], "channel": "store", "days_ago": 24},
    {"id": "ord_005", "customer_id": "cus_006", "total": 2200, "items": ["cleanser", "sunscreen"], "channel": "online", "days_ago": 38},
    {"id": "ord_006", "customer_id": "cus_007", "total": 5100, "items": ["festive jacket"], "channel": "online", "days_ago": 20},
    {"id": "ord_007", "customer_id": "cus_008", "total": 8900, "items": ["premium dress", "earrings"], "channel": "store", "days_ago": 8},
    {"id": "ord_008", "customer_id": "cus_009", "total": 1800, "items": ["denim shirt"], "channel": "online", "days_ago": 110},
    {"id": "ord_009", "customer_id": "cus_010", "total": 6400, "items": ["lehenga accessory set"], "channel": "store", "days_ago": 29},
    {"id": "ord_010", "customer_id": "cus_012", "total": 1400, "items": ["lip tint"], "channel": "online", "days_ago": 130},
    {"id": "ord_011", "customer_id": "cus_001", "total": 3200, "items": ["hoodie"], "channel": "online", "days_ago": 42},
    {"id": "ord_012", "customer_id": "cus_008", "total": 4100, "items": ["perfume"], "channel": "online", "days_ago": 34},
]
