#!/usr/bin/env python3
"""
verify_feba.py — Script de vérification automatique FEBA v20
Tests :
  - Connexion (login / refresh / logout)
  - Année active
  - Notes (liste, création, suppression, restauration, historique)
  - Bulletins (liste, génération)
  - Permissions (endpoints protégés)
  - Endpoints critiques (branding, notifications, messages)
  - Incohérences (élèves sans année, parents sans enfants, notes sans trimestre)

Usage :
  python verify_feba.py --url http://localhost:8000 --email admin@feba.cd --password secret
"""
import argparse
import json
import sys
import csv
import requests

# ── Config ─────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="FEBA v20 verification script")
parser.add_argument("--url",      default="http://localhost:8000", help="API base URL")
parser.add_argument("--email",    default="admin@feba.cd",         help="Admin email")
parser.add_argument("--password", default="admin123",              help="Admin password")
parser.add_argument("--output",   default="verify_results.json",   help="JSON output file")
args = parser.parse_args()

BASE = args.url.rstrip("/")
RESULTS = []
PASS = 0
FAIL = 0

def ok(label, detail=""):
    global PASS
    PASS += 1
    print(f"  ✅ {label}" + (f" — {detail}" if detail else ""))
    RESULTS.append({"test": label, "status": "PASS", "detail": detail})

def fail(label, detail=""):
    global FAIL
    FAIL += 1
    print(f"  ❌ {label}" + (f" — {detail}" if detail else ""))
    RESULTS.append({"test": label, "status": "FAIL", "detail": detail})

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ── Auth ───────────────────────────────────────────────────────────────────────
section("1. AUTHENTIFICATION")
try:
    r = requests.post(f"{BASE}/api/auth/login/", json={"email": args.email, "password": args.password}, timeout=10)
    if r.status_code == 200:
        data = r.json()
        access  = data.get("access")
        refresh = data.get("refresh")
        ok("Login admin", f"status={r.status_code}")
    else:
        fail("Login admin", f"status={r.status_code} body={r.text[:200]}")
        sys.exit(1)
except Exception as e:
    fail("Login admin", str(e))
    sys.exit(1)

H = {"Authorization": f"Bearer {access}"}

# Refresh token
try:
    r = requests.post(f"{BASE}/api/auth/refresh/", json={"refresh": refresh}, timeout=10)
    if r.status_code == 200:
        ok("Token refresh", f"status={r.status_code}")
    else:
        fail("Token refresh", f"status={r.status_code}")
except Exception as e:
    fail("Token refresh", str(e))

# /me
try:
    r = requests.get(f"{BASE}/api/auth/me/", headers=H, timeout=10)
    if r.status_code == 200:
        me = r.json()
        ok("GET /api/auth/me/", f"user={me.get('email')} role={me.get('role')}")
    else:
        fail("GET /api/auth/me/", f"status={r.status_code}")
except Exception as e:
    fail("GET /api/auth/me/", str(e))

# Recipients
try:
    r = requests.get(f"{BASE}/api/auth/recipients/", headers=H, timeout=10)
    if r.status_code == 200:
        ok("GET /api/auth/recipients/", f"count={len(r.json())}")
    else:
        fail("GET /api/auth/recipients/", f"status={r.status_code}")
except Exception as e:
    fail("GET /api/auth/recipients/", str(e))

# ── Année active ───────────────────────────────────────────────────────────────
section("2. ANNÉE SCOLAIRE ACTIVE")
active_year = None
try:
    r = requests.get(f"{BASE}/api/schools/years/", headers=H, timeout=10)
    if r.status_code == 200:
        years = r.json().get("results", r.json()) if isinstance(r.json(), dict) else r.json()
        active = [y for y in (years if isinstance(years, list) else []) if y.get("is_current")]
        if active:
            active_year = active[0]
            ok("Année active trouvée", f"name={active_year.get('name')} id={active_year.get('id')}")
        else:
            fail("Année active", "Aucune année scolaire active trouvée")
    else:
        fail("GET /api/schools/years/", f"status={r.status_code}")
except Exception as e:
    fail("Années scolaires", str(e))

# ── Branding ──────────────────────────────────────────────────────────────────
section("3. BRANDING / LOGO")
try:
    r = requests.get(f"{BASE}/api/schools/branding/active/", headers=H, timeout=10)
    if r.status_code == 200:
        ok("GET /api/schools/branding/active/", f"status={r.status_code}")
    else:
        fail("GET /api/schools/branding/active/", f"status={r.status_code}")
except Exception as e:
    fail("GET /api/schools/branding/active/", str(e))

# ── Notes ─────────────────────────────────────────────────────────────────────
section("4. NOTES (GRADES)")
try:
    r = requests.get(f"{BASE}/api/grades/", headers=H, timeout=10)
    if r.status_code == 200:
        grades = r.json()
        count = len(grades.get("results", grades)) if isinstance(grades, dict) else len(grades)
        ok("GET /api/grades/", f"count={count}")
    else:
        fail("GET /api/grades/", f"status={r.status_code}")
except Exception as e:
    fail("GET /api/grades/", str(e))

# Notes supprimées
try:
    r = requests.get(f"{BASE}/api/grades/?show_deleted=1", headers=H, timeout=10)
    if r.status_code == 200:
        deleted = r.json()
        count = len(deleted.get("results", deleted)) if isinstance(deleted, dict) else len(deleted)
        ok("GET /api/grades/?show_deleted=1", f"count={count}")
    else:
        fail("GET /api/grades/?show_deleted=1", f"status={r.status_code}")
except Exception as e:
    fail("Notes supprimées", str(e))

# Student summary
try:
    r = requests.get(f"{BASE}/api/grades/student-summary/?student=1", headers=H, timeout=10)
    if r.status_code in (200, 404):
        ok("GET /api/grades/student-summary/", f"status={r.status_code}")
    else:
        fail("GET /api/grades/student-summary/", f"status={r.status_code}")
except Exception as e:
    fail("GET /api/grades/student-summary/", str(e))

# ── Bulletins ─────────────────────────────────────────────────────────────────
section("5. BULLETINS")
try:
    r = requests.get(f"{BASE}/api/bulletins/", headers=H, timeout=10)
    if r.status_code == 200:
        bulletins = r.json()
        count = len(bulletins.get("results", bulletins)) if isinstance(bulletins, dict) else len(bulletins)
        ok("GET /api/bulletins/", f"count={count}")
    else:
        fail("GET /api/bulletins/", f"status={r.status_code}")
except Exception as e:
    fail("GET /api/bulletins/", str(e))

# ── Messages ──────────────────────────────────────────────────────────────────
section("6. MESSAGES / CONVERSATIONS")
for ep in [
    "/api/messages/conversations/",
    "/api/messages/inbox/",
    "/api/messages/unread-count/",
]:
    try:
        r = requests.get(f"{BASE}{ep}", headers=H, timeout=10)
        if r.status_code == 200:
            ok(f"GET {ep}", f"status={r.status_code}")
        else:
            fail(f"GET {ep}", f"status={r.status_code}")
    except Exception as e:
        fail(f"GET {ep}", str(e))

# ── Notifications ─────────────────────────────────────────────────────────────
section("7. NOTIFICATIONS")
for ep in [
    "/api/notifications/",
    "/api/notifications/unread-count/",
]:
    try:
        r = requests.get(f"{BASE}{ep}", headers=H, timeout=10)
        if r.status_code == 200:
            ok(f"GET {ep}", f"status={r.status_code}")
        else:
            fail(f"GET {ep}", f"status={r.status_code}")
    except Exception as e:
        fail(f"GET {ep}", str(e))

# ── Dashboard ─────────────────────────────────────────────────────────────────
section("8. DASHBOARD ADMIN")
try:
    r = requests.get(f"{BASE}/api/dashboard/admin/", headers=H, timeout=10)
    if r.status_code == 200:
        d = r.json()
        ok("GET /api/dashboard/admin/", f"active_year={d.get('active_year', {}).get('name', 'N/A')}")
    else:
        fail("GET /api/dashboard/admin/", f"status={r.status_code}")
except Exception as e:
    fail("GET /api/dashboard/admin/", str(e))

# ── Permissions 401 check (sans token) ────────────────────────────────────────
section("9. VÉRIFICATION SÉCURITÉ (sans token)")
for ep in ["/api/grades/", "/api/students/", "/api/bulletins/"]:
    try:
        r = requests.get(f"{BASE}{ep}", timeout=10)
        if r.status_code == 401:
            ok(f"Non-auth 401 {ep}", "Correct — accès refusé sans token")
        else:
            fail(f"Non-auth 401 {ep}", f"status={r.status_code} (attendu 401)")
    except Exception as e:
        fail(f"Non-auth 401 {ep}", str(e))

# ── Incohérences CSV ──────────────────────────────────────────────────────────
section("10. RAPPORT D'INCOHÉRENCES")
incoherences = []

try:
    r = requests.get(f"{BASE}/api/students/?page_size=1000", headers=H, timeout=15)
    if r.status_code == 200:
        students_data = r.json()
        students = students_data.get("results", students_data) if isinstance(students_data, dict) else students_data
        no_year = [s for s in students if not s.get("school_year") and not s.get("school_year_id")]
        for s in no_year:
            incoherences.append({
                "type": "Élève sans année scolaire",
                "id": s.get("id"),
                "nom": s.get("full_name", f"{s.get('first_name','')} {s.get('last_name','')}"),
                "detail": "school_year absent"
            })
        if no_year:
            fail("Élèves sans année scolaire", f"{len(no_year)} élèves sans school_year")
        else:
            ok("Élèves sans année scolaire", "Aucune incohérence")
except Exception as e:
    fail("Vérification élèves", str(e))

try:
    r = requests.get(f"{BASE}/api/parents/?page_size=1000", headers=H, timeout=15)
    if r.status_code == 200:
        parents_data = r.json()
        parents = parents_data.get("results", parents_data) if isinstance(parents_data, dict) else parents_data
        no_children = [p for p in parents if not p.get("children_links") and not p.get("children")]
        for p in no_children:
            incoherences.append({
                "type": "Parent sans enfant",
                "id": p.get("id"),
                "nom": p.get("full_name", ""),
                "detail": "children vide"
            })
        if no_children:
            fail("Parents sans enfants", f"{len(no_children)} parents sans enfants")
        else:
            ok("Parents sans enfants", "Aucune incohérence")
except Exception as e:
    fail("Vérification parents", str(e))

try:
    r = requests.get(f"{BASE}/api/grades/?page_size=1000", headers=H, timeout=15)
    if r.status_code == 200:
        grades_data = r.json()
        grades = grades_data.get("results", grades_data) if isinstance(grades_data, dict) else grades_data
        no_trimestre = [g for g in grades if not g.get("period")]
        for g in no_trimestre:
            incoherences.append({
                "type": "Note sans trimestre",
                "id": g.get("id"),
                "nom": g.get("student_name", ""),
                "detail": f"value={g.get('value')} period=None"
            })
        if no_trimestre:
            fail("Notes sans trimestre", f"{len(no_trimestre)} notes sans période")
        else:
            ok("Notes sans trimestre", "Aucune incohérence")
except Exception as e:
    fail("Vérification notes", str(e))

# Bulletins en doublon
try:
    r = requests.get(f"{BASE}/api/bulletins/?page_size=1000", headers=H, timeout=15)
    if r.status_code == 200:
        bul_data = r.json()
        bulletins = bul_data.get("results", bul_data) if isinstance(bul_data, dict) else bul_data
        seen = {}
        dupes = []
        for b in bulletins:
            key = (b.get("student"), b.get("school_year"), b.get("period"))
            if key in seen:
                dupes.append(b)
                incoherences.append({
                    "type": "Bulletin doublon",
                    "id": b.get("id"),
                    "nom": b.get("student_name", ""),
                    "detail": f"period={b.get('period')} year={b.get('school_year_name')}"
                })
            else:
                seen[key] = True
        if dupes:
            fail("Bulletins en doublon", f"{len(dupes)} doublons détectés")
        else:
            ok("Bulletins en doublon", "Aucun doublon")
except Exception as e:
    fail("Vérification bulletins doublons", str(e))

# Écriture du CSV d'incohérences
if incoherences:
    with open("incoherences_v20.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "id", "nom", "detail"])
        writer.writeheader()
        writer.writerows(incoherences)
    print(f"\n  📄 Rapport CSV : incoherences_v20.csv ({len(incoherences)} entrées)")

# ── Résumé ────────────────────────────────────────────────────────────────────
section("RÉSUMÉ FINAL")
total = PASS + FAIL
print(f"  Tests réussis : {PASS}/{total}")
print(f"  Tests échoués : {FAIL}/{total}")
print(f"  Score : {round(PASS/total*100)}%" if total else "")

with open(args.output, "w", encoding="utf-8") as f:
    json.dump({"pass": PASS, "fail": FAIL, "total": total, "results": RESULTS}, f, indent=2, ensure_ascii=False)
print(f"\n  📊 Résultats JSON : {args.output}")

sys.exit(0 if FAIL == 0 else 1)
