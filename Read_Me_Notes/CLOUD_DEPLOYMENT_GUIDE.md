# Cloud Deployment Guide — Trading System

## Why Cloud?

| Problem | Cloud Solution |
|---------|---------------|
| Power cut at home | Cloud VM runs 24/7 on data-center power |
| Internet outage | Cloud has redundant ISP uplinks |
| PC must stay on 24/7 | VM runs independently of your hardware |
| Can't monitor remotely | Dashboard accessible from phone/laptop anywhere |

---

## Recommended Platform: Oracle Cloud Always Free

### Oracle Cloud vs Others

| Feature | Oracle Free | AWS Free | GCP Free |
|---------|------------|----------|----------|
| CPU | **4 cores** ARM | 1 vCPU x86 | 0.2 vCPU |
| RAM | **24 GB** | 1 GB | 0.6 GB |
| Disk | **200 GB** | 30 GB | 30 GB |
| Duration | **Never expires** | 12 months only | Never expires |
| Static IP | Included | Extra cost | Extra cost |
| Run trading 24/7 | ✅ Yes | ❌ After 1yr | ⚠️ Limited |

**Oracle Cloud Always Free** is the only platform that can run all 3 trading programs + dashboard simultaneously at zero cost forever.

---

## Step-by-Step Deployment

### Step 1: Create Oracle Cloud Account

1. Go to https://cloud.oracle.com
2. Click **Free Tier** → **Start for free**
3. Enter email, password, region (choose closest to India: **Mumbai**)
4. Verify phone number via SMS
5. Enter credit card (for identity verification only — free tier costs nothing)
6. Wait 5-10 minutes for account activation

### Step 2: Launch a VM Instance

1. Login to Oracle Cloud Console
2. Click **Compute** → **Instances** → **Create instance**
3. Configure:
   - **Name**: `trading-bot`
   - **Image**: Ubuntu 24.04 (Canonical)
   - **Shape**: VM.Standard.A1.Flex (ARM)
   - **OCPUs**: 4
   - **Memory**: 24 GB
   - **Boot volume**: 200 GB
4. **Networking**: Keep defaults (it auto-assigns a public IP)
5. **SSH Keys**:
   - On your Windows PC, open **PowerShell**
   - Run: `ssh-keygen -t rsa -b 4096 -f ~\.ssh\oracle_key`
   - This creates `oracle_key` (private) and `oracle_key.pub` (public)
   - Click **Add SSH key** → paste the contents of `oracle_key.pub`
6. Click **Create**

Wait 2-3 minutes for instance to start. Note the **Public IP address**.

### Step 3: Connect to Your VM

On your Windows PC, open PowerShell:

```powershell
ssh -i ~\.ssh\oracle_key ubuntu@<PUBLIC_IP>
```

Replace `<PUBLIC_IP>` with the IP from Step 2.

### Step 4: Update System & Install Dependencies

Run these commands inside the SSH session:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git
python3 --version
pip3 --version
```

### Step 5: Upload Trading Code

**Option A — Via SCP (from Windows PowerShell):**

Open a NEW PowerShell window on your PC (don't close the SSH one):

```powershell
scp -i ~\.ssh\oracle_key -r "G:\Poovendan\AI\Share\ReadyToDeploy\New_Develped_Code\*" ubuntu@<PUBLIC_IP>:~/trading/
```

**Option B — Via Git:**

```bash
# On the VM
git clone https://github.com/your-repo/trading-bot.git ~/trading
```

### Step 6: Install Python Packages

```bash
cd ~/trading
pip3 install -r requirements.txt
```

### Step 7: Generate Kite Access Token

```bash
cd ~/trading
python3 Kite_Access_Token_gen.py
```

The script prints a URL. Copy it, open in your PC's browser, login to Zerodha, paste the redirect URL back into SSH. This creates `kite_access_token.txt`.

### Step 8: Install Screen (Session Manager)

```bash
sudo apt install -y screen
```

### Step 9: Launch the Programs

**Using Launcher:**

```bash
cd ~/trading
python3 launcher.py
```

**Using Screen (recommended for 24/7):**

```bash
# Session 1: Index Trade Engine
screen -S index_trade
python3 bull_index_trade_engine.py
# Ctrl+A then D to detach

# Session 2: Stock Scanner
screen -S stock_scanner
python3 bull_nifty50_scanner_executor.py
# Ctrl+A then D to detach

# Session 3: Dashboard
screen -S dashboard
python3 app.py
# Ctrl+A then D to detach
```

### Step 10: Access Dashboard

**Option A — SSH Tunnel (Secure):** On your Windows PC:

```powershell
ssh -i ~\.ssh\oracle_key -L 5050:localhost:5050 ubuntu@<PUBLIC_IP>
```

Then open http://localhost:5050 in your browser.

**Option B — Open Firewall (Direct Access):**

```bash
sudo ufw allow 5050/tcp
```

Then in Oracle Cloud Console → VCN → Security List → Add Ingress Rule for port 5050.

Access via: `http://<PUBLIC_IP>:5050`

---

## Useful Commands

| Task | Command |
|------|---------|
| List screens | `screen -ls` |
| Reattach screen | `screen -r dashboard` |
| Detach | `Ctrl+A` then `D` |
| Stop screen | `screen -XS index_trade quit` |
| View logs | `tail -f ~/trading/trading_scanner_activity.log` |
| View journal | `cat ~/trading/trade_journal.csv` |
| Manual daily scan | `cd ~/trading && python3 bull_nifty50_daily_scanner_export.py` |
| Check disk | `df -h` |
| Check memory | `free -h` |

---

## Cost Summary

| Item | Cost |
|------|------|
| Oracle Cloud VM | **₹0/month** (Always Free) |
| Internet (VM) | Included |
| Electricity | Included |
| **Total** | **₹0** |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Token missing | Run `python3 Kite_Access_Token_gen.py` |
| `Incorrect api_key or access_token` | Token expired. Regenerate. |
| Dashboard won't load | `screen -r dashboard` to check logs |
| Port 5050 refused | `sudo ufw status` — open if needed |
| Disk full | `rm ~/trading/*.log` |
| VM unreachable | Restart from Oracle Cloud Console |
