indexes = [
    ("idx_sells_date_vendor_id", "sells", "date, vendor_id"),
    ("idx_sells_date", "sells", "date"),
    ("idx_sells_vendor_id", "sells", "vendor_id"),
    ("idx_sells_item_id", "sells", "item_id"),

    ("idx_details_sell_id", "details", "sell_id"),
    ("idx_details_item_id", "details", "item_id"),

    ("idx_items_name", "items", "name"),
    ("idx_items_status_name", "items", "status, name"),

    ("idx_notifications_user_read", "notifications", "user_id, is_read"),
    ("idx_notifications_created", "notifications", "created_at DESC"),

    ("idx_audit_user_id", "audit_log", "user_id"),
    ("idx_audit_entity", "audit_log", "entity_type, entity_id"),
    ("idx_audit_timestamp", "audit_log", "timestamp DESC"),

    ("idx_customers_name", "customers", "name"),
    ("idx_movements_customer_date", "account_movements", "customer_id, date"),
    ("idx_movements_sell_id", "account_movements", "sell_id"),
    
    ("idx_weight_items_name", "weight_items", "name"),
    ("idx_weight_items_status", "weight_items", "status"),
    ("idx_weight_details_sell_id", "weight_details", "sell_id"),
    ("idx_weight_details_weight_item_id", "weight_details", "weight_item_id"),

]