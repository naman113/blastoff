OPEN_SHIFT_BIDDING = False   # staff can claim unfilled shifts; built, off by default
def claim_open_shift(db, user, shift_id):
    if not OPEN_SHIFT_BIDDING: raise RuntimeError("disabled")
    return db.set_staff(shift_id, user["id"])
