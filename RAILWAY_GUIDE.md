# Railway Deployment Guide (Flask + MySQL)

Follow these exact steps to get **T!CKET** live on Railway.

---

## 1. Create a Railway Project
1.  Log in to [Railway.app](https://railway.app/).
2.  Click **New Project** (+).
3.  Select **Deploy from GitHub repo** and choose your `T1cket` repository.

---

## 2. Add MySQL Database
1.  In your Railway project dashboard, click **Add Service** (+).
2.  Select **Database** -> **MySQL**.
3.  Railway will automatically add the database and the environment variables (`MYSQLHOST`, `MYSQLUSER`, etc.) to your project.

---

## 3. Configure Environment Variables
1.  Click on your **Flask Service** (the one from GitHub).
2.  Go to the **Variables** tab.
3.  Add the following variables manually (Railway provides the MySQL ones automatically):
    - `SECRET_KEY`: any long random string (e.g., `rails_rock_777_ticket`)
    - `PYTHON_VERSION`: `3.10` (or your version)

---

## 4. Initialize Database
Because Railway boots your app automatically, you need to run the `init_db.py` script once to create the tables.
1.  Go to your **Flask Service**.
2.  Click the **Console** tab.
3.  Type and run:
    ```bash
    python init_db.py
    ```
4.  Once it says "Database initialized successfully," your site is ready!

---

## 5. Domain & Access
1.  Go to your **Flask Service** -> **Settings**.
2.  In the **Networking** section, click **Generate Domain**.
3.  Click the link to visit your live site!

---

**Note:** Railway uses a `Procfile` I created to start the app using `gunicorn`, which is much safer and faster for your presentation.
