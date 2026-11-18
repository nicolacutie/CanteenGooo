# CanteenGo – Multi-vendor school canteen prototype

A beginner-friendly Flask + SQLite prototype. Students can browse several vendors, but each cart/order belongs to **one vendor only**. Vendors see only their own orders.

## Run it in GitHub Codespaces

1. Create a new GitHub repository and upload all files/folders from this project.
2. Open the repository on GitHub.
3. Click **Code** → **Codespaces** → **Create codespace on main**.
4. In the Codespaces terminal, run:

   ```bash
   pip install -r requirements.txt
   python app.py
   ```

5. Wait for the forwarded port notification for port **5000**, then click **Open in Browser**.

## Demo vendor accounts

| Stall | Email | Password |
|---|---|---|
| Rice Meals | ricevendor@demo.com | rice123 |
| Snacks | snacksvendor@demo.com | snacks123 |
| Drinks | drinksvendor@demo.com | drinks123 |

Create a student account using **Register**.

## Current prototype features

- Student registration and login
- Three sample vendors with separate menus
- A cart can contain products from only one vendor
- Separate order per vendor
- Cash on Pickup and Online Payment (Demo)
- Student order history and status
- Vendor dashboards with vendor-specific orders
- Vendors can update order status

## Important limitations

- Online payment is a **demo only**. No money is collected.
- This is a school-project prototype, not ready for real student transactions.
- Before deployment, change the Flask secret key, turn off debug mode, add CSRF protection, validate inputs more thoroughly, and use a production database/hosting setup.
- Demo vendor passwords are public in this README. Change them before any real deployment.
- The SQLite database file is created automatically when you run `python app.py`.
