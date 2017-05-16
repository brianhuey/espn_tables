# ESPN Fantasy Baseball Table Parser

This package can be used to import ESPN Fantasy Baseball League data as 
Pandas DataFrames. It can be used to download league wide and team specific
data in real-time.


### Supported tables
- Standings
- Draft Results
- Active Stats
- Transactions

### Install:
``` python
python setup.py install
```

### Usage:
```python
import espn_tables
```
League Data:
```python
league = espn_tables.League(leagueId, 2016)
# Get league standings tables
league.getStandingsTable()
```
Team Data:
```python
team = espn_tables.Team(leagueId, 2016, teamId)
# Get team pitching active stats
team.getActiveStatsTable(batter=False)
```
