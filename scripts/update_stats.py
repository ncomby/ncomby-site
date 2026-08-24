#!/usr/bin/env python3
"""Régénère stats.json depuis l'API Strava — fenêtre glissante de 28 jours.

Conçu pour tourner chaque nuit dans GitHub Actions (voir
.github/workflows/stats.yml), mais fonctionne aussi en local :

    STRAVA_CLIENT_ID=… STRAVA_CLIENT_SECRET=… STRAVA_REFRESH_TOKEN=… \
        python3 scripts/update_stats.py

La "note" (contexte : examens, récup…) n'est JAMAIS touchée par ce script :
elle est relue depuis le stats.json existant. Pour la changer, édite
stats.json à la main (ou via l'interface web GitHub).
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

STATS_PATH = Path(__file__).resolve().parent.parent / "stats.json"
NOTE_DEFAUT = {"fr": "", "en": ""}


def api(url, data=None, token=None):
    req = urllib.request.Request(url)
    if data is not None:
        req.data = urllib.parse.urlencode(data).encode()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def access_token():
    return api(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": os.environ["STRAVA_CLIENT_ID"],
            "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
            "refresh_token": os.environ["STRAVA_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
    )["access_token"]


def main():
    # Fenêtre : les 28 jours pleins se terminant hier (UTC).
    fin = date.today() - timedelta(days=1)
    debut = fin - timedelta(days=27)
    after = int(time.mktime(datetime(debut.year, debut.month, debut.day).timetuple()))
    before = int(time.mktime(datetime(fin.year, fin.month, fin.day, 23, 59, 59).timetuple()))

    token = access_token()
    km = {"Swim": 0.0, "Bike": 0.0, "Run": 0.0}
    secondes = 0
    page = 1
    while True:
        acts = api(
            "https://www.strava.com/api/v3/athlete/activities?"
            + urllib.parse.urlencode({"after": after, "before": before, "per_page": 200, "page": page}),
            token=token,
        )
        if not acts:
            break
        for a in acts:
            t = a.get("sport_type") or a.get("type")
            if t in ("Ride", "VirtualRide", "GravelRide", "MountainBikeRide"):
                cle = "Bike"
            elif t == "Swim":
                cle = "Swim"
            elif t in ("Run", "TrailRun", "VirtualRun"):
                cle = "Run"
            else:
                continue  # voile, muscu… hors stats triathlon
            km[cle] += a.get("distance", 0) / 1000
            secondes += a.get("moving_time", 0)
        page += 1

    note = NOTE_DEFAUT
    if STATS_PATH.exists():
        try:
            note = json.loads(STATS_PATH.read_text(encoding="utf-8")).get("note", NOTE_DEFAUT)
        except Exception:
            pass

    stats = {
        "debut": debut.isoformat(),
        "fin": fin.isoformat(),
        "maj": date.today().isoformat(),
        "heures": round(secondes / 3600),
        "natation": round(km["Swim"]),
        "velo": round(km["Bike"]),
        "course": round(km["Run"]),
        "note": note,
    }
    STATS_PATH.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("stats.json mis à jour :", json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
