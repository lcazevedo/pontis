# Creating a Google Drive OAuth `client_id` for Pontis

By default, `rclone` uses a shared global OAuth client ID for Google Drive. Because that client ID is shared across all `rclone` users worldwide, it can hit API rate limits (`403 rateLimitExceeded` / slow directory listings).

Creating your own **free Google Cloud `client_id` and `client_secret`** keeps your quota dedicated to your account and makes syncing significantly faster and more reliable.

---

## Step 1: Create a Google Cloud Project

1. Sign in to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project selector at the top and choose **New Project**.
3. Give it a name (e.g., `Pontis-Drive-Sync`) and click **Create**.
4. Make sure the newly created project is selected in the top bar.

## Step 2: Enable the Google Drive API

1. Open the left navigation menu and go to **APIs & Services → Library**.
2. Search for **Google Drive API**.
3. Click **Google Drive API** and then click **Enable**.

## Step 3: Configure the OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen** (or **Google Auth platform → Branding / Audience**).
2. Choose **External** as the user type (unless you are inside a Google Workspace organization and only want internal users) and click **Create**.
3. Fill in the required fields:
   - **App name:** `Pontis Sync` (or any personal name).
   - **User support email:** your email address.
   - **Developer contact information:** your email address.
4. On the **Scopes** step, add:
   - `.../auth/drive` (or keep default and let `rclone` request it during authorization).
5. On the **Test users** (Audience) step, click **Add Users** and add **your own Google email address**.
   > 💡 Leaving the app in **Testing** mode is completely fine for personal use and avoids Google's public app verification process. Note that in Testing mode, refresh tokens expire after **7 days** unless you publish the app (or re-authorize when prompted); if you choose **Publish App** for personal use without sensitive scopes, Google shows an *"App isn't verified"* warning screen that you can click past via **Advanced → Go to ... (unsafe)** since you own the project.

## Step 4: Create OAuth Desktop Credentials

1. Go to **APIs & Services → Credentials**.
2. Click **+ Create Credentials → OAuth client ID**.
3. For **Application type**, select **Desktop app**.
4. Give it a name (e.g., `Pontis Linux Desktop`) and click **Create**.
5. Copy the generated **Client ID** and **Client Secret**.

## Step 5: Use the Credentials in Pontis

### Option A: Create a new remote with Pontis CLI

```bash
pontis remote add gdrive drive \
  --param client_id=YOUR_CLIENT_ID.apps.googleusercontent.com \
  --param client_secret=YOUR_CLIENT_SECRET
```

A browser window will open so you can sign in and grant access to your Google account. Once finished, verify connectivity:

```bash
pontis remote test gdrive
```

### Option B: Import from an existing `rclone.conf`

If you already configured a remote with a custom `client_id` using `rclone config`, import it directly into Pontis's isolated configuration (`~/.config/pontis/rclone.conf`):

```bash
pontis remote import --remote gdrive
pontis remote test gdrive
```

---

## Security Notes

- Keep your `client_secret` private; never commit `~/.config/pontis/rclone.conf` to Git.
- Pontis stores its `rclone.conf` with `0600` permissions and excludes all credentials when exporting profiles (`pontis profile export`).
