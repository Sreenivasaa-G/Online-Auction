# BidSpace — Complete Online Auction Demo

A polished educational auction marketplace using Python Flask, Flask-SQLAlchemy, SQLite, HTML, CSS, JavaScript, and CSRF protection. Bidding is simulated: no real payments or sales.

## Features
- Responsive marketplace with sample listings, search, category filters, and countdowns
- Registration and login; passwords are securely hashed
- CSRF protection on POST forms
- Auction details, bid validation, bid history, and personal bid history
- Personal watchlist: save/remove listings
- Ended-auction winner display; highest bid wins, or no winner if no bids
- Admin dashboard with counts, listing creation, and hide/unhide controls
- SQLite database created automatically and sample data seeded on first run
- HTTP-only and SameSite session cookie settings

## Requirements
- Python 3.10+ (Python 3.12 is a good choice)
- Internet access on first run to install dependencies; product images and Google Fonts use external URLs

## Run on Windows with VS Code
1. Extract the ZIP and open the `online_auction_complete` folder in VS Code.
2. In the VS Code terminal:
   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe app.py
   ```
   You can use `py -m venv .venv` if `py -3.12` is not available. If you use PowerShell activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then `.\.venv\Scripts\Activate.ps1`.
3. Open http://127.0.0.1:5000.

The database is stored in Flask's `instance` directory. It is created automatically at startup.

## Demo admin account
- Email: `admin@auction.demo`
- Password: `Admin123!`

Change the demo password and set a strong `SECRET_KEY` before deploying. Do not expose this demo account publicly.

## Demo flow
1. Browse and filter products.
2. Register a user account and log in.
3. Place a bid greater than the current highest bid.
4. Check bid history and My Bids.
5. Save items to Watchlist.
6. Sign in as admin to create a listing and hide/unhide listings.
7. Ended auctions show the highest bidder if at least one bid exists.

## Important limitations
This is a complete college demonstration, not a production auction or payment system. It does not collect money, send notifications, or implement real-time WebSocket bidding. For production use, add database transaction/locking guarantees for concurrent bids, rate limiting, email verification, password reset, automated tests, and a production server. Set `COOKIE_SECURE=1` only when serving over HTTPS.
