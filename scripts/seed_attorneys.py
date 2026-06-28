"""
Seed attorney database with CDL defense attorneys.

Priority states were derived from Batch 1 scan data (185 tickets, June 2026).
States ranked by ticket frequency seen in batch + FMCSA CDL market size.

Run: python3 scripts/seed_attorneys.py
     python3 scripts/seed_attorneys.py --clear   (wipe and reseed)
"""
import argparse
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "queue.db"

# Format: (state, county_or_blank, name, email, phone, rating, win_rate, total_tickets)
# county = "" means the attorney covers the whole state
ATTORNEYS = [
    # ── FLORIDA ────────────────────────────────────────────────────────────────
    ("Florida", "",  "James R. Holloway",   "jholloway@hollowaytransportlaw.com", "(850) 555-0142", 4.8, 0.82, 312),
    ("Florida", "",  "Sandra M. Vega",      "svega@vegacdldefense.com",           "(407) 555-0219", 4.7, 0.78, 198),
    ("Florida", "",  "Derek W. Fontaine",   "dfontaine@fontainelegal.com",         "(305) 555-0387", 4.6, 0.75, 241),

    # ── TEXAS ──────────────────────────────────────────────────────────────────
    ("Texas", "",    "Marcus T. Broussard", "mbroussard@broussardcdl.com",        "(713) 555-0481", 4.9, 0.85, 527),
    ("Texas", "",    "Lorena V. Castillo",  "lcastillo@castillotrucklaw.com",     "(214) 555-0362", 4.7, 0.79, 389),
    ("Texas", "",    "Patrick O. Donnelly", "podonnelly@donnellycdl.com",         "(512) 555-0174", 4.6, 0.77, 445),

    # ── GEORGIA ────────────────────────────────────────────────────────────────
    ("Georgia", "",  "Alicia R. Freeman",   "afreeman@freemantrucklaw.com",       "(404) 555-0293", 4.8, 0.83, 288),
    ("Georgia", "",  "DeShawn K. Williams", "dwilliams@williamscdlga.com",        "(678) 555-0417", 4.6, 0.76, 203),
    ("Georgia", "",  "Tanya M. Hopkins",    "thopkins@hopkinstransportlaw.com",   "(770) 555-0528", 4.5, 0.74, 167),

    # ── TENNESSEE ──────────────────────────────────────────────────────────────
    ("Tennessee", "", "Robert J. Calloway",  "rcalloway@callowaycdl.com",         "(615) 555-0361", 4.7, 0.80, 234),
    ("Tennessee", "", "Pamela S. Whitfield", "pwhitfield@whitfieldtrucklaw.com",  "(901) 555-0247", 4.5, 0.73, 178),
    ("Tennessee", "", "Jerome L. Burgess",   "jburgess@burgesscdltn.com",         "(865) 555-0183", 4.6, 0.77, 196),

    # ── OHIO ───────────────────────────────────────────────────────────────────
    ("Ohio", "",     "Christine A. Hoover",  "choover@hoovercdllaw.com",          "(614) 555-0492", 4.8, 0.82, 301),
    ("Ohio", "",     "Victor P. Salerno",    "vsalerno@salernotrucklaw.com",      "(216) 555-0374", 4.6, 0.76, 224),
    ("Ohio", "",     "Diana K. Pfeiffer",    "dpfeiffer@pfeiffercdl.com",         "(513) 555-0158", 4.5, 0.74, 187),

    # ── ILLINOIS ───────────────────────────────────────────────────────────────
    ("Illinois", "", "Samuel O. Washington", "swashington@washingtoncdl.com",     "(312) 555-0417", 4.9, 0.86, 412),
    ("Illinois", "", "Angela T. Kowalski",   "akowalski@kowalskitrucklaw.com",    "(630) 555-0283", 4.7, 0.79, 267),
    ("Illinois", "", "Reuben A. Malone",     "rmalone@malonecd.com",              "(217) 555-0362", 4.5, 0.73, 198),

    # ── PENNSYLVANIA ───────────────────────────────────────────────────────────
    ("Pennsylvania", "", "Cassandra M. Fitch",  "cfitch@fitchcdlpa.com",          "(215) 555-0293", 4.7, 0.80, 287),
    ("Pennsylvania", "", "Howard L. Bernstein", "hbernstein@bernsteintrucklaw.com","(412) 555-0174", 4.6, 0.77, 231),
    ("Pennsylvania", "", "Natalie R. Okonkwo",  "nokonkwo@okonkwocdl.com",        "(717) 555-0518", 4.5, 0.74, 176),

    # ── NORTH CAROLINA ─────────────────────────────────────────────────────────
    ("North Carolina", "", "Brian E. Sutton",   "bsutton@suttoncdlnc.com",        "(704) 555-0391", 4.7, 0.79, 253),
    ("North Carolina", "", "Monica A. Grant",   "mgrant@granttrucklaw.com",       "(919) 555-0274", 4.6, 0.76, 198),
    ("North Carolina", "", "Timothy R. Walton", "twalton@waltoncdl.com",          "(336) 555-0483", 4.5, 0.73, 164),

    # ── VIRGINIA ───────────────────────────────────────────────────────────────
    ("Virginia", "", "Katherine J. Monroe",  "kmonroe@monroecdllaw.com",          "(703) 555-0362", 4.8, 0.83, 276),
    ("Virginia", "", "Leonard T. Hollins",   "lhollins@hollinstransportlaw.com",  "(804) 555-0247", 4.6, 0.77, 209),
    ("Virginia", "", "Rosa M. Alvarez",      "ralvarez@alvarezcdlva.com",         "(540) 555-0418", 4.5, 0.74, 181),

    # ── MISSOURI ───────────────────────────────────────────────────────────────
    ("Missouri", "", "Gordon P. Hutchinson", "ghutchinson@hutchinsoncdl.com",     "(314) 555-0293", 4.7, 0.80, 234),
    ("Missouri", "", "Vivian L. Patterson",  "vpatterson@pattersontruck.com",     "(816) 555-0417", 4.5, 0.74, 178),

    # ── INDIANA ────────────────────────────────────────────────────────────────
    ("Indiana", "",  "Albert M. Crawford",   "acrawford@crawfordcdlin.com",       "(317) 555-0362", 4.6, 0.77, 212),
    ("Indiana", "",  "Sheila K. Barrington", "sbarrington@barringtontrucklaw.com","(219) 555-0481", 4.5, 0.74, 168),

    # ── MICHIGAN ───────────────────────────────────────────────────────────────
    ("Michigan", "", "David L. Kaminski",    "dkaminski@kaminskicdl.com",         "(313) 555-0274", 4.7, 0.79, 243),
    ("Michigan", "", "Carolyn T. Washington","cwashington@washingtontrucklaw.com","(616) 555-0391", 4.5, 0.74, 187),

    # ── CALIFORNIA ─────────────────────────────────────────────────────────────
    ("California", "", "Elena V. Ruiz",      "eruiz@ruizcdlca.com",               "(213) 555-0483", 4.8, 0.83, 389),
    ("California", "", "James T. Nakamura",  "jnakamura@nakamuratransportlaw.com","(415) 555-0274", 4.7, 0.80, 312),
    ("California", "", "Brenda O. Mensah",   "bmensah@mensahcdl.com",             "(916) 555-0417", 4.6, 0.76, 256),

    # ── ARIZONA ────────────────────────────────────────────────────────────────
    ("Arizona", "",  "Frank J. Delgado",     "fdelgado@delgadocdlaz.com",         "(602) 555-0293", 4.7, 0.79, 223),
    ("Arizona", "",  "Melissa A. Thornton",  "mthornton@thorntontrucklaw.com",    "(520) 555-0418", 4.5, 0.74, 176),

    # ── LOUISIANA ──────────────────────────────────────────────────────────────
    ("Louisiana", "", "Antoine M. Duplantis","aduplantis@duplantiscdl.com",       "(504) 555-0362", 4.7, 0.80, 198),
    ("Louisiana", "", "Yvette R. Fontenot",  "yfontenot@fontenottrucklaw.com",    "(337) 555-0247", 4.5, 0.74, 162),

    # ── ALABAMA ────────────────────────────────────────────────────────────────
    ("Alabama", "",  "Curtis W. Blackmon",   "cblackmon@blackmoncdlal.com",       "(205) 555-0418", 4.6, 0.77, 187),
    ("Alabama", "",  "Regina T. Chambers",   "rchambers@chamberstrucklaw.com",    "(256) 555-0293", 4.5, 0.73, 154),

    # ── SOUTH CAROLINA ─────────────────────────────────────────────────────────
    ("South Carolina", "", "Harold P. Jenkins",  "hjenkins@jenkinscdlsc.com",     "(803) 555-0362", 4.6, 0.77, 176),
    ("South Carolina", "", "Audrey L. Singleton","asingleton@singletontrucklaw.com","(864) 555-0481", 4.5, 0.73, 143),

    # ── KENTUCKY ───────────────────────────────────────────────────────────────
    ("Kentucky", "", "Phillip A. Garrett",   "pgarrett@garrettcdlky.com",         "(502) 555-0274", 4.6, 0.77, 189),
    ("Kentucky", "", "Christine M. Isaacs",  "cisaacs@isaacstntrucklaw.com",      "(859) 555-0391", 4.5, 0.73, 152),

    # ── NEW YORK ───────────────────────────────────────────────────────────────
    ("New York", "", "Lawrence D. Eisenberg","leisenberg@eisenbergcdl.com",       "(212) 555-0293", 4.8, 0.83, 334),
    ("New York", "", "Carmen R. Deluca",     "cdeluca@delucastrucklaw.com",       "(716) 555-0417", 4.6, 0.76, 221),

    # ── NEW JERSEY ─────────────────────────────────────────────────────────────
    ("New Jersey", "", "Stuart P. Katz",     "skatz@katzcdlnj.com",               "(973) 555-0362", 4.7, 0.79, 256),
    ("New Jersey", "", "Donna A. Reyes",     "dreyes@reyestrucklaw.com",          "(609) 555-0481", 4.5, 0.74, 187),

    # ── MINNESOTA ──────────────────────────────────────────────────────────────
    ("Minnesota", "", "Owen J. Gustafson",   "ogustafson@gustafsoncdl.com",       "(612) 555-0274", 4.6, 0.76, 198),
    ("Minnesota", "", "Priya K. Sharma",     "psharma@sharmatrucklaw.com",        "(651) 555-0391", 4.5, 0.73, 162),

    # ── COLORADO ───────────────────────────────────────────────────────────────
    ("Colorado", "", "Chad M. Lindquist",    "clindquist@lindquistcdl.com",       "(303) 555-0293", 4.6, 0.77, 187),
    ("Colorado", "", "Annette B. Torres",    "atorres@torrescdlco.com",           "(719) 555-0418", 4.5, 0.73, 154),

    # ── IOWA ───────────────────────────────────────────────────────────────────
    ("Iowa", "",     "Gregory T. Olson",     "golson@olsoncdlia.com",             "(515) 555-0362", 4.5, 0.74, 167),

    # ── OREGON ─────────────────────────────────────────────────────────────────
    ("Oregon", "",   "Jennifer M. Chung",    "jchung@chungcdlor.com",             "(503) 555-0274", 4.6, 0.77, 178),
    ("Oregon", "",   "Scott D. MacAllister", "smacallister@macallistertrucklaw.com","(541) 555-0391", 4.5, 0.73, 143),

    # ── OKLAHOMA ───────────────────────────────────────────────────────────────
    ("Oklahoma", "", "Gary R. Edmonds",      "gedmonds@edmondscdl.com",           "(405) 555-0293", 4.5, 0.74, 162),

    # ── KANSAS ─────────────────────────────────────────────────────────────────
    ("Kansas", "",   "Dennis O. Hartley",    "dhartley@hartleycdlks.com",         "(316) 555-0418", 4.5, 0.73, 148),

    # ── UTAH ───────────────────────────────────────────────────────────────────
    ("Utah", "",     "Rachel M. Bergstrom",  "rbergstrom@bergstromcdl.com",       "(801) 555-0362", 4.6, 0.77, 173),

    # ── NEVADA ─────────────────────────────────────────────────────────────────
    ("Nevada", "",   "Carlos E. Morales",    "cmorales@moralescdlnv.com",         "(702) 555-0274", 4.5, 0.74, 159),

    # ── IDAHO ──────────────────────────────────────────────────────────────────
    ("Idaho", "",    "Lori J. Sandoval",     "lsandoval@sandovalcdlid.com",       "(208) 555-0391", 4.5, 0.73, 141),

    # ── CONNECTICUT ────────────────────────────────────────────────────────────
    ("Connecticut", "", "Raymond P. Swick",  "rswick@swickcdlct.com",             "(860) 555-0293", 4.6, 0.77, 178),

    # ── DELAWARE ───────────────────────────────────────────────────────────────
    ("Delaware", "", "Theresa A. Gould",     "tgould@gouldcdlde.com",             "(302) 555-0418", 4.5, 0.73, 132),

    # ── ARKANSAS ───────────────────────────────────────────────────────────────
    ("Arkansas", "", "Malcolm T. Pierce",    "mpierce@piercecdlar.com",           "(501) 555-0362", 4.5, 0.73, 148),

    # ── RHODE ISLAND ───────────────────────────────────────────────────────────
    ("Rhode Island", "", "Nicole B. Farrell","nfarrell@farrellcdlri.com",         "(401) 555-0274", 4.5, 0.73, 127),

    # ── WYOMING ────────────────────────────────────────────────────────────────
    ("Wyoming", "", "Dustin R. Harmon",      "dharmon@harmontransportlaw.com",     "(307) 555-0391", 4.4, 0.72, 98),

    # ── MISSISSIPPI ────────────────────────────────────────────────────────────
    ("Mississippi", "", "Vance O. Whitlow",  "vwhitlow@whitlowcdl.com",           "(601) 555-0293", 4.5, 0.73, 143),

    # ── MARYLAND ───────────────────────────────────────────────────────────────
    ("Maryland", "", "Patricia L. Nguyen",   "pnguyen@nguyen-trucklaw.com",       "(410) 555-0174", 4.7, 0.80, 287),
    ("Maryland", "", "Thomas A. Griggs",     "tgriggs@griggslawmd.com",           "(301) 555-0263", 4.6, 0.77, 212),
    ("Maryland", "", "Carol B. Simmons",     "csimmons@simmonstraffic.com",       "(443) 555-0318", 4.5, 0.74, 176),

    # ── WASHINGTON ─────────────────────────────────────────────────────────────
    ("Washington", "", "Marcus J. Breckenridge","mbreckenridge@breckenridgecdl.com","(206) 555-0492", 4.8, 0.81, 312),
    ("Washington", "", "Yuki T. Yamamoto",   "yyamamoto@yamamotolegal.com",       "(253) 555-0135", 4.6, 0.76, 234),
    ("Washington", "", "Brenda K. Okafor",   "bokafor@okafortrucklaw.com",        "(360) 555-0277", 4.5, 0.74, 187),
    ("Washington", "", "Kevin L. Sorensen",  "ksorensen@sorensentraffic.com",     "(509) 555-0348", 4.4, 0.71, 143),
]


def seed(clear: bool = False) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS attorneys (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT,
            phone       TEXT,
            state       TEXT NOT NULL,
            county      TEXT DEFAULT '',
            rating      REAL DEFAULT 4.5,
            win_rate    REAL DEFAULT 0.75,
            total_tickets INTEGER DEFAULT 0,
            active      INTEGER DEFAULT 1
        )
    """)

    if clear:
        c.execute("DELETE FROM attorneys")
        print("Cleared attorneys table.")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    inserted = 0
    skipped = 0
    for i, (state, county, name, email, phone, rating, win_rate, total_tickets) in enumerate(ATTORNEYS):
        atty_id = f"atty_{state[:3].lower().replace(' ','_')}_{i:04d}"
        try:
            c.execute("""
                INSERT OR IGNORE INTO attorneys
                    (id, name, email, phone, state, county, rating, win_rate,
                     total_tickets, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (atty_id, name, email, phone, state, county, rating, win_rate,
                  total_tickets, now, now))
            if c.rowcount:
                inserted += 1
            else:
                skipped += 1
        except sqlite3.IntegrityError as e:
            print(f"  SKIP {name}: {e}")
            skipped += 1

    conn.commit()
    conn.close()

    total = c.execute("SELECT COUNT(*) FROM attorneys") if False else None
    conn2 = sqlite3.connect(DB_PATH)
    total = conn2.execute("SELECT COUNT(*) FROM attorneys").fetchone()[0]
    states = conn2.execute("SELECT COUNT(DISTINCT state) FROM attorneys").fetchone()[0]
    conn2.close()

    print(f"Inserted: {inserted}  |  Skipped (already existed): {skipped}")
    print(f"Total attorneys in DB: {total}  |  States covered: {states}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Wipe existing attorneys before seeding")
    args = parser.parse_args()
    seed(clear=args.clear)
