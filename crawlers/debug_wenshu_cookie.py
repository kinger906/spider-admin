import os, json, time
from dotenv import load_dotenv
load_dotenv()
import requests
from framework.wenshu_crypto import make_ciphertext, make_page_id, make_token, decrypt, today_iv

cookie = os.environ.get("WENSHU_COOKIE", "")
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"})
if cookie:
    s.headers["Cookie"] = cookie

print("1) GET homepage")
r = s.get("https://wenshu.court.gov.cn/", timeout=30)
print("status", r.status_code, "cookies", {c.name: c.value[:20]+"..." for c in s.cookies})

print("2) GET list page")
page_id = make_page_id()
r2 = s.get(f"https://wenshu.court.gov.cn/website/wenshu/181217BMTKHNT2W0/index.html?pageId={page_id}&s16=%E5%BC%BA%E5%A5%B8%E7%BD%AA&s13=166", timeout=30)
print("status", r2.status_code, "cookies", list(s.cookies.keys()))

print("3) POST api")
payload = {
    "pageId": page_id,
    "s16": "强奸罪",
    "s13": "166",
    "sortFields": "s51:desc",
    "ciphertext": make_ciphertext(),
    "pageNum": "1",
    "pageSize": "5",
    "queryCondition": json.dumps([{"key": "s13", "value": "166"}], ensure_ascii=False, separators=(",", ":")),
    "cfg": "com.lawyee.judge.dc.parse.dto.SearchDataDsoDTO@queryDoc",
    "__RequestVerificationToken": make_token(),
    "wh": "1012", "ww": "2133", "cs": "0",
}
r3 = s.post("https://wenshu.court.gov.cn/website/parse/rest.q4w", data=payload, headers={
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": r2.url,
    "Origin": "https://wenshu.court.gov.cn",
    "X-Requested-With": "XMLHttpRequest",
}, timeout=40)
print("status", r3.status_code)
print(r3.text[:500])
data = r3.json()
if data.get("secretKey") and data.get("result"):
    print("decrypted", decrypt(data["result"], data["secretKey"], today_iv())[:500])

print("\nfull cookie header:")
print("; ".join(f"{c.name}={c.value}" for c in s.cookies))
