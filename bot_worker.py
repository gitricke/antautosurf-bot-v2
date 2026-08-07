#!/usr/bin/env python3
# bot_worker.py - BOT V2 con 6 account asincrono-sequenziale (UN CICLO PER ACCOUNT)
# SISTEMA CAPTCHA CONDIVISO - salva sempre le soluzioni nel JSON

import asyncio
import json
import re
import sys
import time
from datetime import datetime
from playwright.async_api import async_playwright
from proxy_manager import ProxyManager

# ============================================================
# CONFIGURAZIONE
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
# SISTEMA CAPTCHA AUTO-APPRENDENTE CON SALVATAGGIO
# ============================================================

def carica_database():
    try:
        with open("hash_phash_db.json", "r") as f:
            return json.load(f)
    except:
        return {}

phash_db = carica_database()
print(f"📊 Database phash: {len(phash_db)} hash")

async def risolvi_captcha(page, email):
    """Sistema avanzato di risoluzione captcha con salvataggio automatico"""
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
            # 🔥 SALVA SUBITO NEL DATABASE!
            phash_db[str(cid)] = cid
            with open("hash_phash_db.json", "w") as f:
                json.dump(phash_db, f, indent=2)
            log(email, f"   💾 CID {cid} salvato nel database!")
            return True
    
    # 3. Se nessun CID funziona, prova con PHASH
    try:
        img_element = await page.query_selector('img[src*="capimg.php"]')
        if img_element:
            from PIL import Image
            import io
            import imagehash
            
            img_data = await img_element.screenshot()
            img_pil = Image.open(io.BytesIO(img_data))
            phash = imagehash.phash(img_pil)
            phash_str = str(phash)
            log(email, f"   🔑 PHASH: {phash_str}")
            
            # Cerca nel database
            for stored_phash, cid in phash_db.items():
                try:
                    diff = imagehash.hex_to_hash(phash_str) - imagehash.hex_to_hash(stored_phash)
                    if diff <= 10:
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
# SURF CYCLE - UN SINGOLO CICLO
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
# GESTISCI ACCOUNT - UN SINGOLO CICLO
# ============================================================

async def gestisci_account(account_data, proxy_manager):
    """Gestisce un singolo account per UN CICLO di surf"""
    
    email = account_data["email"]
    password = account_data["password"]
    
    log(email, "🚀 Avvio account...")
    
    proxy_str = await proxy_manager.assegna_proxy(email)
    if not proxy_str:
        log(email, "❌ Nessun proxy disponibile!")
        return
    
    proxy_config = parse_proxy(proxy_str)
    if not proxy_config:
        log(email, "❌ Proxy non valido!")
        await proxy_manager.rilascia_proxy(proxy_str, successo=False)
        return
    
    log(email, f"🌐 Proxy: {proxy_str.split('@')[1] if '@' in proxy_str else proxy_str}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS,
            proxy=proxy_config,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            if not await login_con_retry(page, email, password):
                await proxy_manager.rilascia_proxy(proxy_str, successo=False)
                return
            
            await page.goto(f"https://antautosurf.com/index.php?bitcoinwallet={email}&ref=")
            await asyncio.sleep(0)
            
            await risolvi_captcha(page, email)
            
            html = await page.content()
            balance_match = re.search(r'btoday["\']?\s*[=:]\s*([\d.]+)', html)
            if balance_match:
                log(email, f"💰 Balance: {balance_match.group(1)}")
            
            # ============================================================
            # 🔥 ESEGUE UN SINGOLO CICLO DI SURF
            # ============================================================
            await surf_cycle(page, email)
            
            log(email, "✅ Ciclo completato, passo al prossimo account")
                    
        except Exception as e:
            log(email, f"❌ Errore: {e}")
            await proxy_manager.rilascia_proxy(proxy_str, successo=False)
        finally:
            await browser.close()
            await proxy_manager.rilascia_proxy(proxy_str, successo=True)

# ============================================================
# MAIN - LOOP INFINITO CON ROTAZIONE ACCOUNT
# ============================================================

async def main():
    print("="*60)
    print("🚀 BOT V2 - 6 ACCOUNT (UN CICLO PER ACCOUNT)")
    print("="*60)
    
    accounts = carica_accounts()
    if not accounts:
        print("❌ Nessun account trovato!")
        return
    
    print(f"📋 Account: {len(accounts)}")
    print(f"🔇 Headless: {HEADLESS}")
    print("="*60)
    
    proxy_manager = ProxyManager("proxy_pool.json")
    stats = await proxy_manager.ottieni_statistiche()
    print(f"📊 Proxy disponibili: {stats['disponibili']}/{stats['totale']}")
    print("="*60)
    print("🔄 Modalità: un ciclo per account, poi rotazione")
    print("="*60)
    
    # 🔥 LOOP INFINITO - ROTAZIONE ACCOUNT
    while True:
        for account in accounts:
            await gestisci_account(account, proxy_manager)
            await asyncio.sleep(0)
            print("─" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Arresto manuale...")
        sys.exit(0)
