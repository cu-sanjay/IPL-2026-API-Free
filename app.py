import os
import re
import logging
from datetime import datetime, timezone

import httpx
from flask import Flask, jsonify, render_template
from selectolax.parser import HTMLParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.json.sort_keys = False

SEASON = "2026"
CRICBUZZ_SERIES_ID = "9241"
CREX_SERIES_SLUG = "indian-premier-league-2026-1PW"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
HTTP_TIMEOUT = 15.0


def today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def safe_text(node, default: str = "") -> str:
    """Return stripped text from a selectolax node or default if node is None."""
    if node is None:
        return default
    try:
        return node.text(strip=True) or default
    except Exception:
        return default


def http_get(url: str, headers: dict | None = None) -> httpx.Response:
    merged = {**HEADERS, **(headers or {})}
    with httpx.Client(timeout=HTTP_TIMEOUT, headers=merged, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp


def error_payload(title: str, message: str, resolution: str, code: int = 500) -> tuple:
    return (
        jsonify({
            "status_code": code,
            "title": title,
            "message": message,
            "resolution": resolution,
        }),
        code,
    )


@app.route("/")
def home():
    return render_template("home.html", season=SEASON)


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------
@app.route(f"/ipl-{SEASON}-schedule")
@app.route("/ipl-schedule")
def ipl_schedule():
    url = "https://www.sportskeeda.com/go/ipl/schedule"
    try:
        response = http_get(url)
        tree = HTMLParser(response.text)
        match_cards = tree.css("div.cricket-match-card-container")

        if not match_cards:
            return error_payload(
                "No Schedule Data",
                "No match cards were found on the source page.",
                "The source site structure may have changed; try again later.",
            )

        schedule = {}
        for i, card in enumerate(match_cards, 1):
            teams = [
                safe_text(t.css_first("div.cricket-match-card-team-name"))
                for t in card.css("div.cricket-match-card-team-info")
            ]
            teams = [t for t in teams if t]

            venue_node = card.css_first("header.cricket-match-card-header")
            venue = ""
            if venue_node:
                venue = " ".join(
                    safe_text(span)
                    for span in venue_node.css("span.cricket-match-card--match-venue")
                ).strip()

            date = safe_text(card.css_first("div.cricket-match-card-timer--date"), "TBD")
            time_ = safe_text(card.css_first("div.cricket-match-card-timer--time"), "TBD")

            schedule[f"Match {i}"] = {
                "Rival": f"{teams[0]} vs {teams[1]}" if len(teams) >= 2 else "TBD",
                "Location": venue or "Unknown",
                "Date": date,
                "Time": time_,
            }

        return jsonify({"status_code": 200, "season": SEASON, "schedule": schedule})

    except httpx.HTTPError as e:
        logger.error("Schedule network error: %s", e)
        return error_payload(
            "Network Error",
            f"Failed to fetch schedule: {e}",
            "Try again later or check the source site.",
        )
    except Exception as e:
        logger.exception("Schedule parse error")
        return error_payload(
            "Parsing Error",
            f"Failed to parse schedule: {e}",
            "The source site structure may have changed.",
        )


# ---------------------------------------------------------------------------
# Points table
# ---------------------------------------------------------------------------
@app.route(f"/ipl-{SEASON}-points-table")
@app.route("/ipl-points-table")
def ipl_points_table():
    url = "https://cf-gotham.sportskeeda.com/cricket/ipl/points-table"
    try:
        response = http_get(url)
        data = response.json()

        try:
            teams = data["table"][0]["table"][0]["group"]
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f"Unexpected API response structure: {e}")

        if not teams:
            return error_payload(
                "No Points Data",
                "API returned an empty team list.",
                "The season may not have begun yet.",
            )

        points_table = {}
        for i, team in enumerate(teams, 1):
            try:
                points_table[f"Team {i}"] = {
                    "Name": team.get("team_name", "Unknown"),
                    "Played": int(team.get("played", 0) or 0),
                    "Won": int(team.get("won", 0) or 0),
                    "Loss": int(team.get("lost", 0) or 0),
                    "No Result": int(team.get("no_result", 0) or 0),
                    "Net Run Rate": float(team.get("nrr", 0) or 0),
                    "Points": int(team.get("points", 0) or 0),
                }
            except (TypeError, ValueError) as e:
                logger.warning("Skipping malformed team row: %s (%s)", team, e)
                continue

        return jsonify({"status_code": 200, "season": SEASON, "points_table": points_table})

    except httpx.HTTPError as e:
        logger.error("Points-table network error: %s", e)
        return error_payload(
            "Network Error",
            f"Failed to fetch points table: {e}",
            "Try again later.",
        )
    except (ValueError, KeyError) as e:
        logger.error("Points-table parse error: %s", e)
        return error_payload(
            "Parsing Error",
            f"Failed to parse points-table response: {e}",
            "The upstream API structure may have changed.",
        )


# ---------------------------------------------------------------------------
# Live score (Sportskeeda) — parses scores inline from the carousel page
# ---------------------------------------------------------------------------
def _sportskeeda_match(card) -> dict | None:
    """Extract a match dict from a .keeda_cricket_match_list node."""
    status = (card.attributes.get("data-match-status") or "").lower()
    match_time = card.attributes.get("data-match-time") or ""
    description = card.attributes.get("data-match-description") or ""

    match_type = safe_text(card.css_first("span.cricket-match-card--match-type"))
    venue = safe_text(card.css_first("span.cricket-match-card--match-venue"))
    date = safe_text(card.css_first("span.cricket-match-card--match-date"))

    teams = []
    for t in card.css("div.keeda_widget_team"):
        name_node = t.css_first("span.keeda_widget_team_name")
        score_node = t.css_first("span.keeda_widget_score")
        if name_node is None and score_node is None:
            continue
        teams.append({
            "name": safe_text(name_node, "TBD"),
            "score": safe_text(score_node, ""),
        })

    if len(teams) < 2:
        return None

    result_node = card.css_first("div.marquee-strip")
    result = ""
    if result_node is not None:
        try:
            result = result_node.text(deep=True, separator=" ", strip=True)
            result = re.sub(r"\s+", " ", result).strip()
        except Exception:
            result = safe_text(result_node)
    status_label = {"live": "Live", "post": "Completed", "pre": "Upcoming"}.get(status, status or "Unknown")

    entry = {
        "status": status_label,
        "description": description or match_type or "Match",
        "type": match_type,
        "venue": venue or "Unknown",
        "date": date or "TBD",
        "start_time_utc": match_time,
        "team_1": teams[0]["name"],
        "score_1": teams[0]["score"] or "N.A",
        "team_2": teams[1]["name"],
        "score_2": teams[1]["score"] or "N.A",
    }
    if result:
        entry["result"] = result
    return entry


@app.route(f"/ipl-{SEASON}-live-score")
@app.route("/ipl-live-score")
def ipl_live_score():
    base_url = "https://www.sportskeeda.com"
    main_url = f"{base_url}/go/ipl?ref=carousel"

    try:
        response = http_get(main_url)
        tree = HTMLParser(response.text)
        cards = tree.css("div.keeda_cricket_match_list")

        # Pre-season countdown only matters when there are no match cards at all.
        if not cards:
            countdown = tree.css_first("div.hero-countdown-timer")
            if countdown:
                target_attr = countdown.attributes.get("data-target", "0") or "0"
                try:
                    target_epoch = int(target_attr) / 1000
                    start_date = datetime.fromtimestamp(target_epoch, tz=timezone.utc).strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    )
                except (ValueError, TypeError):
                    start_date = "Unknown"
                return jsonify({
                    "status_code": 200,
                    "status": "Pre-Season",
                    "message": f"IPL {SEASON} has not started yet.",
                    "season_start": start_date,
                    "date_checked": today_iso(),
                })
            return jsonify({
                "status_code": 200,
                "status": "No Data",
                "message": "No matches listed yet.",
                "date_checked": today_iso(),
            })

        matches = {}
        live_matches = {}
        for i, card in enumerate(cards, 1):
            entry = _sportskeeda_match(card)
            if entry is None:
                continue
            matches[f"Match {i}"] = entry
            if entry["status"] == "Live":
                live_matches[f"Match {i}"] = entry

        if not matches:
            return jsonify({
                "status_code": 200,
                "status": "No Data",
                "message": "Found match cards but could not extract any data.",
                "date_checked": today_iso(),
            })

        return jsonify({
            "status_code": 200,
            "season": SEASON,
            "source": "sportskeeda",
            "status": "Live" if live_matches else "No Live Matches",
            "live_count": len(live_matches),
            "live_score": live_matches,
            "matches": matches,
            "date_checked": today_iso(),
        })

    except httpx.HTTPError as e:
        logger.error("Live-score network error: %s", e)
        return error_payload("Network Error", f"Failed to fetch data: {e}", "Try again later.")
    except Exception as e:
        logger.exception("Live-score unexpected error")
        return error_payload("Server Error", f"Unexpected error: {e}", "Contact support.")


# ---------------------------------------------------------------------------
# Live score (Crex) — uses crex.com series page, parses Angular SSR markup
# ---------------------------------------------------------------------------
def _crex_match(card, base_url: str) -> dict | None:
    link_node = card.css_first("a.match-card-wrapper") or card.css_first("a[href]")
    href = link_node.attributes.get("href", "") if link_node else ""
    full_link = (href if href.startswith("http") else f"{base_url}{href}") if href else ""

    teams = []
    for ti in card.css("div.team-info"):
        name_node = ti.css_first("span.team-name")
        score_node = ti.css_first("span.team-score")
        overs_node = ti.css_first("span.total-overs")
        if name_node is None and score_node is None:
            continue
        teams.append({
            "name": safe_text(name_node, "TBD"),
            "score": safe_text(score_node, ""),
            "overs": safe_text(overs_node, ""),
        })

    if len(teams) < 2:
        return None

    result_node = card.css_first("div.result")
    result_classes = (result_node.attributes.get("class", "") if result_node else "") or ""
    is_live = "live" in result_classes or card.css_first("span.liveTag") is not None

    result_text = ""
    if result_node:
        # Prefer the human result text (e.g. "MI won by 6 wickets") over the "Live" tag text.
        result_text = safe_text(result_node.css_first("div.notes")) or safe_text(result_node.css_first("span.result-text")) or ""

    start_time = safe_text(card.css_first("div.start-text")) or safe_text(card.css_first("span.start-text"))

    if is_live:
        status = "Live"
    elif result_text:
        status = "Completed"
    else:
        status = "Upcoming"

    entry = {
        "status": status,
        "team_1": teams[0]["name"],
        "score_1": teams[0]["score"] or "N.A",
        "overs_1": teams[0]["overs"] or "N.A",
        "team_2": teams[1]["name"],
        "score_2": teams[1]["score"] or "N.A",
        "overs_2": teams[1]["overs"] or "N.A",
        "match_url": full_link,
    }
    if result_text:
        entry["result"] = result_text
    if start_time:
        entry["start_time"] = start_time
    return entry


@app.route(f"/ipl-{SEASON}-live-score-s2")
@app.route("/ipl-live-score-s2")
def ipl_live_score_s2():
    base_url = "https://crex.com"
    candidate_urls = [
        f"{base_url}/series/{CREX_SERIES_SLUG}",
        f"{base_url}/fixtures/match-list",
    ]

    try:
        response = None
        for u in candidate_urls:
            try:
                response = http_get(u)
                break
            except httpx.HTTPError as e:
                logger.warning("Crex URL %s failed: %s", u, e)
                continue
        if response is None:
            return error_payload("Network Error", "Could not reach the Crex source.", "Try again later.")

        tree = HTMLParser(response.text)
        cards = tree.css("app-match-card") or tree.css("div.match-card-container")

        if not cards:
            return jsonify({
                "status_code": 200,
                "status": "No Data",
                "message": "No matches listed yet on Crex.",
                "date_checked": today_iso(),
            })

        matches = {}
        live_matches = {}
        for i, card in enumerate(cards, 1):
            entry = _crex_match(card, base_url)
            if entry is None:
                continue
            matches[f"Match {i}"] = entry
            if entry["status"] == "Live":
                live_matches[f"Match {i}"] = entry

        if not matches:
            return jsonify({
                "status_code": 200,
                "status": "No Data",
                "message": "Found match cards but could not extract any data.",
                "date_checked": today_iso(),
            })

        return jsonify({
            "status_code": 200,
            "season": SEASON,
            "source": "crex",
            "status": "Live" if live_matches else "No Live Matches",
            "live_count": len(live_matches),
            "live_score": live_matches,
            "matches": matches,
            "date_checked": today_iso(),
        })

    except httpx.HTTPError as e:
        logger.error("Live-score-s2 network error: %s", e)
        return error_payload("Network Error", f"Failed to fetch data: {e}", "Try again later.")
    except Exception as e:
        logger.exception("Live-score-s2 unexpected error")
        return error_payload("Server Error", f"Unexpected error: {e}", "Contact support.")


# ---------------------------------------------------------------------------
# Live score (Cricbuzz mobile) — uses /cricket-series/<id>/.../matches
# ---------------------------------------------------------------------------
def _cricbuzz_match(card_anchor, base_url: str) -> dict | None:
    href = card_anchor.attributes.get("href", "") or ""
    title = card_anchor.attributes.get("title", "") or ""
    full_link = href if href.startswith("http") else f"{base_url}{href}"

    info_node = card_anchor.css_first("span.text-cbTxtSec")
    info = safe_text(info_node)

    # Each team row contains a name span (full or short) and a score span.
    rows = card_anchor.css("div.flex.items-center.gap-4.justify-between")
    teams = []
    for row in rows:
        # Team that has batted uses text-cbTxtPrim; team yet to bat uses text-cbTxtSec.
        name_nodes = row.css("span.text-cbTxtPrim, span.text-cbTxtSec")
        name = ""
        for n in name_nodes:
            t = safe_text(n)
            if t:
                name = t
                break
        score_node = row.css_first("span.font-medium") or row.css_first("span.font-semibold")
        score = safe_text(score_node)
        if name or score:
            teams.append({"name": name or "TBD", "score": score or ""})

    if len(teams) < 2 and not info and not title:
        return None
    while len(teams) < 2:
        teams.append({"name": "TBD", "score": ""})

    # Status text appears in the trailing span. Live matches use cbLive*, completed use cbComplete, upcoming use cbPreview.
    status_spans = card_anchor.css("span")
    status_text = ""
    is_live = False
    is_complete = False
    is_upcoming = False
    for s in status_spans:
        cls = s.attributes.get("class", "") or ""
        if "cbLive" in cls or "text-cbLive" in cls:
            is_live = True
            status_text = safe_text(s) or status_text
        elif "cbComplete" in cls and safe_text(s) not in ("Live Score", "Scorecard", "Full Commentary", "News", ""):
            is_complete = True
            status_text = safe_text(s) or status_text
        elif "cbPreview" in cls:
            is_upcoming = True
            status_text = safe_text(s) or status_text

    if is_live:
        status = "Live"
    elif is_complete:
        status = "Completed"
    elif is_upcoming:
        status = "Upcoming"
    else:
        status = "Unknown"

    entry = {
        "status": status,
        "title": title.strip(),
        "info": info,
        "team_1": teams[0]["name"],
        "score_1": teams[0]["score"] or "N.A",
        "team_2": teams[1]["name"],
        "score_2": teams[1]["score"] or "N.A",
        "match_url": full_link,
    }
    if status_text:
        entry["status_text"] = status_text
    return entry


@app.route(f"/ipl-{SEASON}-live-score-s3")
@app.route("/ipl-live-score-s3")
def ipl_live_score_s3():
    base_url = "https://m.cricbuzz.com"
    main_url = f"{base_url}/cricket-match/live-scores"

    try:
        response = http_get(main_url)
        tree = HTMLParser(response.text)

        # Locate the IPL section by its header anchor whose title contains the season.
        header_anchors = tree.css(f'a[title*="Indian Premier League {SEASON}"]')
        ipl_section = None
        for header in header_anchors:
            parent = header.parent
            if parent is not None and parent.css('a[href*="/live-cricket-scores/"]'):
                ipl_section = parent
                break

        if ipl_section is None:
            return jsonify({
                "status_code": 200,
                "status": "No Data",
                "message": f"No IPL {SEASON} section found on Cricbuzz live-scores page.",
                "source_url": main_url,
                "date_checked": today_iso(),
            })

        # Match cards are anchors with the card classes; ignore the small action-link anchors.
        anchors = ipl_section.css('a[href*="/live-cricket-scores/"]')
        seen = set()
        unique_anchors = []
        for a in anchors:
            href = a.attributes.get("href", "") or ""
            cls = a.attributes.get("class", "") or ""
            if not href or href in seen:
                continue
            if "bg-cbWhite" not in cls and "flex-col" not in cls:
                continue
            seen.add(href)
            unique_anchors.append(a)

        if not unique_anchors:
            return jsonify({
                "status_code": 200,
                "status": "No Data",
                "message": "No IPL match cards found on Cricbuzz live-scores page.",
                "source_url": main_url,
                "date_checked": today_iso(),
            })

        matches = {}
        live_matches = {}
        for i, a in enumerate(unique_anchors, 1):
            entry = _cricbuzz_match(a, base_url)
            if entry is None:
                continue
            matches[f"Match {i}"] = entry
            if entry["status"] == "Live":
                live_matches[f"Match {i}"] = entry

        if not matches:
            return jsonify({
                "status_code": 200,
                "status": "No Data",
                "message": "Found anchors but could not extract any match data.",
                "date_checked": today_iso(),
            })

        return jsonify({
            "status_code": 200,
            "season": SEASON,
            "source": "cricbuzz",
            "series_id": CRICBUZZ_SERIES_ID,
            "status": "Live" if live_matches else "No Live Matches",
            "live_count": len(live_matches),
            "live_score": live_matches,
            "matches": matches,
            "date_checked": today_iso(),
        })

    except httpx.HTTPError as e:
        logger.error("Live-score-s3 network error: %s", e)
        return error_payload("Network Error", f"Failed to fetch data: {e}", "Try again later.")
    except Exception as e:
        logger.exception("Live-score-s3 unexpected error")
        return error_payload("Server Error", f"Unexpected error: {e}", "Contact support.")



# ---------------------------------------------------------------------------
# Squads
# ---------------------------------------------------------------------------
TEAMS = {
    "mi": "mumbai-indians",
    "rcb": "royal-challengers-bengaluru",
    "csk": "chennai-super-kings",
    "dc": "delhi-capitals",
    "pbks": "punjab-kings",
    "pk": "punjab-kings",
    "kkr": "kolkata-knight-riders",
    "rr": "rajasthan-royals",
    "srh": "sunrisers-hyderabad",
    "gt": "gujarat-titans",
    "lsg": "lucknow-super-giants",
}


@app.route("/squad/<string:team_micro>")
def get_squad(team_micro):
    team_micro = (team_micro or "").lower().strip()
    if team_micro not in TEAMS:
        return error_payload(
            "Invalid Team",
            f'Team "{team_micro}" not recognized. Valid: {", ".join(sorted(set(TEAMS.keys())))}.',
            "Use one of the listed team codes.",
            code=400,
        )

    team_macro = TEAMS[team_micro]
    url = f"https://www.sportskeeda.com/team/{team_macro}/squad"

    try:
        response = http_get(url)
        tree = HTMLParser(response.text)
        squad_section = tree.css_first("section.team-full-squad")

        if not squad_section:
            return error_payload(
                "Data Unavailable",
                f"No squad section found for {team_macro}.",
                "Source page structure may have changed.",
            )

        player_nodes = squad_section.css("div.team-squad-player")
        if not player_nodes:
            return error_payload(
                "No Players",
                f"No player data extracted for {team_macro}.",
                "Squad may not be published yet.",
            )

        squad = {}
        for i, player in enumerate(player_nodes, 1):
            name = safe_text(player.css_first("span.team-squad-player--name"), "Unknown")
            style_text = safe_text(player.css_first("span.team-squad-player--batting-style"))

            nationality, style = "N/A", "N/A"
            if style_text:
                m = re.match(r"([A-Z]{2,3})\s*\.\s*(.*)", style_text)
                if m:
                    nationality, style = m.group(1), m.group(2).strip() or "N/A"
                else:
                    nationality = style_text[:3]
                    style = style_text[3:].strip() or "N/A"

            role = "N/A"
            try:
                section = player.parent
                while section is not None and section.tag != "section":
                    section = section.parent
                if section is not None:
                    role_node = section.css_first("div.role-title")
                    role = safe_text(role_node, "N/A")
            except Exception:
                role = "N/A"

            captaincy_status = safe_text(player.css_first("div.captain-title")) or None

            info_text = safe_text(player.css_first("div.team-squad-info"))
            is_wk = "(wk)" in info_text.lower()
            is_overseas = "✈" in info_text

            entry = {
                "Name": name,
                "Nationality": nationality,
                "Role": role,
                "Style": style,
                "Wicketkeeper": is_wk,
                "Overseas": is_overseas,
            }
            if captaincy_status:
                entry["Captaincy"] = captaincy_status
            squad[f"Player {i}"] = entry

        return jsonify({"status_code": 200, "team": team_macro, "season": SEASON, "squad": squad})

    except httpx.HTTPError as e:
        logger.error("Squad network error %s: %s", url, e)
        return error_payload("Network Error", f"Failed to fetch data: {e}", "Try again later.")
    except Exception as e:
        logger.exception("Squad unexpected error")
        return error_payload("Server Error", f"Unexpected error: {e}", "Contact support.")


# ---------------------------------------------------------------------------
# IPL winners (history)
# ---------------------------------------------------------------------------
@app.route("/ipl-winners")
def ipl_winners():
    url = "https://www.sportskeeda.com/cricket/ipl-winners-list?ref=carousel"
    try:
        response = http_get(url)
        tree = HTMLParser(response.text)
        table = tree.css_first('table[border="1"] tbody') or tree.css_first("table tbody")

        if not table:
            return error_payload(
                "Data Unavailable",
                "No IPL winners table found.",
                "The page structure may have changed.",
            )

        rows = table.css("tr")
        if len(rows) < 2:
            return error_payload(
                "No Data",
                "No IPL winners data extracted.",
                "Table may be empty.",
            )

        winners = {}
        for row in rows[1:]:
            cells = [safe_text(c) for c in row.css("td")]
            if len(cells) == 5:
                year, winner, won_by, runner_up, venue = cells
            elif len(cells) == 4:
                year, winner, won_by, venue = cells
                m = re.search(r"against\s+([A-Za-z0-9 ()&.\-]+)", won_by)
                runner_up = m.group(1).strip() if m else "N/A"
            else:
                logger.warning("Skipping malformed row: %s", cells)
                continue
            winners[year] = {
                "Winner": winner,
                "Won By": won_by,
                "Runner Up": runner_up,
                "Venue": venue,
            }

        if not winners:
            return error_payload(
                "No Winners",
                "No valid IPL winners data extracted.",
                "Check the table structure.",
            )

        return jsonify({"status_code": 200, "winners": winners})

    except httpx.HTTPError as e:
        logger.error("Winners network error: %s", e)
        return error_payload("Network Error", f"Failed to fetch data: {e}", "Try again later.")
    except Exception as e:
        logger.exception("Winners unexpected error")
        return error_payload("Server Error", f"Unexpected error: {e}", "Contact support.")


# ---------------------------------------------------------------------------
# Health & errors
# ---------------------------------------------------------------------------
@app.route("/health")
def health():
    return jsonify({"status_code": 200, "status": "ok", "season": SEASON})


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.errorhandler(404)
def page_not_found(e):
    logger.warning("404: %s", e)
    return jsonify({
        "status_code": 404,
        "title": "Page Not Found",
        "message": "The requested URL was not found.",
        "resolution": "Check the URL or visit / for available endpoints.",
    }), 404


@app.errorhandler(500)
def server_error(e):
    logger.error("500: %s", e)
    return jsonify({
        "status_code": 500,
        "title": "Internal Server Error",
        "message": "An unexpected error occurred.",
        "resolution": "Try again later.",
    }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=False, host="0.0.0.0", port=port)
