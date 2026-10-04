import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_KEY = os.environ.get("STEAM_API_KEY")
STEAM_ID = "76561199089422261"
BASE = "https://api.steampowered.com"
OUT = "dados"


def agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def iso(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


def get_json(url, tentativas=3):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "steam-dados/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 403, 404):
                return None
            time.sleep(2 * (i + 1))
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def api(caminho, **params):
    params["key"] = API_KEY
    return get_json(f"{BASE}/{caminho}?{urllib.parse.urlencode(params)}")


def salvar(nome, dados):
    os.makedirs(OUT, exist_ok=True)
    corpo = {"atualizado_em": agora(), "total": len(dados), "dados": dados}
    with open(f"{OUT}/{nome}.json", "w", encoding="utf-8") as f:
        json.dump(corpo, f, ensure_ascii=False, indent=1)
    print(f"{nome}: {len(dados)} registros")


def biblioteca():
    d = api(
        "IPlayerService/GetOwnedGames/v1/",
        steamid=STEAM_ID,
        include_appinfo=1,
        include_played_free_games=1,
        format="json",
    )
    jogos_api = ((d or {}).get("response") or {}).get("games")
    if not jogos_api:
        sys.exit("Falha ao ler a biblioteca. Confira a chave e a privacidade do perfil.")
    jogos = []
    for g in jogos_api:
        jogos.append(
            {
                "appid": g["appid"],
                "nome": g.get("name"),
                "horas": round(g.get("playtime_forever", 0) / 60, 1),
                "horas_ultimas_2_semanas": round(g.get("playtime_2weeks", 0) / 60, 1),
                "ultima_vez_jogado": iso(g.get("rtime_last_played")),
            }
        )
    jogos.sort(key=lambda j: (j["nome"] or "").lower())
    return jogos


def nomes_da_loja(appids):
    resultado = {}
    for i in range(0, len(appids), 50):
        lote = appids[i : i + 50]
        entrada = {
            "ids": [{"appid": a} for a in lote],
            "context": {"language": "portuguese", "country_code": "BR"},
            "data_request": {"include_basic_info": True},
        }
        d = api("IStoreBrowseService/GetItems/v1/", input_json=json.dumps(entrada))
        for item in ((d or {}).get("response") or {}).get("store_items", []):
            opcao = item.get("best_purchase_option") or {}
            resultado[item.get("appid")] = {
                "nome": item.get("name"),
                "preco": opcao.get("formatted_final_price"),
                "desconto_percentual": opcao.get("discount_pct"),
            }
        time.sleep(1)
    return resultado


def wishlist():
    d = api("IWishlistService/GetWishlist/v1/", steamid=STEAM_ID)
    itens = ((d or {}).get("response") or {}).get("items", [])
    info = nomes_da_loja([i["appid"] for i in itens])
    saida = []
    for i in itens:
        extra = info.get(i["appid"], {})
        saida.append(
            {
                "appid": i["appid"],
                "nome": extra.get("nome"),
                "preco": extra.get("preco"),
                "desconto_percentual": extra.get("desconto_percentual"),
                "prioridade": i.get("priority"),
                "adicionado_em": iso(i.get("date_added")),
            }
        )
    saida.sort(key=lambda w: (w["prioridade"] or 9999))
    return saida


def conquistas(jogos):
    saida = []
    for g in jogos:
        if g["horas"] <= 0:
            continue
        d = api(
            "ISteamUserStats/GetPlayerAchievements/v1/",
            steamid=STEAM_ID,
            appid=g["appid"],
        )
        lista = ((d or {}).get("playerstats") or {}).get("achievements")
        if lista:
            total = len(lista)
            feitas = sum(1 for a in lista if a.get("achieved") == 1)
            saida.append(
                {
                    "appid": g["appid"],
                    "nome": g["nome"],
                    "conquistas_feitas": feitas,
                    "conquistas_total": total,
                    "percentual": round(100 * feitas / total, 1),
                }
            )
        time.sleep(0.2)
    return saida


def main():
    if not API_KEY:
        sys.exit("Variável STEAM_API_KEY não definida.")
    jogos = biblioteca()
    salvar("biblioteca", jogos)
    salvar("wishlist", wishlist())
    salvar("conquistas", conquistas(jogos))


if __name__ == "__main__":
    main()
