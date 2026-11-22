"""
我的交易紀錄：抓每一筆還沒出場的標的最新收盤價，判斷成交了沒、重算損益，重畫 資料/交易紀錄.html。

一支程式只做一件事：讓中控台第八區的「我的交易紀錄」跟著真實股價動。
按中控台那個鍵就是跑這支；也可以自己在資料夾裡跑：
    python 程式/更新交易紀錄.py

資料來源：資料/交易紀錄.csv（一行一筆，直接改這個檔就能加一筆）
產出：資料/交易紀錄.html（中控台第八區顯示的就是這個）

狀態怎麼判（這一段是這支程式唯一需要想的地方，做多掛單適用）：
    沒有進場價                -> 未進場（我決定不做）
    有出場價                  -> 已出場（損益用出場價算，已實現）
    有進場價、還沒出場：
        最新價 <= 進場價      -> 持有（掛單成交了，算未實現損益）
        最新價 >  進場價      -> 等成交（掛單還掛在那裡，一股都沒買到，不能算損益）
抓不到現價的，損益寫「抓不到現價」，不猜。
"""

import csv
import sys
from datetime import datetime
from pathlib import Path

# Windows 的 console 預設不是 utf-8，中文會炸；先換掉
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

根目錄 = Path(__file__).resolve().parent.parent
紀錄檔 = 根目錄 / "資料" / "交易紀錄.csv"
產出檔 = 根目錄 / "資料" / "交易紀錄.html"

欄位 = ["日期", "標的", "AI建議", "老闆決定", "狀態", "進場價", "最新價", "出場價", "損益", "備註"]


def 唸數字(字):
    """空字串、抓不到的，回 None。"""
    try:
        字 = str(字).strip().replace(",", "")
        return float(字) if 字 else None
    except ValueError:
        return None


def 抓最新價(標的):
    """回 (價格, 錯誤訊息)。抓不到就回 (None, 原因)。"""
    代號 = str(標的).split()[0] if str(標的).strip() else ""
    if not 代號:
        return None, "沒有代號"
    try:
        import yfinance as yf
    except ImportError:
        return None, "這台電腦沒裝 yfinance"
    try:
        資料 = yf.Ticker(代號).history(period="5d", interval="1d")
        if 資料 is None or 資料.empty:
            return None, "Yahoo 沒有這檔"
        return float(資料["Close"].iloc[-1]), ""
    except Exception as e:
        return None, str(e)[:60]


def 主程式():
    if not 紀錄檔.exists():
        print("做好了：還沒有 資料/交易紀錄.csv，先放一筆進去")
        return

    with 紀錄檔.open(encoding="utf-8-sig", newline="") as f:
        每筆 = list(csv.DictReader(f))

    抓價筆數 = 0
    for 筆 in 每筆:
        for 名 in 欄位:
            筆.setdefault(名, "")
        筆["最新價"] = ""       # 每次重抓，不沿用上次的數字

        進場 = 唸數字(筆["進場價"])
        出場 = 唸數字(筆["出場價"])

        if 出場 is not None and 進場:
            筆["狀態"] = "已出場"
            筆["損益"] = f"{(出場 - 進場) / 進場 * 100:+.2f}%（已實現）"
            continue

        if 進場 is None:
            筆["狀態"] = "未進場"
            筆["損益"] = ""
            continue

        價格, 錯 = 抓最新價(筆["標的"])
        if 價格 is None:
            筆["狀態"] = "等成交" if 筆["狀態"] != "持有" else "持有"
            筆["損益"] = f"抓不到現價（{錯}）"
            continue

        抓價筆數 += 1
        筆["最新價"] = f"{價格:.2f}"
        if 價格 <= 進場:
            筆["狀態"] = "持有"
            筆["損益"] = f"{(價格 - 進場) / 進場 * 100:+.2f}%（未實現）"
        else:
            筆["狀態"] = "等成交"
            筆["損益"] = ""

    with 紀錄檔.open("w", encoding="utf-8-sig", newline="") as f:
        寫 = csv.DictWriter(f, fieldnames=欄位)
        寫.writeheader()
        寫.writerows(每筆)

    計 = {名: sum(1 for 筆 in 每筆 if 筆["狀態"] == 名) for 名 in ["未進場", "等成交", "持有", "已出場"]}
    一筆一行 = "\n".join(
        f"""      <tr>
        <td class="日期">{筆["日期"]}</td>
        <td class="標的">{筆["標的"]}</td>
        <td>{筆["AI建議"]}</td>
        <td class="決定">{筆["老闆決定"]}</td>
        <td class="狀態 {筆["狀態"]}">{筆["狀態"] or "—"}</td>
        <td class="數字">{筆["進場價"] or "—"}</td>
        <td class="數字">{筆["最新價"] or "—"}</td>
        <td class="數字">{筆["出場價"] or "—"}</td>
        <td class="數字 損益">{筆["損益"] or "—"}</td>
        <td class="備註">{筆["備註"]}</td>
      </tr>"""
        for 筆 in 每筆
    )

    現在 = datetime.now().strftime("%Y-%m-%d %H:%M")
    頁 = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>我的交易紀錄</title>
<style>
  :root {{ --字: #e8edf5; --淡: #9aa7bb; --線: #2a3444; --底: #131a24; --卡: #1a2331; --綠: #3ddc84; --紅: #ff6b6b; --黃: #ffd166; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 18px; background: var(--底); color: var(--字);
         font-family: "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif; font-size: 14px; }}
  h1 {{ font-size: 18px; margin: 0 0 6px; }}
  .說明 {{ color: var(--淡); font-size: 12px; margin-bottom: 14px; line-height: 1.7; }}
  .統計 {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }}
  .統計 div {{ background: var(--卡); border: 1px solid var(--線); border-radius: 8px; padding: 8px 16px; }}
  .統計 span {{ color: var(--淡); font-size: 12px; }}
  .統計 b {{ display: block; font-size: 20px; margin-top: 2px; }}
  table {{ width: 100%; border-collapse: collapse; background: var(--卡); border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: 9px 10px; text-align: left; border-bottom: 1px solid var(--線); vertical-align: top; line-height: 1.6; }}
  th {{ background: #223045; font-size: 12px; color: #cfd9e8; white-space: nowrap; }}
  tr:last-child td {{ border-bottom: none; }}
  td.數字 {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
  td.損益 {{ font-weight: 700; color: var(--綠); }}
  td.決定 {{ color: var(--黃); }}
  td.狀態 {{ white-space: nowrap; font-weight: 700; font-size: 12px; }}
  td.狀態.未進場 {{ color: var(--淡); }}
  td.狀態.等成交 {{ color: var(--黃); }}
  td.狀態.持有 {{ color: var(--綠); }}
  td.狀態.已出場 {{ color: #7fb3ff; }}
  td.備註 {{ color: var(--淡); font-size: 12px; }}
</style>
</head>
<body>
  <h1>我的交易紀錄</h1>
  <div class="說明">
    一行一筆：AI 給什麼訊號、我最後做什麼、後來怎麼了。<br>
    按中控台第八區的「更新交易紀錄（抓現價、算損益）」，這張表會抓最新收盤價重算。<br>
    「等成交」代表掛單還掛著、一股都沒買到，所以不算損益。
  </div>
  <div class="統計">
    <div><span>未進場</span><b>{計["未進場"]}</b></div>
    <div><span>等成交</span><b>{計["等成交"]}</b></div>
    <div><span>持有中</span><b>{計["持有"]}</b></div>
    <div><span>已出場</span><b>{計["已出場"]}</b></div>
    <div><span>最後更新</span><b style="font-size:13px">{現在}</b></div>
  </div>
  <table>
    <thead>
      <tr>{"".join(f"<th>{名}</th>" for 名 in 欄位)}</tr>
    </thead>
    <tbody>
{一筆一行}
    </tbody>
  </table>
</body>
</html>
"""
    產出檔.parent.mkdir(parents=True, exist_ok=True)
    產出檔.write_text(頁, encoding="utf-8")

    print(
        f"做好了：交易紀錄更新完成，共 {len(每筆)} 筆，"
        f"抓到 {抓價筆數} 筆現價（未進場 {計['未進場']}、等成交 {計['等成交']}、持有 {計['持有']}、已出場 {計['已出場']}）。"
    )


if __name__ == "__main__":
    主程式()
