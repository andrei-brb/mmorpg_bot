# Finding Your Supabase Connection String

## Step-by-Step:

1. **After creating your project**, click on your project name in the left sidebar
2. Go to **Settings** (gear icon at bottom of left sidebar)
3. Click **"Database"** in the settings menu
4. Scroll down to **"Connection string"** section
5. Look for **"URI"** tab (not "Session mode" or "Transaction mode")
6. Copy the string that looks like:
   ```
   postgresql://postgres.[ref]:[YOUR-PASSWORD]@aws-0-us-west-1.pooler.supabase.com:6543/postgres
   ```
   OR
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```

**Important:** Replace `[YOUR-PASSWORD]` with the password you set when creating the project!

---

## Alternative: I can set up local PostgreSQL instead!

If Supabase is confusing, I can install PostgreSQL on your Mac in about 2 minutes. Just say "yes" or "install local" and I'll do it automatically!
