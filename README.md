<p align="center">
  <img src="https://github.com/user-attachments/assets/77d3f84b-7f03-49bf-9d32-ecf5a410db0c" alt="IPL 2025 API" width="200" height="200">
</p>

<h1 align="center">IPL 2025 API</h1>

<p align="center">Free and simple API for IPL 2025 cricket data.</p>

### Overview

IPL 2025 API provides easy access to Indian Premier League data, including live scores, team squads, and past winners. Built by Sannjay, this project is open-source under the MIT License and hosted at [https://ipl-okn0.onrender.com](https://ipl-okn0.onrender.com). Perfect for developers needing cricket stats.

### Features

- Live IPL 2025 scores with multiple speed options
- Team squad details for all 10 IPL teams
- Historical IPL winners from 2008 onwards
- Lightweight and fast responses
- Free to use, no API key required

### Endpoints

| Endpoint                  | Description                     | Sample Response                                      |
|---------------------------|---------------------------------|-----------------------------------------------------|
| `/ipl-2025-schedule`      | IPL 2025 match schedule         | `{ "status_code": 200, "schedule": { "Match 1": { "Date": "2025-03-20", "Team 1": "Mumbai Indians", "Team 2": "Chennai Super Kings", "Venue": "Mumbai" } } }` |
| `/ipl-2025-points-table`  | Current points table            | `{ "status_code": 200, "points_table": { "Team 1": { "Name": "Mumbai Indians", "Matches": 2, "Wins": 2, "Losses": 0, "Points": 4 } } }` |
| `/ipl-2025-live-score`    | Live scores (moderate speed)    | `{ "status_code": 200, "live_score": { "Match 1": { "Now": "10th Match", "Team 1": "MI", "1st innings": "183/4 (20)", "Team 2": "CSK", "2nd innings": "150/3 (18)", "CR": "8.33", "RR": "9.00" } } }` |
| `/ipl-2025-live-score-s2` | Live scores (slower variant)    | `{ "status_code": 200, "live_score": { "Match 1": { "Now": "11th Match", "Team 1": "RCB", "1st innings": "165/6 (20)", "Team 2": "KKR", "2nd innings": "120/5 (15)", "CR": "8.00", "RR": "9.20" } } }` |
| `/ipl-2025-live-score-s3` | Live scores (fastest variant)   | `{ "status_code": 200, "live_score": { "Match 1": { "Now": "12th Match", "Team 1": "CSK", "1st innings": "190/5 (20)", "Team 2": "DC", "2nd innings": "170/4 (19)", "CR": "8.94", "RR": "10.00" } } }` |
| `/squad/<team_micro>`     | Team squad details (e.g., /squad/mi) | `{ "status_code": 200, "squad": { "Player 1": { "Name": "Hardik Pandya", "Nationality": "IND", "Role": "All Rounders", "Style": "Right Handed Bat", "Wicketkeeper": false, "Overseas": false, "Captaincy": "Captain" } } }` |
| `/ipl-winners`            | Historical IPL winners          | `{ "status_code": 200, "winners": { "2023": { "Winner": "Chennai Super Kings", "Won By": "5 wickets", "Runner Up": "Gujarat Titans", "Venue": "Ahmedabad" } } }` |

**[Visit Live API](https://ipl-okn0.onrender.com)**

### Team Codes for `/squad/<team_micro>`

- mi: Mumbai Indians
- rcb: Royal Challengers Bengaluru
- csk: Chennai Super Kings
- dc: Delhi Capitals
- pk: Punjab Kings
- kkr: Kolkata Knight Riders
- rr: Rajasthan Royals
- srh: Sunrisers Hyderabad
- gt: Gujarat Titans
- lsg: Lucknow Super Giants

### Usage

Test any endpoint with a simple HTTP request:

```bash
curl https://ipl-okn0.onrender.com/ipl-2025-points-table
```

Use tools like Postman or your preferred client. No authentication needed.

### Performance

Tested with [Pingdom Tools](https://tools.pingdom.com/):

- **/ipl-2025-schedule**
  - Performance Grade: A100
  - Page Size: 2.4 KB
  - Load Time: 610 ms
  - Requests: 2
  - [Test Endpoint](https://ipl-okn0.onrender.com/ipl-2025-schedule)

- **/squad/mi**
  - Performance Grade: A100
  - Page Size: 1.7 KB
  - Load Time: 396 ms
  - Requests: 2
  - [Test Endpoint](https://ipl-okn0.onrender.com/squad/mi)

- **/ipl-winners**
  - Performance Grade: A100
  - Page Size: 1.5 KB
  - Load Time: 362 ms
  - Requests: 2
  - [Test Endpoint](https://ipl-okn0.onrender.com/ipl-winners)

### Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the app:
   ```bash
   python app.py
   ```

Requirements: `flask`, `httpx`, `selectolax`

### Contributing

Fork this repo, make changes, and submit a pull request. Issues can be reported at [GitHub Issues](hhttps://github.com/cu-sanjay/IPL-2025-API-Free/issues).

### License

MIT License. Free to use and modify.
