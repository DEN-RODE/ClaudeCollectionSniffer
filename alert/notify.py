"""
Module d'alerte (STEP 6).

Hiérarchie de sortie, toutes optionnelles sauf la console :
  1. console : toujours (lisible en run local).
  2. Telegram : si TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID dans l'env.
  3. Discord  : si DISCORD_WEBHOOK_URL dans l'env.

On n'envoie une notif PUSH que pour les pépites (verdict == "PÉPITE", score >= 75).
Le reste ("À surveiller") part en digest console.
"""
import os
import requests


def format_alert(listing, gem, comp: dict, trend: dict) -> str:
    """Message lisible : pièce, score, comp, tendance, mise max, lien."""
    lines = [
        f"{gem.verdict} — score {gem.score}/100",
        listing.title,
        f"Prix : {listing.price_eur:.0f} € ({listing.source})",
    ]
    if comp and comp.get("comp_median"):
        lines.append(f"Comp marché (médiane active) : {comp['comp_median']:.0f} € (n={comp.get('n')})")
    if gem.max_bid_eur is not None:
        lines.append(f"Mise max conseillée : {gem.max_bid_eur:.0f} €")
    if trend and trend.get("direction"):
        d = trend["direction"]
        pct = f" ({trend.get('change_pct')}%)" if trend.get("change_pct") is not None else ""
        lines.append(f"Tendance : {d}{pct}")
    if gem.reasons:
        lines.append("Raisons : " + " ; ".join(gem.reasons))
    if listing.url:
        lines.append(listing.url)
    return "\n".join(lines)


def _send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
            timeout=15,
        ).raise_for_status()
        return True
    except Exception as e:
        print(f"[alert] Telegram KO : {e}")
        return False


def _send_discord(text: str) -> bool:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        return False
    try:
        requests.post(url, json={"content": text[:1900]}, timeout=15).raise_for_status()
        return True
    except Exception as e:
        print(f"[alert] Discord KO : {e}")
        return False


def dispatch(listing, gem, comp: dict, trend: dict, push: bool = True) -> None:
    """Affiche l'alerte ; pousse sur Telegram/Discord si configuré et push=True."""
    text = format_alert(listing, gem, comp, trend)
    print("\n" + "=" * 60 + "\n" + text + "\n" + "=" * 60)
    if push:
        _send_telegram(text)
        _send_discord(text)
