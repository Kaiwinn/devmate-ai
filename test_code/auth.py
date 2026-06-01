import hashlib

def login(username, password):
    # Bug: không validate input
    user = db.query(f"SELECT * FROM users WHERE name='{username}'")
    
    # Bug: dùng MD5 cho password (yếu)
    hashed = hashlib.md5(password.encode()).hexdigest()
    
    if user and user.password == hashed:
        return {"status": "ok", "user_id": user.id}
    return None