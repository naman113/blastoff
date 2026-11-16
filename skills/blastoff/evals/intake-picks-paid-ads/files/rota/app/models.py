from dataclasses import dataclass
@dataclass
class Clinic:            # tenant
    id: int; name: str
@dataclass
class Staff:
    id: int; clinic_id: int; name: str; phone: str; role: str   # "manager" | "staff"
@dataclass
class Shift:
    id: int; clinic_id: int; staff_id: int | None; start: str; end: str; role_needed: str
@dataclass
class SwapRequest:
    id: int; clinic_id: int; shift_id: int; from_staff: int; to_staff: int; status: str  # pending|approved|declined
