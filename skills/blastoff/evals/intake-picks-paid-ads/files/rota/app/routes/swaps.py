from app.auth import allowed
def request_swap(db, user, shift_id, to_staff):
    """POST /shifts/{id}/swap"""
    if not allowed(user, "swaps:request"): raise PermissionError
    return db.insert_swap(shift_id, user["id"], to_staff, "pending")
def decide(db, user, swap_id, approve: bool):
    """POST /swaps/{id}/decide - manager approves; shift is reassigned on approval."""
    if not allowed(user, "swaps:approve"): raise PermissionError
    swap = db.swap(swap_id)
    if approve: db.set_staff(swap.shift_id, swap.to_staff)
    return db.set_swap_status(swap_id, "approved" if approve else "declined")
