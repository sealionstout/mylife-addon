# Installing myLife on your HA Green — the no-GitHub way

You'll copy the add-on folder into the Green's built-in `/addons` share, then
install it as a "local add-on." No GitHub, no build tools on your Mac.

## Step 0 — What you need
- The `mylife` folder (inside `mylife-addon/`) from this project.
- A way to copy files onto the Green. Easiest: the **Samba share** add-on
  (network folder) or the **Studio Code Server** / **File editor** add-on.

---

## Step 1 — Install the Samba share add-on (one time)
1. In HA (Safari): **Settings → Add-ons → Add-on Store**.
2. Search **"Samba share"** → click it → **Install** → **Start**.
3. Open its **Configuration** tab, set a username + password, **Save**, restart the add-on.
   (This exposes the Green's folders to your Mac over the network.)

## Step 2 — Connect to the Green from your Mac
1. In **Finder**, press **Cmd+K** (Go → Connect to Server).
2. Enter: `smb://192.168.4.198`
3. Log in with the Samba username/password you just set.
4. Mount the **`addons`** share when prompted. A folder opens in Finder.

## Step 3 — Copy the add-on in
1. Copy the entire **`mylife`** folder (the one containing `config.yaml`,
   `Dockerfile`, `run.sh`, `app/`) into that mounted **`addons`** folder.
2. Final layout on the Green should be:
   ```
   addons/
     mylife/
       config.yaml
       Dockerfile
       run.sh
       requirements.txt
       app/...
   ```

## Step 4 — Install it as a local add-on
1. In HA: **Settings → Add-ons → Add-on Store**.
2. Top-right **⋮ menu → Check for updates** (this makes HA rescan `/addons`).
3. Scroll down — you'll see a **"Local add-ons"** section with **myLife Dashboard**.
4. Click it → **Install** (first build takes a few minutes — it builds the container).

## Step 5 — Configure & start
1. On the myLife add-on page → **Configuration** tab.
2. Confirm your kids/sizes look right (Brady YL, Beau YM, Logan YS) — edit if needed.
3. **Save** → go to **Info** tab → **Start**.
4. Turn ON **"Start on boot"** and **"Watchdog"** (auto-restart).
5. Open the **Log** tab — you should see:
   `Starting myLife backend on :8000` then `pulled home ok` / `pulled shopping ok`.

## Step 6 — Open your dashboard
- On your home network, go to: **http://192.168.4.198:8000**
- You'll see your real dashboard: live thermostat, lights, security, presence,
  and live BL101 tees & shorts. It refreshes every 60 seconds.

*(Safari works great. Chrome may need the http:// trick from before, or just
use the IP directly.)*

---

## Troubleshooting
- **Don't see myLife under Local add-ons?** ⋮ → Check for updates again, or
  reload the page. Make sure the folder is `addons/mylife/` (not nested deeper).
- **Build fails?** Open the Log tab and copy the error to Ryan/assistant.
- **`pulled home FAILED`?** The add-on talks to HA via the built-in supervisor
  proxy — make sure `homeassistant_api: true` is in config.yaml (it is by default).
- **Lights show 0?** That only happened in offline testing; live HA populates them.
- **Want it on your phone away from home later?** Add the free **Tailscale**
  add-on, or Nabu Casa — the dashboard URL then works from anywhere.
