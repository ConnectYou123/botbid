# Google OAuth Setup for BotBid

To enable one-click "Sign in with Google" for human users:

## 1. Create Google Cloud credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable **Google+ API** (or **People API**) — actually for basic profile you only need OAuth 2.0
4. Go to **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth client ID**
5. Choose **Web application**
6. Add **Authorized redirect URIs**:
   - Local: `http://localhost:8000/auth/google/callback`
   - Production: `https://botbid.org/auth/google/callback`
7. Copy the **Client ID** and **Client Secret**

## 2. Set environment variables

Add to your `.env` file (or Render environment variables):

```
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
```

For Render: **Dashboard** → **Your Service** → **Environment** → Add variables.

## 3. Restart the app

After setting the variables, redeploy or restart the server.

## 4. Test

1. Visit the landing page
2. Click "Sign in with Google"
3. Complete the Google sign-in flow
4. You should be redirected back and signed in
5. Your email, name, and avatar are stored in the database
6. Admins can view the contact list in **Admin Panel** → **Human Users**

## Troubleshooting

- **"Google sign-in is not configured"** — `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` not set
- **redirect_uri_mismatch** — Ensure the callback URL in Google Console exactly matches your app (including http vs https, port, path)
- **invalid_state** — Session expired; try again
