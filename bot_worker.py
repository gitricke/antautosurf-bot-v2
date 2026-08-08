#!/usr/bin/env python3
# bot_worker.py - CON SUPABASE (proxy NON cancellati se falliscono)

import asyncio
import json
import re
import sys
import os
from datetime import datetime
from playwright.async_api import async_playwright
from supabase import create_client, Client
from PIL import Image
import io
import imagehash

# ============================================================
# CONFIGURAZIONE SUPABASE
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://osetncxfnkgzlfxmltrl.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9zZXRuY3hmbmtnemxmeG1sdHJsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjEwNjc4MCwiZXhwIjoyMTAxNjgyNzgwfQ.Omc1pr1pPHq1M8Ph2HzLy1KAGRMzY4JYB5GbGulIYUM")
WORKER_ID = os.getenv("WORKER_ID", "worker_1")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# CONFIGURAZIONE BOT
# ============================================================

HEADLESS = True
MAX_RETRY = 3
ACCOUNTS_FILE = "accounts.json"

# ============================================================
# CARICA ACCOUNT
# ============================================================

def carica_accounts():
    try:
        with open(ACCOUNTS_FILE, "r") as f:
            return json.load(f)
    except:
        print(f"❌ File {ACCOUNTS_FILE} non trovato!")
        return []

# ============================================================
# FUNZIONI DI UTILITÀ
# ============================================================

def log(email, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{email[:10]}...] {msg}", flush=True)

def parse_proxy(proxy_str):
    try:
        auth, host = proxy_str.split('@')
        user, password = auth.split(':')
        return {"server": f"http://{host}", "username": user, "password": password}
    except:
        return None

# ============================================================
# FUNZIONI DATABASE - GESTIONE PROXY
# ============================================================

def get_proxy_table():
    return f"proxy_pool_{WORKER_ID}"

async def prendi_proxy():
    """
    Prende un proxy dal database (NON LO CANCELLA, lo segna come "in_uso")
    Restituisce: (proxy_string, proxy_id) o (None, None)
    """
    table = get_proxy_table()
    
    try:
        # Prendi il primo proxy disponibile
        response = supabase.table(table).select("id, proxy").eq("status", "available").limit(1).execute()
        
        if not response.data:
            print(f"❌ Nessun proxy disponibile per {WORKER_ID}")
            return None, None
        
        proxy_data = response.data[0]
        proxy_id = proxy_data["id"]
        proxy = proxy_data["proxy"]
        
        # 🔥 NON CANCELLARE! Segna solo come "in_uso"
        supabase.table(table).update({
            "status": "in_uso",
            "assigned_to": WORKER_ID,
            "assigned_at": datetime.now().isoformat()
        }).eq("id", proxy_id).execute()
        
        print(f"📤 Proxy {proxy_id} preso (in uso)")
        return proxy, proxy_id
        
    except Exception as e:
        print(f"❌ Errore prendi_proxy: {e}")
        return None, None

async def cancella_proxy(proxy_id):
    """Cancella un proxy dal database (SOLO dopo surf riuscito)"""
    table = get_proxy_table()
    
    try:
        supabase.table(table).delete().eq("id", proxy_id).execute()
        print(f"🗑️ Proxy {proxy_id} CANCELLATO (surf riuscito)")
        return True
    except Exception as e:
        print(f"❌ Errore cancellazione proxy: {e}")
        return False

async def rilascia_proxy(proxy_id):
    """Rilascia un proxy (torna disponibile se fallisce)"""
    table = get_proxy_table()
    
    try:
        supabase.table(table).update({
            "status": "available",
            "assigned_to": None,
            "assigned_at": None
        }).eq("id", proxy_id).execute()
        print(f"🔄 Proxy {proxy_id} RILASCIATO (torna disponibile)")
        return True
    except Exception as e:
        print(f"❌ Errore rilascio proxy: {e}")
        return False

async def ottieni_statistiche():
    """Ottiene statistiche sui proxy disponibili"""
    table = get_proxy_table()
    
    try:
        total = supabase.table(table).select("id").execute()
        available = supabase.table(table).select("id").eq("status", "available").execute()
        in_uso = supabase.table(table).select("id").eq("status", "in_uso").execute()
        
        print(f"📊 Proxy: {len(available.data)} disponibili, {len(in_uso.data)} in uso, {len(total.data)} totali")
        return {
            "totale": len(total.data),
            "disponibili": len(available.data),
            "in_uso": len(in_uso.data)
        }
    except:
        return {"totale": 0, "disponibili": 0, "in_uso": 0}

# ============================================================
# SISTEMA CAPTCHA CON SUPABASE
# ============================================================

def carica_database_locale():
    try:
        with open("hash_phash_db.json", "r") as f:
            return json.load(f)
    except:
        return {}

phash_db = carica_database_locale()
print(f"📊 Database phash locale: {len(phash_db)} hash")

async def risolvi_captcha(page, email):
    """Sistema avanzato di risoluzione captcha con Supabase"""
    html = await page.content()
    
    if "Please Click Similar" not in html:
        return True
    
    log(email, "⚠️ CAPTCHA RILEVATO!")
    
    # 1. Estrai tutti i CID disponibili
    cids = [int(x) for x in re.findall(r'cid=(\d+)', html)]
    cids_unici = list(set(cids))
    log(email, f"   📌 CID disponibili: {cids_unici}")
    
    # 2. Prova ogni CID
    for cid in cids_unici:
        await page.goto(f"https://antautosurf.com/index.php?cid={cid}")
        await asyncio.sleep(2)
        html_test = await page.content()
        if "Please Click Similar" not in html_test:
            log(email, f"   ✅ CAPTCHA RISOLTO! CID: {cid}")
            # Salva su Supabase
            try:
                supabase.table("captcha_cache").insert({"phash": str(cid), "cid": cid}).execute()
            except:
                pass
            return True
    
    # 3. Se nessun CID funziona, prova con PHASH
    try:
        img_element = await page.query_selector('img[src*="capimg.php"]')
        if img_element:
            img_data = await img_element.screenshot()
            img_pil = Image.open(io.BytesIO(img_data))
            phash = imagehash.phash(img_pil)
            phash_str = str(phash)
            log(email, f"   🔑 PHASH: {phash_str}")
            
            # Cerca su Supabase
            try:
                response = supabase.table("captcha_cache")\
                    .select("cid")\
                    .eq("phash", phash_str)\
                    .limit(1)\
                    .execute()
                
                if response.data:
                    cid = response.data[0]["cid"]
                    await page.goto(f"https://antautosurf.com/index.php?cid={cid}")
                    await asyncio.sleep(2)
                    log(email, f"   ✅ CAPTCHA RISOLTO! CID: {cid} (da database)")
                    return True
            except:
                pass
    except:
        pass
    
    log(email, f"   ❌ CAPTCHA NON RISOLTO!")
    return False

# ============================================================
# LOGIN CON RETRY
# ============================================================

async def login_con_retry(page, email, password):
    for tentativo in range(MAX_RETRY):
        log(email, f"📧 Tentativo login {tentativo+1}/{MAX_RETRY}")
        
        try:
            await page.goto("https://antautosurf.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            
            await page.fill('input[name="bitcoinwallet"]', email)
            await page.click('input[type="submit"][value*="Enter"]')
            await asyncio.sleep(3)
            
            html = await page.content()
            
            if "Set Login Password" in html:
                log(email, "📝 Nuovo account! Registro...")
                await page.fill('input[name="password"]', password)
                await page.fill('input[name="passwordb"]', password)
                match = re.search(r'name="confirm2" value="(\d+)"', html)
                if match:
                    confirm2 = match.group(1)
                    await page.goto(f"https://antautosurf.com/index.php?password={password}&passwordb={password}&confirm2={confirm2}")
                    await asyncio.sleep(3)
                    log(email, "   ✅ Password impostata!")
                    continue
            
            html = await page.content()
            if "Please enter Password" in html:
                await page.fill('input[name="password"]', password)
                await page.click('input[value="Enter"]')
                await asyncio.sleep(3)
            
            html = await page.content()
            if "Please enter Password" not in html and "Set Login Password" not in html:
                log(email, "✅ Login completato!")
                return True
            
        except Exception as e:
            log(email, f"⚠️ Errore tentativo {tentativo+1}: {e}")
            await asyncio.sleep(5)
    
    log(email, "❌ Login fallito dopo 3 tentativi")
    return False

# ============================================================
# SURF CYCLE
# ============================================================

async def surf_cycle(page, email):
    """Esegue un singolo ciclo di surf per un account"""
    
    log(email, f"🔄 CICLO")
    
    await page.goto(f"https://antautosurf.com/surf.php?wallet={email}")
    await asyncio.sleep(0)
    
    page_text = await page.content()
    
    if "--_--" not in page_text:
        await asyncio.sleep(5)
        return False
    
    parts = page_text.split("--_--")
    if len(parts) < 4:
        return False
    
    ad_url = parts[0].strip()
    time_val = int(parts[1])
    
    log(email, f"   📢 Annuncio! Timer: {time_val}s")
    
    for i in range(time_val, 0, -1):
        print(f"[{email[:10]}] ⏳ {i}s", end="\r")
        await asyncio.sleep(0)
        await asyncio.sleep(1)
    
    print(" " * 30, end="\r")
    log(email, f"   ✅ Timer completato!")
    return True

# ============================================================
# GESTISCI ACCOUNT - CON GESTIONE PROXY INTELLIGENTE
# ============================================================

async def gestisci_account(account_data):
    """
    Gestisce un singolo account per UN CICLO di surf.
    Proxy: se fallisce → torna disponibile, se successo → cancellato
    """
    
    email = account_data["email"]
    password = account_data["password"]
    
    log(email, "🚀 Avvio account...")
    
    # 🔥 1. PRENDI PROXY (NON CANCELLATO!)
    proxy_str, proxy_id = await prendi_proxy()
    if not proxy_str:
        log(email, "❌ Nessun proxy disponibile!")
        return
    
    proxy_config = parse_proxy(proxy_str)
    if not proxy_config:
        log(email, "❌ Proxy non valido!")
        await rilascia_proxy(proxy_id)  # Rilascia (torna disponibile)
        return
    
    log(email, f"🌐 Proxy: {proxy_str.split('@')[1] if '@' in proxy_str else proxy_str}")
    
    successo = False  # 🔥 Traccia se il ciclo è riuscito
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS,
            proxy=proxy_config,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # LOGIN
            if not await login_con_retry(page, email, password):
                await rilascia_proxy(proxy_id)
                return
            
            # DASHBOARD
            await page.goto(f"https://antautosurf.com/index.php?bitcoinwallet={email}&ref=")
            await asyncio.sleep(0)
            
            # CAPTCHA
            await risolvi_captcha(page, email)
            
            # BALANCE
            html = await page.content()
            balance_match = re.search(r'btoday["\']?\s*[=:]\s*([\d.]+)', html)
            if balance_match:
                log(email, f"💰 Balance: {balance_match.group(1)}")
            
            # 🔥 SURF - SE ARRIVA QUI, HA FUNZIONATO
            await surf_cycle(page, email)
            
            log(email, "✅ Ciclo completato, passo al prossimo account")
            successo = True  # 🔥 MARK SUCCESSO!
                    
        except Exception as e:
            log(email, f"❌ Errore: {e}")
            await rilascia_proxy(proxy_id)  # Rilascia (torna disponibile)
        finally:
            await browser.close()
            
            # 🔥 SOLO SE HA AVUTO SUCCESSO, CANCELLA IL PROXY!
            if successo:
                await cancella_proxy(proxy_id)
            else:
                await rilascia_proxy(proxy_id)  # Già rilasciato, ma per sicurezza

# ============================================================
# MAIN - LOOP INFINITO CON ROTAZIONE ACCOUNT
# ============================================================

async def main():
    print("="*60)
    print(f"🚀 BOT V2 - SUPABASE ({WORKER_ID})")
    print("="*60)
    
    accounts = carica_accounts()
    if not accounts:
        print("❌ Nessun account trovato!")
        return
    
    print(f"📋 Account: {len(accounts)}")
    print(f"🔇 Headless: {HEADLESS}")
    print(f"📦 Worker: {WORKER_ID}")
    print("="*60)
    
    # Mostra statistiche iniziali
    await ottieni_statistiche()
    print("="*60)
    
    # 🔥 LOOP INFINITO - ROTAZIONE ACCOUNT
    while True:
        for account in accounts:
            await gestisci_account(account)
            await asyncio.sleep(2)
            print("─" * 60)
            
            # Ogni 5 cicli, mostra statistiche
            if accounts.index(account) == 0:
                await ottieni_statistiche()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Arresto manuale...")
        sys.exit(0)
