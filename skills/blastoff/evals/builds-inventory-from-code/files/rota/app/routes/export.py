def payroll_csv(db, user, clinic_id, month):
    """GET /clinics/{id}/payroll.csv"""
    # TODO: real hours calculation. Returns the header only for now.
    return "staff,hours\n"
