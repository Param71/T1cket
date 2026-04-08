# AlwaysData Deployment Guide (Flask + MySQL)

Follow these exact steps to get **T!CKET** live on your AlwaysData "Free Forever" account.

---

## 1. Create your MySQL Database
1.  Log in to [AlwaysData Dashboard](https://admin.alwaysdata.com/).
2.  Go to **Databases > MySQL** in the left sidebar.
3.  Set a **MySQL Password**.
4.  Copy the **Host** provided (format: `mysql-yourusername.alwaysdata.net`).
5.  Click **Add a database** and name it `t1cket`.

---

## 2. Upload your Files
1.  Go to **Files** in the sidebar.
2.  Click **Upload** and select your project files, **OR** (recommended) use the **Terminal** tab and run:
    ```bash
    git clone https://github.com/Param71/T1cket.git .
    ```
3.  Create a `.env` file in the root folder using their file editor and fill in the details from Step 1:
    ```env
    DB_HOST=mysql-yourusername.alwaysdata.net
    DB_USER=yourusername
    DB_PASSWORD=your_mysql_password
    DB_NAME=yourusername_t1cket
    SECRET_KEY=t1cket_production_key_123
    ```

---

## 3. Initialize Database
1.  Go to the **Consoles** tab and open a **Bash** console.
2.  Run the initialization script:
    ```bash
    python3 init_db.py
    ```
3.  It should say "Database initialized successfully."

---

## 4. Setup the Web App
1.  Go to **Web > Sites**.
2.  Click **Add a site**.
3.  **Type:** Python (WSGI).
4.  **Path:** leave as default `/`.
5.  **Environment:** Select **Python 3.12** (or latest).
6.  **Application path:** `passenger_wsgi.py`.
7.  **Address:** Choose your free subdomain (e.g., `t1cket.alwaysdata.net`).
8.  Click **Submit** at the bottom.

---

## 5. Security Note
> [!IMPORTANT]
> The AlwaysData free tier provides an SSL certificate automatically. Make sure you access your site via `https://` for security.

---

**Your project is now live!** Give it a few seconds to start up on the first visit.
