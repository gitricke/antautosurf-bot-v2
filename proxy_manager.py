# proxy_manager.py - Gestore centrale dei proxy

import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, List

class ProxyManager:
    def __init__(self, file_path="proxy_pool.json"):
        self.file_path = file_path
        self.lock = asyncio.Lock()
        self.proxies = self._carica_proxy()
    
    def _carica_proxy(self) -> List[Dict]:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f).get("proxies", [])
        except:
            return []
    
    def _salva_proxy(self):
        try:
            with open(self.file_path, "w") as f:
                json.dump({"proxies": self.proxies}, f, indent=2)
        except:
            pass
    
    async def assegna_proxy(self, account_email: str) -> Optional[str]:
        async with self.lock:
            for proxy in self.proxies:
                if proxy["stato"] == "disponibile":
                    proxy["stato"] = "in_uso"
                    proxy["account_assegnato"] = account_email
                    proxy["ultimo_test"] = datetime.now().isoformat()
                    self._salva_proxy()
                    return proxy["proxy"]
            return None
    
    async def rilascia_proxy(self, proxy_string: str, successo: bool = True):
        async with self.lock:
            for proxy in self.proxies:
                if proxy["proxy"] == proxy_string:
                    if successo:
                        proxy["stato"] = "disponibile"
                        proxy["tentativi_falliti"] = 0
                        proxy["account_assegnato"] = None
                    else:
                        proxy["tentativi_falliti"] += 1
                        if proxy["tentativi_falliti"] >= 3:
                            proxy["stato"] = "morto"
                            proxy["account_assegnato"] = None
                        else:
                            proxy["stato"] = "disponibile"
                            proxy["account_assegnato"] = None
                    self._salva_proxy()
                    return
    
    async def ottieni_statistiche(self) -> Dict:
        return {
            "totale": len(self.proxies),
            "disponibili": len([p for p in self.proxies if p["stato"] == "disponibile"]),
            "in_uso": len([p for p in self.proxies if p["stato"] == "in_uso"]),
            "morti": len([p for p in self.proxies if p["stato"] == "morto"])
        }