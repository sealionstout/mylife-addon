"""BL101 connector — pulls live Shopify products.json, filters to youth
tees & shorts in the configured kids' sizes, flags sale vs new."""
import os, json, requests

DOMAIN = os.environ.get("BL101_DOMAIN", "www.bl101.com")
KIDS = json.loads(os.environ.get("KIDS_JSON", '[]')) or [
    {"name": "Brady", "size": "YL"}, {"name": "Beau", "size": "YM"}, {"name": "Logan", "size": "YS"}]
SIZE_TO_KID = {k["size"].upper(): k["name"] for k in KIDS}
FALLBACK = {"YL": "L", "YM": "M", "YS": "S"}
FALLBACK_TO_KID = {FALLBACK[k["size"].upper()]: k["name"] for k in KIDS if k["size"].upper() in FALLBACK}

ALLOWED = ("tee", "t-shirt", "tshirt", "shirt", "short")
EXCLUDE = ("underwear", "sock", "boxer", "brief", "long sleeve")

def _allowed_type(p):
    hay = (p.get("title", "") + " " + p.get("product_type", "")).lower()
    if any(x in hay for x in EXCLUDE): return False
    return any(k in hay for k in ALLOWED)

def _youth(p, tags):
    hay = (p.get("title", "") + " " + p.get("product_type", "") + " " + " ".join(tags)).lower()
    return any(w in hay for w in ("youth", "kid", "boys", "girls", "junior", "yth"))

def pull():
    r = requests.get(f"https://{DOMAIN}/products.json?limit=250", timeout=25,
                     headers={"User-Agent": "Mozilla/5.0 myLife/0.1"})
    r.raise_for_status()
    prods = r.json().get("products", [])
    items = []
    for p in prods:
        if not _allowed_type(p): continue
        tags = p.get("tags", [])
        if isinstance(tags, str): tags = [t.strip() for t in tags.split(",")]
        is_new = "new" in [t.lower() for t in tags]
        youth = _youth(p, tags)
        img = (p.get("images") or [{}])[0].get("src", "")
        handle = p.get("handle", "")
        for v in p.get("variants", []):
            if not v.get("available"): continue
            opts = {o.upper() for o in (v.get("option1"), v.get("option2"), v.get("option3")) if o}
            kid = matched = None
            for sz, name in SIZE_TO_KID.items():
                if sz in opts: kid, matched = name, sz; break
            if not kid and youth:
                for sz, name in FALLBACK_TO_KID.items():
                    if sz in opts: kid, matched = name, sz; break
            if not kid: continue
            try: price = float(v["price"])
            except (TypeError, ValueError): continue
            if price < 3: continue
            cmp_ = v.get("compare_at_price")
            on_sale = bool(cmp_) and float(cmp_) > price >= 3
            if not (on_sale or is_new): continue
            items.append({
                "title": p["title"], "kid": kid, "size": matched,
                "price": price, "compare_at": float(cmp_) if on_sale else None,
                "pct_off": round((1 - price/float(cmp_))*100) if on_sale else None,
                "status": "sale" if on_sale else "new",
                "image": img.split("?")[0] if img else "",
                "url": f"https://{DOMAIN}/products/{handle}"})
            break  # one variant per product
    counts = {"total": len(items),
              "sale": sum(1 for i in items if i["status"] == "sale"),
              "new": sum(1 for i in items if i["status"] == "new")}
    return {"items": items, "counts": counts, "source": DOMAIN}

if __name__ == "__main__":
    print(json.dumps(pull(), indent=2)[:2000])
