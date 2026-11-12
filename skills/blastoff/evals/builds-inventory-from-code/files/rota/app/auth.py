import hashlib
ROLES = {"manager": {"shifts:write", "swaps:approve", "export:read"}, "staff": {"shifts:read", "swaps:request"}}
def login(email, password, users):
    u = users.get(email)
    return u if u and u["pw"] == hashlib.sha256(password.encode()).hexdigest() else None
def allowed(user, perm): return perm in ROLES[user["role"]]
