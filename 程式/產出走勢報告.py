import yfinance as yf
import mplfinance as mpf
import base64
from io import BytesIO

# 抓台積電過去 6 個月日線
代號 = "2330.TW"
tk = yf.Ticker(代號)
df = tk.history(period="6mo")

if df.empty:
    raise SystemExit("yfinance 沒抓到資料，可能沒連網或代號錯誤")

# 用 mplfinance 畫蠟燭圖，存到記憶體
buf = BytesIO()
mpf.plot(df, type="candle", style="yahoo",
         title=f"{代號} 6-Month Daily Chart",
         ylabel="Price (TWD)",
         xrotation=15,
         figratio=(10, 5),
         savefig=dict(fname=buf, format="png", bbox_inches="tight"))
buf.seek(0)
圖片_base64 = base64.b64encode(buf.read()).decode("utf-8")

# 最新價格與統計
最新收盤 = float(df["Close"].iloc[-1])
昨日收盤 = float(df["Close"].iloc[-2])
最高價 = float(df["High"].max())
最低價 = float(df["Low"].min())
漲跌 = 最新收盤 - 昨日收盤
漲跌幅 = (漲跌 / 昨日收盤) * 100

# 動態計算交易建議（以最新收盤為進場基準）
進場點位 = round(最新收盤, 2)
停損比例 = 0.02   # 2% 停損
風險報酬比 = 3    # 1:3
停損點位 = round(進場點位 * (1 - 停損比例), 2)
目標點位 = round(進場點位 * (1 + 停損比例 * 風險報酬比), 2)
實際風險報酬 = round((目標點位 - 進場點位) / (進場點位 - 停損點位), 2)

# 交易理由：根據實際走勢簡要說明
趨勢 = "上漲" if 最新收盤 > 昨日收盤 else "下跌"

html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>交易決策分析報告（第四版）</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, "PingFang TC", "Microsoft JhengHei", sans-serif; background: #f4f6f8; color: #1a202c; }}
  .container {{ max-width: 900px; margin: 32px auto; padding: 0 20px; }}
  .card {{ background: #fff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); margin-bottom: 20px; overflow: hidden; }}
  .card-header {{ background: #1a202c; color: #fff; padding: 16px 20px; font-size: 18px; font-weight: 700; }}
  .card-body {{ padding: 20px; }}
  .card-body h3 {{ margin-top: 0; font-size: 16px; color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
  th, td {{ border: 1px solid #e2e8f0; padding: 10px 12px; text-align: left; font-size: 14px; }}
  th {{ background: #f7fafc; width: 30%; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 700; }}
  .badge-buy {{ background: #c6f6d5; color: #276749; }}
  .badge-sell {{ background: #fed7d7; color: #9b2c2c; }}
  .badge-wait {{ background: #feebc8; color: #975a16; }}
  .rr {{ font-size: 15px; font-weight: 700; color: #2c5282; }}
  .footer {{ text-align: center; color: #718096; font-size: 13px; margin-top: 24px; }}
  .decision {{ background: #f7fafc; border: 2px solid #e2e8f0; border-radius: 10px; padding: 16px 20px; margin-top: 20px; }}
  .decision h3 {{ margin-top: 0; border-bottom: none; }}
  .btn-row {{ display: flex; gap: 10px; margin-top: 12px; }}
  button {{ flex: 1; padding: 10px 16px; font-size: 14px; border: 1px solid #cbd5e0; border-radius: 8px; background: #fff; cursor: pointer; }}
  button.buy {{ background: #48bb78; color: #fff; border-color: #38a169; }}
  button.sell {{ background: #f56565; color: #fff; border-color: #e53e3e; }}
  button.wait {{ background: #ed8936; color: #fff; border-color: #dd6b20; }}
  .走勢圖 {{ text-align: center; margin-top: 10px; }}
  .走勢圖 img {{ max-width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; }}
  .統計列 {{ display: flex; gap: 12px; margin-top: 10px; }}
  .統計卡 {{ flex: 1; background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; text-align: center; }}
  .統計卡 .數值 {{ font-size: 18px; font-weight: 700; color: #2d3748; }}
  .統計卡 .標籤 {{ font-size: 12px; color: #718096; }}
  .漲 {{ color: #2ecc71; }}
  .跌 {{ color: #e74c3c; }}
</style>
</head>
<body>
<div class="container">
  <div class="card">
    <div class="card-header">交易決策分析報告（第四版）</div>
    <div class="card-body">
      <table>
        <tr><th>報告編號</th><td>TRD-20261115-004</td></tr>
        <tr><th>分析日期</th><td>2026-11-15</td></tr>
        <tr><th>交易標的</th><td>台積電 (2330.TW)</td></tr>
        <tr><th>數據來源</th><td>yfinance（Yahoo Finance，歷史 K 線，即時抓取）</td></tr>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header">即時走勢（過去 6 個月日線）</div>
    <div class="card-body">
      <div class="走勢圖">
        <img src="data:image/png;base64,{圖片_base64}" alt="{代號} 走勢圖">
      </div>
      <div class="統計列">
        <div class="統計卡">
          <div class="數值 {'漲' if 漲跌 >= 0 else '跌'}">{最新收盤:,.2f} 元</div>
          <div class="標籤">最新收盤（進場參考）</div>
        </div>
        <div class="統計卡">
          <div class="數值 {'漲' if 漲跌 >= 0 else '跌'}">{漲跌:+.2f} ({漲跌幅:+.2f}%)</div>
          <div class="標籤">漲跌（昨日比較）</div>
        </div>
        <div class="統計卡">
          <div class="數值">{最高價:,.2f} 元</div>
          <div class="標籤">6 個月最高</div>
        </div>
        <div class="統計卡">
          <div class="數值">{最低價:,.2f} 元</div>
          <div class="標籤">6 個月最低</div>
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-header">建議交易設定（根據即時股價重新計算）</div>
    <div class="card-body">
      <table>
        <tr><th>建議進場點位</th><td>{進場點位:,.2f} 元（以即時收盤價為基準，市價進場）</td></tr>
        <tr><th>停損（失效點）</th><td>{停損點位:,.2f} 元（跌破進場價 {{停損比例*100:.0f}}%，結構失效即出場）</td></tr>
        <tr><th>停利（目標價）</th><td>{目標點位:,.2f} 元（上漲 {{停損比例*風險報酬比*100:.0f}}%，風險報酬 1:{{風險報酬比}}）</td></tr>
        <tr><th>預期風險報酬</th><td class="rr">1:{實際風險報酬}，符合預設風險報酬標準</td></tr>
        <tr><th>建議倉位</th><td>單筆風險不超過帳戶總資金的 1%</td></tr>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header">交易理由（根據即時走勢）</div>
    <div class="card-body">
      <ul style="margin:0; padding-left:20px; line-height:1.8;">
        <li><strong>即時價格：</strong>台積電最新收盤 {最新收盤:,.2f} 元，今日{趨勢}，漲跌 {漲跌:+.2f} 元 ({{漲跌幅:+.2f}}%)。</li>
        <li><strong>進場邏輯：</strong>以即時收盤價 {進場點位:,.2f} 元作為進場參考，避免用過時假設數字。</li>
        <li><strong>停損邏輯：</strong>跌破進場價 {{停損比例*100:.0f}}%（{停損點位:,.2f} 元）即判定結構失效，嚴格出場。</li>
        <li><strong>停利邏輯：</strong>上漲 {{停損比例*風險報酬比*100:.0f}}%（{目標點位:,.2f} 元）獲利了結，維持 1:{{風險報酬比}} 風險報酬。</li>
        <li><strong>提醒：</strong>本報告僅根據歷史 K 線產生，不包含即時盤口、外資法人買賣等盤中資訊，實際執行前請自行確認盤面。</li>
      </ul>
    </div>
  </div>

  <div class="decision">
    <h3>老闆判斷（抓住韁繩的地方）</h3>
    <p>以上分析由 AI 團隊（N1）輸出，最後要不要買，由老闆自己決定。</p>
    <div class="btn-row">
      <button class="buy">買進</button>
      <button class="sell">不買</button>
      <button class="wait">觀望</button>
    </div>
    <p style="margin-top:12px; font-size:13px; color:#718096;">決定後請記錄：買／不買、理由、執行價格，供日後複盤。</p>
  </div>

  <div class="footer">
    本報告僅供個人投資決策參考，不構成投資建議。股市有風險，入市需謹慎。<br>
    走勢圖與交易設定由 Python + yfinance 抓取 Yahoo Finance 歷史數據產生，圖片與數字已嵌入本檔，離線開啟也能看圖。
  </div>
</div>
</body>
</html>"""

with open(r"C:\Users\郭宏洋\Desktop\OpenCode\W7-工作資料夾專題\成品\交易決策分析報告-第四版.html", "w", encoding="utf-8") as f:
    f.write(html)

print("第四版報告已產出：成品/交易決策分析報告-第四版.html")
print(f"最新收盤：{最新收盤:,.2f} 元，進場：{進場點位:,.2f}，停損：{停損點位:,.2f}，目標：{目標點位:,.2f}，RR 1:{實際風險報酬}")
