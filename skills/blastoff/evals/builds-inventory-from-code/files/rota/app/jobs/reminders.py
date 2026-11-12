import os
from twilio.rest import Client
def send_tomorrow(db):
    """Runs daily at 17:00. Texts each person their shift for tomorrow."""
    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    for shift in db.shifts_tomorrow():
        if shift.staff_id:
            s = db.staff(shift.staff_id)
            client.messages.create(to=s.phone, from_=os.environ["TWILIO_FROM"], body=f"Rota: you work {shift.start}-{shift.end} tomorrow.")
