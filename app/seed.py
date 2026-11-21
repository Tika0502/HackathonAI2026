"""Reset the demo data. Run:  python -m app.seed

Deletes rota.db and creates:
- 1 manager (name "Manager", PIN 0000)
- 5 demo workers for real phones (PINs 1111 ... 5555)
- 45 fake workers (PIN 1234) who answer by themselves if "bots" is on
- Every worker has a role (Cashier or Stock)
- NO future shifts: the manager creates the 7-day plan in the app and sends it
  to the agent, which then invites workers
- Past shift records for this month (so the report and fairness have data)
"""
import random
from datetime import date, timedelta

from . import db

# Real people use these logins in the demo (e.g. the judges).
# They have few hours this month, so the agent asks them first.
DEMO_WORKERS = [
    ("Anna Kovacs", "1111", 8, "Cashier"),
    ("Bence Nagy", "2222", 16, "Cashier"),
    ("Csilla Toth", "3333", 16, "Cashier"),
    ("David Szabo", "4444", 24, "Stock"),
    ("Eva Horvath", "5555", 40, "Cashier"),
]
ROLES = ["Cashier", "Cashier", "Cashier", "Stock", "Stock"]   # fake workers: 60% Cashier, 40% Stock

FIRST = ["Adam", "Agnes", "Andras", "Balazs", "Boglarka", "Daniel", "Dora", "Eszter", "Fanni", "Ferenc",
         "Gabor", "Gergo", "Hanna", "Istvan", "Janos", "Judit", "Kata", "Krisztian", "Laszlo", "Lili",
         "Marton", "Marcell", "Nora", "Orsolya", "Peter", "Petra", "Reka", "Robert", "Sara", "Tamas",
         "Viktor", "Zita", "Zoltan", "Akos", "Bianka", "Csaba", "Emese", "Gyula", "Ildiko", "Kristof",
         "Levente", "Mate", "Noemi", "Richard", "Timea"]
LAST = ["Kiss", "Molnar", "Nemeth", "Farkas", "Balogh", "Papp", "Lakatos", "Takacs", "Juhasz", "Meszaros",
        "Olah", "Simon", "Racz", "Fekete", "Szilagyi"]

SHIFTS = [("Morning", "06:00", "14:00", 15), ("Evening", "14:00", "22:00", 15)]


def seed():
    rng = random.Random(42)
    # Drop the tables instead of deleting rota.db: on Windows the running server
    # keeps the file open, so deleting it would fail (and break "Reset demo data").
    with db.connect() as conn:
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
            if not name.startswith("sqlite_"):
                conn.execute(f'DROP TABLE "{name}"')
    db.init_db()

    db.execute("INSERT INTO workers(name, pin, is_manager) VALUES ('Manager', '0000', 1)")
    demo_ids = {}
    for name, pin, _, role in DEMO_WORKERS:
        demo_ids[name] = db.execute("INSERT INTO workers(name, pin, role, is_demo) VALUES (?, ?, ?, 1)",
                                    (name, pin, role))
    fake_ids = []
    for i, first in enumerate(FIRST):
        name = f"{first} {LAST[i % len(LAST)]}"
        fake_ids.append(db.execute("INSERT INTO workers(name, pin, role) VALUES (?, '1234', ?)",
                                   (name, ROLES[i % len(ROLES)])))

    today = date.today()

    # Past shift records for this month (1st .. yesterday) so the report has data.
    first_of_month = today.replace(day=1)
    days_so_far = (today - first_of_month).days
    for wid in fake_ids:
        for d in range(days_so_far):
            if rng.random() < 0.6:
                day = (first_of_month + timedelta(days=d)).isoformat()
                sick = rng.random() < 0.04
                name, start, end, _ = rng.choice(SHIFTS)
                db.execute(
                    "INSERT INTO shift_records(worker_id, date, start, end, hours, is_sick) VALUES (?, ?, ?, ?, ?, ?)",
                    (wid, day, start, end, 0 if sick else 8, int(sick)),
                )
    for name, _, hours, _ in DEMO_WORKERS:
        for k in range(min(hours // 8, days_so_far)):
            day = (first_of_month + timedelta(days=k)).isoformat()
            db.execute(
                "INSERT INTO shift_records(worker_id, date, start, end, hours) VALUES (?, ?, '06:00', '14:00', 8)",
                (demo_ids[name], day),
            )
    print(f"Demo data ready: {1 + len(DEMO_WORKERS) + len(fake_ids)} logins. No shifts yet: "
          f"the manager creates the 7-day plan in the app.")


if __name__ == "__main__":
    seed()
