from app.auth import allowed
def create_week(db, user, clinic_id, template):
    """POST /clinics/{id}/weeks - copy a template week into real shifts."""
    if not allowed(user, "shifts:write"): raise PermissionError
    made = [db.insert_shift(clinic_id, **slot) for slot in template]
    return made
def assign(db, user, shift_id, staff_id):
    """PUT /shifts/{id}/assign - refuses overlapping shifts for the same person."""
    if not allowed(user, "shifts:write"): raise PermissionError
    shift = db.shift(shift_id)
    if any(o.start < shift.end and shift.start < o.end for o in db.shifts_for(staff_id)):
        raise ValueError("overlap")
    return db.set_staff(shift_id, staff_id)
def my_week(db, user):
    """GET /me/week"""
    return db.shifts_for(user["id"])
