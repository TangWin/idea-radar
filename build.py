#!/usr/bin/env python3
"""Idea Radar static site generator. Usage: python3 build.py"""
import json, glob, os, re, html, sys, unicodedata

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

TAGS = [  # English terms are word-bounded (\b) to avoid hits like "git" in "digital", "ide" in "idea"
    ("Agent/AI编码", r"\b(?:agents?|agentic|claude|codex|cursor|copilot|llms?|mcp|prompts?|vibe.?cod\w*|coding)\b|编程|编码|提示词|token"),
    ("开发者工具", r"\b(?:cli|apis?|git|github|ssh|terminal|devops|vps|ide|self.?host\w*|sdk|webhooks?)\b|开发者|终端|部署|服务器|日志|代码|自托管"),
    ("支付/计费", r"\b(?:billing|stripe|invoices?|pricing|refunds?)\b|支付|计费|订阅|账单|发票|定价|退款|费用|收入"),
    ("增长/转化", r"\b(?:seo|marketing|distribution|growth)\b|增长|转化|获客|冷邮|分发|营销|落地页|首批|推广|激活"),
    ("Mac/桌面工具", r"\b(?:mac|macos|macbook|touch id|menu ?bar)\b|桌面|菜单栏|windows ?(?:应用|客户端|app)"),
    ("语言学习", r"\b(?:language learning|duolingo|vocabulary)\b|语言学习|外语|英语|学习者|词汇|可懂输入"),
    ("安全/隐私", r"\b(?:security|privacy|secrets?|creds|malware)\b|安全|隐私|密码|凭证|密钥|恶意|加密|爬虫"),
    ("电商", r"\b(?:shopify|sku|amazon|etsy|e-?commerce)\b|电商|商家|店铺|商品|采购|库存|市集"),
    ("运营/客服", r"\b(?:support|inbox|helpdesk|crm)\b|客服|运营|询盘|收件箱|工单|催收|催款|会计|行政|事务所"),
    ("个人/生活", r"\b(?:iphone|diy|family)\b|家庭|家人|照片|手机|键盘|木工|求职|面试|约会|生活"),
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
        if "title" in idea: idea["title"] = re.sub(r"^\s*\d+[.、]\s*", "", str(idea["title"]).strip().strip("[]")).strip()
        try: idea["rank"] = int(idea["rank"])
        except (TypeError, ValueError): idea["rank"] = i + 1
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
    """One-line pain for the collapsed card. Returns (text, kind): kind 'p' = problem,
    't' = from title after colon, 'q' = first user quote (verbatim). Never invents text."""
    t = idea.get("title", "")
    p = idea.get("problem")
    if p:
        first_s = re.split(r"(?<=[。！？!?])", p)[0].strip()
        if first_s and first_s != t.strip():
            return short(first_s, 70), "p"
    m = re.split(r"[：:]", t, maxsplit=1)
    if len(m) == 2 and m[1].strip():
        return short(m[1].strip(), 70), "t"
    qs = idea.get("quotes") or []
    if qs and qs[0].get("text"):
        return short(qs[0]["text"].strip().strip("「」“”\"'"), 80), "q"
    return None, None

def short_title(t):
    parts = re.split(r"[：:]", t, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and len(t) > 22: t = parts[0]
    return short(t.strip(), 32)

def safe_url(u):
    u = str(u or "").strip()
    return u if re.match(r"^https?://", u, re.I) else None

E = lambda s: html.escape(str(s), quote=True)

CSS = """:root{color-scheme:light dark;--bg:#f5f6f8;--card:#fff;--fg:#1b2130;--mut:#5b6474;--line:#e3e6eb;--acc:#4338ca;--acc2:#eef0ff;--box:#f7f8fa;
--g:#15803d;--gb:#dcfce7;--y:#a16207;--yb:#fef3c7;--r:#b91c1c;--rb:#fee2e2;--focus:#2563eb}
@media(prefers-color-scheme:dark){:root{--bg:#0e1016;--card:#171a22;--fg:#e7e9ef;--mut:#a3aab8;--line:#2a2f3b;--acc:#a5b4fc;--acc2:#23284a;--box:#1e222c;
--g:#86efac;--gb:#14321f;--y:#fcd34d;--yb:#3a2e0f;--r:#fca5a5;--rb:#3b1515;--focus:#93c5fd}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scroll-padding-top:12px}
body{margin:0;font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Noto Sans CJK SC","Noto Sans SC","Microsoft YaHei","Segoe UI",sans-serif;background:var(--bg);color:var(--fg);overflow-wrap:anywhere}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px;border-radius:6px}
.skip{position:absolute;left:-999px}.skip:focus{left:8px;top:8px;background:var(--card);padding:6px 10px;z-index:9}
.wrap{max-width:860px;margin:0 auto;padding:20px 14px 64px}header h1{margin:0;font-size:24px;line-height:1.3}header p{margin:4px 0 14px;color:var(--mut);font-size:14px}
.search{width:100%;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--fg);font-size:16px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 6px}.chip{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:999px;padding:5px 12px;font-size:13px;cursor:pointer;min-height:32px}
.chip[aria-pressed=true]{background:var(--acc);color:var(--card);border-color:var(--acc)}
.stat{color:var(--mut);font-size:13px;margin:6px 0 14px;min-height:1.2em}
.day{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin-bottom:12px}.day h2{margin:0 0 4px;font-size:17px}
.day ol{list-style:none;margin:0;padding:0}.day li{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;padding:7px 0;border-top:1px dashed var(--line)}
.day li:first-child{border-top:0}.day li>a{font-weight:600;flex:1 1 220px}.hide{display:none!important}
.n{display:inline-flex;width:22px;height:22px;border-radius:7px;background:var(--acc2);color:var(--acc);font-size:12px;font-weight:700;align-items:center;justify-content:center;flex:none}
.tags{display:inline-flex;flex-wrap:wrap;gap:4px}
.tag{display:inline-block;font-size:12px;line-height:1.6;background:var(--acc2);color:var(--acc);border-radius:6px;padding:0 7px;white-space:nowrap}
.sc{display:inline-flex;align-items:center;gap:4px;font-size:12px;line-height:1.6;border-radius:6px;padding:0 7px;white-space:nowrap}
.sc i{display:inline-flex;gap:2px}.sc i b{width:7px;height:7px;border-radius:50%;background:currentColor;opacity:.25}.sc i b.on{opacity:1}
.lv-g{background:var(--gb);color:var(--g)}.lv-y{background:var(--yb);color:var(--y)}.lv-r{background:var(--rb);color:var(--r)}
.meta{color:var(--mut);font-size:13px}
.nav{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:10px 0 14px;font-size:14px}
.nav>*{flex:1}.nav .c{text-align:center}.nav .r{text-align:right}
.tools{display:flex;gap:8px;margin-bottom:10px}.tools button{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:8px;padding:4px 10px;cursor:pointer}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;margin-bottom:12px;overflow:hidden}
.card.hl{border-color:var(--acc);box-shadow:0 0 0 2px var(--acc2)}
.card>summary{list-style:none;cursor:pointer;padding:14px;display:grid;grid-template-columns:36px 1fr auto;gap:4px 10px;align-items:start}.card>summary::-webkit-details-marker{display:none}
.rank{grid-row:span 3;width:34px;height:34px;border-radius:10px;background:var(--acc);color:var(--card);display:flex;align-items:center;justify-content:center;font-weight:700}
.chev{color:var(--mut);transition:transform .15s;font-size:20px;line-height:1}.card[open] .chev{transform:rotate(90deg)}
.t{font-weight:700;font-size:17px;line-height:1.45}.pain{color:var(--mut);font-size:14.5px;line-height:1.6;grid-column:2/4}.pain .k{font-size:12px;margin-right:4px}
.row{grid-column:2/4;display:flex;flex-wrap:wrap;gap:4px 6px;align-items:center}
.card[open]>summary{border-bottom:1px solid var(--line)}.body{padding:12px 14px 16px}
.full{font-size:14px;color:var(--mut);margin-bottom:8px}
.sec{margin:8px 0}.sec h3{margin:0 0 2px;font-size:13px;color:var(--mut);font-weight:600}.sec p{margin:0;font-size:15px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
@media(max-width:640px){.grid{grid-template-columns:1fr}.card>summary{grid-template-columns:30px 1fr auto}.rank{width:28px;height:28px;border-radius:8px}}
.box{background:var(--box);border-radius:10px;padding:9px 12px}
.sec ul{margin:2px 0 0;padding-left:18px}.sec li{margin:1px 0}
details.q{margin-top:12px}details.q>summary{cursor:pointer;color:var(--acc);font-size:14px;padding:4px 0}
blockquote{margin:8px 0;padding:6px 12px;border-left:3px solid var(--acc);background:var(--box);border-radius:0 8px 8px 0;font-size:14px}
blockquote .src{display:block;font-size:12.5px;margin-top:3px}
.empty{color:var(--mut);text-align:center;padding:30px}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}"""

def page(title, body, rel=""):
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<meta name="color-scheme" content="light dark"><title>{E(title)}</title><link rel="stylesheet" href="{rel}style.css"></head>'
            f'<body><a class="skip" href="#main">跳到正文</a><main class="wrap" id="main">{body}</main></body></html>')

def meter(label, v, invert):
    """Score pill with 5 dots. invert=True: higher is worse (difficulty)."""
    if not isinstance(v, int) or not 1 <= v <= 5: return ""
    good = 6 - v if invert else v
    lv = "g" if good >= 4 else ("y" if good == 3 else "r")
    dots = "".join('<b class="on"></b>' if k < v else "<b></b>" for k in range(5))
    return f'<span class="sc lv-{lv}" title="{label} {v}/5"><span>{label}</span><i aria-hidden="true">{dots}</i><span>{v}/5</span></span>'

def badges(i):
    return meter("难度", i.get("difficulty"), True) + meter("潜力", i.get("potential"), False)

def tag_html(tags):
    return '<span class="tags">' + "".join(f'<span class="tag">{E(t)}</span>' for t in tags) + "</span>"

def split_items(v):
    parts = [x.strip(" ；;、。") for x in re.split(r"[；;]|、", v) if x.strip(" ；;、。")]
    return parts if 2 <= len(parts) <= 12 and all(len(x) <= 60 for x in parts) else None

DAY_JS = """<script>(function(){const C=[...document.querySelectorAll('details.card')];
function go(){const h=decodeURIComponent(location.hash.slice(1));const el=h&&document.getElementById(h);C.forEach(c=>c.classList.remove('hl'));
if(el&&el.matches('details.card')){el.open=true;el.classList.add('hl');el.scrollIntoView({block:'start'})}}
addEventListener('hashchange',go);go();
document.getElementById('ex').onclick=()=>C.forEach(c=>c.open=true);document.getElementById('co').onclick=()=>C.forEach(c=>c.open=false);
document.addEventListener('keydown',e=>{if(e.target.closest('input,textarea')||e.metaKey||e.ctrlKey||e.altKey)return;
const a=e.key==='ArrowLeft'?document.querySelector('a[rel=prev]'):e.key==='ArrowRight'?document.querySelector('a[rel=next]'):null;if(a)location.href=a.href})})()</script>"""

def render_day(day, prev, nxt):
    nav = ('<nav class="nav" aria-label="日期导航">' + (f'<a href="{prev}.html" rel="prev">← {prev}</a>' if prev else "<span></span>")
           + '<a class="c" href="../index.html">全部日期</a>'
           + (f'<a class="r" href="{nxt}.html" rel="next">{nxt} →</a>' if nxt else '<span class="r"></span>') + "</nav>")
    cards = []
    for i in day["ideas"]:
        p, kind = pain(i)
        def sec(h, k):
            v = i.get(k)
            if not v: return ""
            items = split_items(v) if k in ("existing", "defects") else None
            inner = ("<ul>" + "".join(f"<li>{E(x)}</li>" for x in items) + "</ul>") if items else f"<p>{E(v)}</p>"
            return f'<div class="sec box"><h3>{h}</h3>{inner}</div>'
        body = ""
        title = i.get("title", "")
        if title and short_title(title) != title: body += f'<div class="full">{E(title)}</div>'
        if i.get("problem") and not (kind == "p" and i["problem"].strip() == (p or "")):
            if i["problem"].strip() != title.strip(): body += sec("😣 痛点", "problem")
        body += sec("👥 目标用户", "target_users")
        g = sec("🏷 已有产品", "existing") + sec("🕳 缺口", "defects")
        if g: body += f'<div class="grid">{g}</div>'
        g = sec("💡 方案", "solution") + sec("🚀 MVP", "mvp")
        if g: body += f'<div class="grid">{g}</div>'
        qs = ""
        for q in i.get("quotes") or []:
            links = " · ".join(f'<a href="{E(u)}" target="_blank" rel="noopener noreferrer">{E(l.get("label") or "来源")} ↗</a>'
                               for l in q.get("links") or [] if (u := safe_url(l.get("url"))))
            qs += f'<blockquote>{E(q["text"])}' + (f'<span class="src">{links}</span>' if links else "") + "</blockquote>"
        srcs = [u for u in (safe_url(x if isinstance(x, str) else (x or {}).get("url")) for x in i.get("sources") or []) if u]
        for u in srcs:
            qs += f'<blockquote><a href="{E(u)}" target="_blank" rel="noopener noreferrer">{E(short(u, 70))} ↗</a></blockquote>'
        if qs:
            n = len(i.get("quotes") or []) or len(srcs)
            label = "💬 用户原话" if i.get("quotes") else "🔗 来源"
            body += f'<details class="q"><summary>{label}（{n}）· 展开</summary>{qs}</details>'
        pk = '<span class="k" title="无痛点字段，显示首条用户原话">💬</span>' if kind == "q" else ""
        pain_html = f'<span class="pain">{pk}{E(p)}</span>' if p else ""
        r = i["rank"]
        cards.append(f'<details class="card" id="i{r}"><summary><span class="rank" aria-label="第{r}名">{r}</span>'
                     f'<span class="t">{E(short_title(title) or "（无标题）")}</span><span class="chev" aria-hidden="true">›</span>'
                     f'{pain_html}<span class="row">{badges(i)}{tag_html(i["tags"])}</span></summary>\n'
                     f'<div class="body">{body or "<p class=meta>源数据没有更多字段</p>"}<p class="meta"><a href="#i{r}">🔗 本条链接</a></p></div></details>\n')
    head = f'<header><h1>{day["date"]} · Top {len(day["ideas"])}</h1>' + (f'<p>{E(day["sample"])}</p>' if day["sample"] else "") + "</header>"
    tools = '<div class="tools"><button type="button" id="ex">全部展开</button><button type="button" id="co">全部收起</button></div>'
    return page(f'{day["date"]} · Idea Radar', head + nav + tools + "".join(cards) + nav + DAY_JS, "../")

JS = r"""(function(){const D=window.IDEAS;let tag=null;const q=document.getElementById('q'),st=document.getElementById('stat');
const N=s=>s.normalize('NFKC').toLowerCase();
function run(push){const terms=N(q.value).trim().split(/\s+/).filter(Boolean);let any=0;
document.querySelectorAll('.day').forEach(d=>{let n=0;d.querySelectorAll('li').forEach(li=>{const it=D[li.dataset.k];
const ok=terms.every(t=>it.blob.includes(t))&&(!tag||it.tags.includes(tag));li.classList.toggle('hide',!ok);if(ok)n++});d.classList.toggle('hide',!n);any+=n});
document.getElementById('empty').classList.toggle('hide',!!any);
st.textContent=(terms.length||tag)?`匹配 ${any} 个想法`:'';
if(push){const u=new URLSearchParams();if(q.value.trim())u.set('q',q.value.trim());if(tag)u.set('tag',tag);
history.replaceState(null,'',u.toString()?'?'+u:location.pathname)}}
function setTag(t){tag=t;document.querySelectorAll('.chip').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.t===tag)))}
q.addEventListener('input',()=>run(1));
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{setTag(tag===c.dataset.t?null:c.dataset.t);run(1)});
const P=new URLSearchParams(location.search);if(P.get('q'))q.value=P.get('q');if(P.get('tag'))setTag(P.get('tag'));run(0);
document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement!==q){e.preventDefault();q.focus()}else if(e.key==='Escape'&&document.activeElement===q){q.value='';run(1)}})})()"""

def render_index(days):
    allidx, rows, counts = {}, [], {}
    for d in days:
        lis = ""
        for i in d["ideas"]:
            k = f'{d["date"]}-{i["rank"]}'
            parts = [d["date"], i.get("title", ""), i.get("problem", ""), i.get("target_users", ""), i.get("existing", ""), i.get("defects", ""),
                     i.get("solution", ""), i.get("mvp", ""), " ".join(i["tags"])] + [q["text"] for q in i.get("quotes") or []]
            blob = unicodedata.normalize("NFKC", " ".join(map(str, parts))).lower()
            allidx[k] = {"tags": i["tags"], "blob": blob}
            for t in i["tags"]: counts[t] = counts.get(t, 0) + 1
            p, _ = pain(i)
            tip = f' title="{E(p)}"' if p else ""
            lis += (f'<li data-k="{E(k)}"><span class="n">{i["rank"]}</span><a href="days/{d["date"]}.html#i{i["rank"]}"{tip}>{E(short_title(i.get("title", "")))}</a>'
                    f'{badges(i)}{tag_html(i["tags"])}</li>\n')
        rows.append(f'<section class="day" aria-labelledby="d{d["date"]}"><h2 id="d{d["date"]}"><a href="days/{d["date"]}.html">{d["date"]}</a></h2>'
                    + (f'<div class="meta">{E(short(d["sample"], 90))}</div>' if d["sample"] else "") + f"<ol>{lis}</ol></section>\n")
    chips = "".join(f'<button type="button" class="chip" aria-pressed="false" data-t="{E(t)}">{E(t)} · {c}</button>'
                    for t, c in sorted(counts.items(), key=lambda x: (-x[1], x[0])))
    n = sum(len(d["ideas"]) for d in days)
    data = json.dumps(allidx, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    body = (f'<header><h1>📡 Idea Radar</h1><p>每日产品 Idea Top 5 · {len(days)} 天 · {n} 个想法 · 难度点越少越容易，潜力点越多越好</p></header>'
            '<label for="q" class="skip">搜索</label><input id="q" class="search" type="search" placeholder="搜索标题、痛点、用户、竞品、原话…（空格=同时包含）" autocomplete="off">'
            f'<div class="chips" role="group" aria-label="按标签筛选">{chips}</div><div id="stat" class="stat" aria-live="polite"></div>' + "".join(rows)
            + '<div id="empty" class="empty hide">没有匹配的想法</div>'
            f'<script>window.IDEAS={data}</script><script>{JS}</script>')
    return page("Idea Radar · 每日产品 Idea Top 5", body)

def failed_dates(failed, f):
    """Keep the last good page for a day whose source failed to parse this run."""
    b = os.path.basename(f).rsplit(".", 1)[0]
    return any(dp.endswith(b) for dp, _ in failed)


def main():
    os.makedirs(f"{ROOT}/data", exist_ok=True); os.makedirs(f"{ROOT}/days", exist_ok=True)
    days, failed = [], []
    for dp in sorted(glob.glob(SRC)):
        if not os.path.isdir(dp) or not re.search(r"\d{4}-\d{2}-\d{2}$", dp): continue
        try:
            d = load_day(dp)
            if not d["ideas"]: raise ValueError("no ideas parsed")
            days.append(d)
            with open(f'{ROOT}/data/{d["date"]}.json', "w", encoding="utf-8") as fh: json.dump(d, fh, ensure_ascii=False, indent=1)
        except Exception as e:
            failed.append((dp, str(e))); print(f"[fail] {dp}: {e}", file=sys.stderr)
    days.sort(key=lambda d: d["date"])
    for k, d in enumerate(days):
        prev = days[k - 1]["date"] if k else None
        nxt = days[k + 1]["date"] if k + 1 < len(days) else None
        open(f'{ROOT}/days/{d["date"]}.html', "w", encoding="utf-8").write(render_day(d, prev, nxt))
    days.reverse()
    open(f"{ROOT}/index.html", "w", encoding="utf-8").write(render_index(days))
    open(f"{ROOT}/style.css", "w", encoding="utf-8").write(CSS)
    keep = {d["date"] for d in days}
    for sub, ext in (("data", "json"), ("days", "html")):  # drop pages whose source dir disappeared
        for f in glob.glob(f"{ROOT}/{sub}/*.{ext}"):
            if os.path.basename(f).rsplit(".", 1)[0] not in keep and not failed_dates(failed, f): os.remove(f)
    open(f"{ROOT}/.nojekyll", "w").write("")
    print(f"built {len(days)} days, {sum(len(d['ideas']) for d in days)} ideas; failed: {len(failed)}")
    for f, e in failed: print("  failed:", f, e)

if __name__ == "__main__":
    main()
