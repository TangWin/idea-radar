#!/usr/bin/env python3
"""Idea Radar static site generator. Usage: python3 build.py"""
import json, glob, os, re, html, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = "/workspace/idea-mining-*"
FIELDS = ["title", "problem", "target_users", "quotes", "existing", "defects", "solution", "mvp", "difficulty", "potential"]
ALIASES = {
    "title": ["title"], "problem": ["problem", "问题"],
    "target_users": ["target_users", "users", "目标用户"],
    "quotes": ["quotes", "用户原话"],
    "existing": ["existing_products", "existing", "已有产品"],
    "defects": ["competitor_defects", "defects", "existing_defects", "product_gaps", "gaps", "已有产品缺陷"],
    "solution": ["solution", "可能的产品方案"], "mvp": ["mvp", "MVP"],
    "difficulty": ["difficulty", "dev_difficulty", "开发难度"],
    "potential": ["potential", "commercial_potential", "business_potential", "商业潜力"],
}
MD_LABELS = [("problem", "问题"), ("target_users", "目标用户"), ("quotes", "用户原话"), ("defects", "已有产品缺陷|缺陷"),
             ("existing", "已有产品"), ("solution", "可能的产品方案|产品方案|方案"), ("mvp", "MVP"),
             ("difficulty", "开发难度"), ("potential", "商业潜力")]
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")

TAGS = [
    ("Agent/AI编码", r"agent|claude|codex|cursor|copilot|llm|编程|编码|coding|mcp|prompt|token"),
    ("开发者工具", r"开发者|cli|api|git|ssh|终端|terminal|部署|devops|vps|服务器|日志|代码|ide|自托管|self.?host"),
    ("支付/计费", r"支付|计费|订阅|账单|发票|定价|退款|billing|stripe|invoice|费用"),
    ("增长/转化", r"增长|转化|获客|冷邮|分发|seo|营销|落地页|distribution|marketing|首批|推广"),
    ("Mac/桌面工具", r"mac|macos|桌面|菜单栏|touch id|windows|浏览器扩展|chrome"),
    ("语言学习", r"语言学习|外语|英语|学习者|词汇|可懂输入|language|english"),
    ("安全", r"安全|隐私|密码|凭证|creds|爬虫|恶意|security|加密|锁"),
    ("电商", r"电商|shopify|商家|店铺|商品|目录|sku|amazon|采购|库存"),
    ("运营/客服", r"客服|运营|询盘|收件箱|工单|催收|会计|行政|support|inbox|事务所"),
    ("消费者", r"家庭|家人|照片|iphone|手机|键盘|木工|diy|求职|面试|约会|个人|生活"),
]

def first(d, keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return None

def score(v):
    if isinstance(v, int): return v
    m = re.search(r"([1-5])\s*/\s*5", str(v or "")) or re.search(r"\b([1-5])\b", str(v or ""))
    return int(m.group(1)) if m else None

def norm_quotes(v):
    out = []
    for q in v or []:
        if isinstance(q, str):
            links = [{"label": a, "url": u} for a, u in LINK.findall(q)]
            out.append({"text": LINK.sub(lambda m: m.group(1), q).strip(), "links": links})
        elif isinstance(q, dict):
            t = first(q, ["text", "quote", "原话", "content"]) or ""
            u = first(q, ["url", "link", "source_url"])
            lab = first(q, ["source", "src", "label"]) or "来源"
            out.append({"text": t, "links": [{"label": str(lab), "url": u}] if u else []})
    return [q for q in out if q["text"]]

def to_text(v):
    if v is None: return None
    if isinstance(v, list): return "、".join(map(str, v))
    return str(v).strip() or None

def parse_md(text):
    sample = None
    for line in text.splitlines()[:8]:
        if "样本" in line:
            sample = re.sub(r"^[#\s]*", "", line).strip(); break
    blocks = re.split(r"^#{2,3}\s*(\d)\.\s*", text, flags=re.M)
    ideas = []
    for i in range(1, len(blocks) - 1, 2):
        rank, body = int(blocks[i]), blocks[i + 1]
        lines = body.split("\n")
        idea = {"rank": rank, "title": lines[0].strip().strip("[]").strip()}
        cur = None
        for ln in lines[1:]:
            if re.match(r"^#", ln): break
            m = re.match(r"^- \s*([^：:]{1,10})[：:]\s*(.*)$", ln)
            if m:
                lab, val = m.group(1).strip(), m.group(2).strip()
                cur = None
                for key, pat in MD_LABELS:
                    if re.fullmatch(pat, lab):
                        cur = key; break
                if cur in ("difficulty", "potential"):
                    idea[cur] = score(val)
                    m2 = re.search(r"商业潜力[：:]\s*([1-5])", val)
                    if m2: idea["potential"] = int(m2.group(1))
                    cur = None
                elif cur == "quotes":
                    idea["quotes"] = [val] if val else []
                elif cur:
                    idea[cur] = val
                continue
            sm = re.match(r"^\s+[-*]\s+(.*)$", ln)
            if sm and cur == "quotes":
                idea["quotes"].append(sm.group(1).strip())
            elif sm and cur and cur in idea:
                idea[cur] += "；" + sm.group(1).strip()
        if "quotes" in idea: idea["quotes"] = norm_quotes(idea["quotes"])
        ideas.append(idea)
    return sample, ideas

def json_ideas(d):
    if isinstance(d, list): return d
    for k in ("top5", "ideas", "items"):
        if isinstance(d.get(k), list): return d[k]
    return []

def sample_from_json(d):
    if not isinstance(d, dict): return None
    c = first(d, ["sample_counts", "counts", "samples"])
    tot = d.get("sample_total")
    if isinstance(c, dict):
        nums = {k: v for k, v in c.items() if isinstance(v, int)}
        s = " / ".join(f"{k} {v}" for k, v in nums.items())
        return f"样本 {tot} 条（{s}）" if tot else f"样本：{s}"
    return f"样本 {tot} 条" if tot else None

def load_day(dirpath):
    date = dirpath.rsplit("idea-mining-", 1)[1]
    md_sample, md_ideas = None, []
    if os.path.exists(f"{dirpath}/top5.md"):
        md_sample, md_ideas = parse_md(open(f"{dirpath}/top5.md", encoding="utf-8").read())
    jd, ji = None, []
    if os.path.exists(f"{dirpath}/top5.json"):
        try:
            jd = json.load(open(f"{dirpath}/top5.json", encoding="utf-8")); ji = json_ideas(jd)
        except Exception as e:
            print(f"[warn] {date}: bad json {e}", file=sys.stderr)
    n = max(len(ji), len(md_ideas))
    ideas = []
    for i in range(n):
        j = ji[i] if i < len(ji) and isinstance(ji[i], dict) else {}
        if j.get("markdown"):
            _, emb = parse_md("## 1. " + re.sub(r"^#{2,3}\s*\d\.\s*", "", j["markdown"].lstrip()))
            jm = emb[0] if emb else {}
        else: jm = {}
        rank = j.get("rank") or i + 1
        m = next((x for x in md_ideas if x["rank"] == rank), md_ideas[i] if i < len(md_ideas) else {})
        idea = {"rank": rank}
        for f in FIELDS:
            v = first(j, ALIASES[f])
            if f == "title" and v is None: v = first(j, ["problem", "问题"])
            if f == "quotes": v = norm_quotes(v) if v else None
            elif f in ("difficulty", "potential"): v = score(v) if v is not None else None
            elif f != "title": v = to_text(v)
            if v in (None, "", []): v = jm.get(f) or m.get(f)
            if v not in (None, "", []): idea[f] = v
        if "title" in idea: idea["title"] = idea["title"].strip("[]")
        if not idea.get("quotes") and j.get("sources"):
            idea["quotes"] = []  # sources only; keep as links
            idea["sources"] = j["sources"]
        idea["tags"] = tag(idea)
        ideas.append(idea)
    sample = md_sample or sample_from_json(jd)
    return {"date": date, "sample": sample, "ideas": ideas}

def tag(idea):
    blob = " ".join(str(idea.get(k, "")) for k in ("title", "problem", "target_users", "solution", "mvp")).lower()
    tblob = str(idea.get("title", "")).lower()
    scored = []
    for name, pat in TAGS:
        hits = len(re.findall(pat, blob)) + 3 * len(re.findall(pat, tblob))
        if hits: scored.append((hits, name))
    scored.sort(key=lambda x: -x[0])
    return [n for _, n in scored[:3]] or ["其他"]

def short(s, n):
    s = re.sub(r"\s+", " ", s or "")
    return s if len(s) <= n else s[:n].rstrip() + "…"

def pain(idea):
    p = idea.get("problem")
    if p: return short(re.split(r"(?<=[。！？])", p)[0], 70)
    t = idea.get("title", "")
    return short(t.split("：", 1)[1], 70) if "：" in t else None

def short_title(t):
    t = re.split(r"[：:]", t, maxsplit=1)[0] if len(t) > 26 else t
    return short(t, 30)

E = lambda s: html.escape(str(s), quote=True)

CSS = """:root{color-scheme:light dark;--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--mut:#6b7280;--line:#e5e7eb;--acc:#4f46e5;--chip:#eef2ff}
@media(prefers-color-scheme:dark){:root{--bg:#0f1117;--card:#181b24;--fg:#e6e8ee;--mut:#9aa1ae;--line:#2a2f3c;--acc:#8b8cf8;--chip:#252a3d}}
*{box-sizing:border-box}body{margin:0;font:15px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Noto Sans SC","Segoe UI",sans-serif;background:var(--bg);color:var(--fg)}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:860px;margin:0 auto;padding:20px 16px 60px}header h1{margin:0;font-size:24px}header p{margin:4px 0 16px;color:var(--mut)}
.search{width:100%;padding:11px 14px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--fg);font-size:15px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 18px}.chip{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:999px;padding:4px 11px;font-size:13px;cursor:pointer}
.chip.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.day{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:12px}.day h2{margin:0 0 6px;font-size:17px}
.day ol{margin:0;padding-left:20px}.day li{margin:3px 0}.day li.hide{display:none}.day.hide{display:none}
.tag{display:inline-block;font-size:11.5px;background:var(--chip);color:var(--acc);border-radius:6px;padding:1px 7px;margin:0 4px 0 0;white-space:nowrap}
.b{display:inline-block;font-size:12px;border-radius:6px;padding:1px 7px;margin-right:4px;border:1px solid var(--line);color:var(--mut);white-space:nowrap}
.meta{color:var(--mut);font-size:13px}
.nav{display:flex;justify-content:space-between;gap:8px;margin:10px 0 16px;font-size:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;margin-bottom:12px;overflow:hidden}
.card>summary{list-style:none;cursor:pointer;padding:14px 16px;display:grid;grid-template-columns:38px 1fr;gap:4px 10px}.card>summary::-webkit-details-marker{display:none}
.rank{grid-row:span 3;width:34px;height:34px;border-radius:10px;background:var(--acc);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700}
.t{font-weight:650;font-size:16px}.pain{color:var(--mut);font-size:14px}
.card[open]>summary{border-bottom:1px solid var(--line)}.body{padding:12px 16px 16px}
.full{font-size:13px;color:var(--mut);margin-bottom:8px}
.sec{margin:10px 0}.sec h4{margin:0 0 3px;font-size:12.5px;letter-spacing:.04em;color:var(--mut);text-transform:uppercase}.sec p{margin:0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:600px){.grid{grid-template-columns:1fr}}
.box{background:var(--bg);border-radius:10px;padding:10px 12px}
details.q{margin-top:12px}details.q>summary{cursor:pointer;color:var(--acc);font-size:14px}
blockquote{margin:8px 0;padding:6px 12px;border-left:3px solid var(--acc);background:var(--bg);border-radius:0 8px 8px 0;font-size:14px}
blockquote .src{display:block;font-size:12px;margin-top:3px}
.empty{color:var(--mut);text-align:center;padding:30px}"""

def page(title, body, rel=""):
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title><link rel="stylesheet" href="{rel}style.css"></head><body><div class="wrap">{body}</div></body></html>"""

def badges(i):
    s = ""
    if i.get("difficulty"): s += f'<span class="b">难度 {i["difficulty"]}/5</span>'
    if i.get("potential"): s += f'<span class="b">潜力 {i["potential"]}/5</span>'
    return s

def render_day(day, prev, nxt):
    nav = '<div class="nav"><span>' + (f'<a href="{prev}.html">← {prev}</a>' if prev else "") + '</span><a href="../index.html">全部日期</a><span>' + (f'<a href="{nxt}.html">{nxt} →</a>' if nxt else "") + "</span></div>"
    cards = []
    for i in day["ideas"]:
        tags = "".join(f'<span class="tag">{E(t)}</span>' for t in i["tags"])
        p = pain(i)
        sec = lambda h, k: f'<div class="sec box"><h4>{h}</h4><p>{E(i[k])}</p></div>' if i.get(k) else ""
        body = ""
        if i.get("title") and short_title(i["title"]) != i["title"]: body += f'<div class="full">{E(i["title"])}</div>'
        if i.get("problem"): body += sec("问题", "problem")
        body += sec("目标用户", "target_users")
        g = sec("已有产品", "existing") + sec("缺陷", "defects")
        if g: body += f'<div class="grid">{g}</div>'
        g = sec("方案", "solution") + sec("MVP", "mvp")
        if g: body += f'<div class="grid">{g}</div>'
        qs = ""
        for q in i.get("quotes") or []:
            links = " · ".join(f'<a href="{E(l["url"])}" target="_blank" rel="noopener">{E(l["label"])} ↗</a>' for l in q["links"])
            qs += f'<blockquote>{E(q["text"])}{f"<span class=src>{links}</span>" if links else ""}</blockquote>'
        for u in i.get("sources") or []:
            qs += f'<blockquote><a href="{E(u)}" target="_blank" rel="noopener">{E(short(u, 70))} ↗</a></blockquote>'
        if qs:
            n = len(i.get("quotes") or i.get("sources") or [])
            label = "Original quotes" if i.get("quotes") else "Sources"
            body += f'<details class="q"><summary>{label} ({n})</summary>{qs}</details>'
        cards.append(f'''<details class="card" id="i{i["rank"]}"><summary><div class="rank">{i["rank"]}</div>
<div class="t">{E(short_title(i.get("title", "")))}</div>{f'<div class="pain">{E(p)}</div>' if p else '<div></div>'}<div>{badges(i)}{tags}</div></summary>
<div class="body">{body}</div></details>''')
    head = f'<header><h1>{day["date"]} · Top {len(day["ideas"])}</h1>' + (f'<p>{E(day["sample"])}</p>' if day["sample"] else "<p></p>") + "</header>"
    return page(f'{day["date"]} · Idea Radar', head + nav + "".join(cards) + nav, "../")

JS = r"""const D=window.IDEAS;let tag=null;const q=document.getElementById('q');
function run(){const s=q.value.trim().toLowerCase();let any=0;
document.querySelectorAll('.day').forEach(d=>{let n=0;d.querySelectorAll('li').forEach(li=>{const it=D[li.dataset.k];
const ok=(!s||it.blob.includes(s))&&(!tag||it.tags.includes(tag));li.classList.toggle('hide',!ok);if(ok)n++});d.classList.toggle('hide',!n);any+=n});
document.getElementById('empty').style.display=any?'none':'block'}
q.addEventListener('input',run);document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{tag=tag===c.dataset.t?null:c.dataset.t;
document.querySelectorAll('.chip').forEach(x=>x.classList.toggle('on',x.dataset.t===tag));run()});"""

def render_index(days):
    allidx, rows, counts = {}, [], {}
    for d in days:
        lis = ""
        for i in d["ideas"]:
            k = f'{d["date"]}-{i["rank"]}'
            blob = " ".join([i.get("title", ""), i.get("problem", ""), i.get("target_users", ""), i.get("existing", ""), i.get("solution", ""), i.get("mvp", "")]
                            + [q["text"] for q in i.get("quotes") or []]).lower()
            allidx[k] = {"tags": i["tags"], "blob": blob}
            for t in i["tags"]: counts[t] = counts.get(t, 0) + 1
            tags = "".join(f'<span class="tag">{E(t)}</span>' for t in i["tags"])
            lis += f'<li data-k="{k}"><a href="days/{d["date"]}.html#i{i["rank"]}">{E(short_title(i.get("title", "")))}</a> {badges(i)}{tags}</li>'
        rows.append(f'<section class="day"><h2><a href="days/{d["date"]}.html">{d["date"]}</a></h2>'
                    + (f'<div class="meta">{E(short(d["sample"], 90))}</div>' if d["sample"] else "") + f"<ol>{lis}</ol></section>")
    chips = "".join(f'<button class="chip" data-t="{E(t)}">{E(t)} · {c}</button>' for t, c in sorted(counts.items(), key=lambda x: -x[1]))
    n = sum(len(d["ideas"]) for d in days)
    body = (f'<header><h1>Idea Radar</h1><p>每日产品 Idea Top 5 · {len(days)} 天 · {n} 个想法</p></header>'
            '<input id="q" class="search" type="search" placeholder="搜索全部想法、用户原话…">'
            f'<div class="chips">{chips}</div>' + "".join(rows) + '<div id="empty" class="empty" style="display:none">没有匹配的想法</div>'
            f'<script>window.IDEAS={json.dumps(allidx, ensure_ascii=False)}</script><script>{JS}</script>')
    return page("Idea Radar · 每日产品 Idea Top 5", body)

def main():
    os.makedirs(f"{ROOT}/data", exist_ok=True); os.makedirs(f"{ROOT}/days", exist_ok=True)
    days, failed = [], []
    for dp in sorted(glob.glob(SRC)):
        if not os.path.isdir(dp) or not re.search(r"\d{4}-\d{2}-\d{2}$", dp): continue
        try:
            d = load_day(dp)
            if not d["ideas"]: raise ValueError("no ideas parsed")
            days.append(d)
            json.dump(d, open(f'{ROOT}/data/{d["date"]}.json', "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception as e:
            failed.append((dp, str(e))); print(f"[fail] {dp}: {e}", file=sys.stderr)
    days.sort(key=lambda d: d["date"])
    for k, d in enumerate(days):
        prev = days[k - 1]["date"] if k else None
        nxt = days[k + 1]["date"] if k + 1 < len(days) else None
        open(f'{ROOT}/days/{d["date"]}.html', "w", encoding="utf-8").write(render_day(d, prev, nxt))
    days.reverse()
    open(f"{ROOT}/index.html", "w", encoding="utf-8").write(render_index(days))
    open(f"{ROOT}/style.css", "w").write(CSS)
    open(f"{ROOT}/.nojekyll", "w").write("")
    print(f"built {len(days)} days, {sum(len(d['ideas']) for d in days)} ideas; failed: {len(failed)}")
    for f, e in failed: print("  failed:", f, e)

if __name__ == "__main__":
    main()
