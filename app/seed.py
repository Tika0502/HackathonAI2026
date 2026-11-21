"""Reset the demo data. Run:  python -m app.seed

Deletes rota.db and creates:
- 1 manager (name "Manager", PIN 0000)
- 5 demo workers for real phones (PINs 1111 ... 5555)
- 45 fake workers (PIN 1234) who answer by themselves if "bots" is on
- THIS week already staffed: Morning + Evening, 15 people each, today + 6 days
  (Eva Horvath works today's evening shift: use her to "Report sick")
- NEXT week: the manager plans it in the app and sends it to the agent
- Past shift records for this month (so the report and fairness have data)
"""
import random
from datetime import date, timedelta

from . import db

# Real people use these logins in the demo (e.g. the judges).
# They have few hours this month, so the agent asks them first.
DEMO_WORKERS = [
    ("Anna Kovacs", "1111", 8),
    ("Bence Nagy", "2222", 16),
    ("Csilla Toth", "3333", 16),
    ("David Szabo", "4444", 24),
    ("Eva Horvath", "5555", 40),
]

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
    for name, pin, _ in DEMO_WORKERS:
        demo_ids[name] = db.execute("INSERT INTO workers(name, pin, is_demo) VALUES (?, ?, 1)", (name, pin))
    fake_ids = []
    for i, first in enumerate(FIRST):
        name = f"{first} {LAST[i % len(LAST)]}"
        fake_ids.append(db.execute("INSERT INTO workers(name, pin) VALUES (?, '1234')", (name,)))

    today = date.today()

    # THIS week (today + next 6 days) is already staffed, so the manager can
    # change numbers and workers can report sick right away. The NEXT week is
    # planned by the manager in the app.
    # Nobody works two shifts on the same day.
    for d in range(7):
        day = (today + timedelta(days=d)).isoformat()
        people = fake_ids[:]
        rng.shuffle(people)
        for idx, (name, start, end, needed) in enumerate(SHIFTS):
            shift_id = db.execute(
                "INSERT INTO shifts(date, name, start, end, needed) VALUES (?, ?, ?, ?, ?)",
                (day, name, start, end, needed),
            )
            team = people[idx * needed:(idx + 1) * needed]
            if d == 0 and name == "Evening":
                team = team[:-1] + [demo_ids["Eva Horvath"]]      # Eva reports sick in the demo
            if d == 1 and name == "Morning":
                team = team[:-4] + [demo_ids[n] for n, _, _ in DEMO_WORKERS[:4]]
            for wid in team:
                db.execute(
                    "INSERT INTO assignments(shift_id, worker_id, start, end) VALUES (?, ?, ?, ?)",
                    (shift_id, wid, start, end),
                )

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
    for name, _, hours in DEMO_WORKERS:
        for k in range(min(hours // 8, days_so_far)):
            day = (first_of_month + timedelta(days=k)).isoformat()
            db.execute(
                "INSERT INTO shift_records(worker_id, date, start, end, hours) VALUES (?, ?, '06:00', '14:00', 8)",
                (demo_ids[name], day),
            )
    print(f"Demo data ready: {1 + len(DEMO_WORKERS) + len(fake_ids)} logins, this week staffed "
          f"({today} + 6 days). Plan next week in the app.")


if __name__ == "__main__":
    seed()
