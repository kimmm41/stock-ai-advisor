import yfinance as yf
import mplfinance as mpf
import base64
from io import BytesIO
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import html as html_mod
from datetime import datetime

埠號 = 8765
代號後綴 = ".TW"

# ================= SMC 參數 =================
停損比例 = 0.02
風險報酬比 = 3
帳戶風險比例 = 0.01
進場評分門檻 = 75  # 進場最低分數

NA = "N/A"

# ================= HTML 樣板 =================

輸入頁面 = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>股票即時分析 - 輸入股票號碼</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, "PingFang TC", "Microsoft JhengHei", sans-serif; background: #f4f6f8; color: #1a202c; }
  .container { max-width: 500px; margin: 80px auto; padding: 0 20px; }
  .card { background: #fff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); overflow: hidden; }
  .card-header { background: #1a202c; color: #fff; padding: 16px 20px; font-size: 18px; font-weight: 700; }
  .card-body { padding: 30px 20px; text-align: center; }
  .form-group { margin-bottom: 20px; }
  label { display: block; margin-bottom: 8px; font-size: 14px; color: #4a5568; }
  input[type="text"] { width: 100%; padding: 12px 16px; font-size: 16px; border: 1px solid #cbd5e0; border-radius: 8px; box-sizing: border-box; }
  input[type="text"]:focus { outline: none; border-color: #4ea1ff; }
  button { width: 100%; padding: 12px 20px; font-size: 16px; font-weight: 700; background: #4ea1ff; color: #fff; border: none; border-radius: 8px; cursor: pointer; }
  button:hover { background: #3888e6; }
  button:disabled { background: #a0aec0; cursor: not-allowed; }
  .hint { margin-top: 16px; font-size: 13px; color: #718096; }
  .hint b { color: #2d3748; }
</style>
</head>
<body>
<div class="container">
  <div class="card">
    <div class="card-header">AI 交易決策分析系統（SMC）</div>
    <div class="card-body">
      <form id="form">
        <div class="form-group">
          <label for="symbol">股票號碼（例如 2330）</label>
          <input type="text" id="symbol" name="symbol" placeholder="輸入台股 4 碼代號" maxlength="10" autocomplete="off">
        </div>
        <button type="submit">即時抓取並分析</button>
      </form>
      <div class="hint">
        <b>使用方式：</b>輸入台股代號（如 2330、2317），系統會自動加上 .TW 後綴，抓取 Yahoo Finance 的多時間框架 K 線，進行 SMC 聰明錢分析並產生交易決策報告。<br>
        需要連網，抓取失敗時會顯示錯誤訊息。
      </div>
    </div>
  </div>
</div>
<script>
  document.getElementById('form').addEventListener('submit', function(e) {
    e.preventDefault();
    const symbol = document.getElementById('symbol').value.trim();
    if (!symbol) { alert('請輸入股票號碼'); return; }
    const btn = this.querySelector('button');
    btn.disabled = true;
    btn.textContent = '分析中…';
    const url = '/analyze?symbol=' + encodeURIComponent(symbol);
    fetch(url)
      .then(r => r.text())
      .then(text => {
        document.open();
        document.write(text);
        document.close();
      })
      .catch(err => {
        alert('抓取失敗：' + err.message);
        btn.disabled = false;
        btn.textContent = '即時抓取並分析';
      });
  });
</script>
</body>
</html>"""

錯誤頁面樣板 = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>抓取失敗</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, "PingFang TC", "Microsoft JhengHei", sans-serif; background: #f4f6f8; color: #1a202c; }
  .container { max-width: 600px; margin: 80px auto; padding: 0 20px; }
  .card { background: #fff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); overflow: hidden; }
  .card-header { background: #e53e3e; color: #fff; padding: 16px 20px; font-size: 18px; font-weight: 700; }
  .card-body { padding: 30px 20px; text-align: center; }
  .錯誤訊息 { background: #fed7d7; border: 1px solid #fc8181; border-radius: 8px; padding: 16px; margin-bottom: 20px; color: #9b2c2c; font-size: 14px; line-height: 1.6; }
  a { color: #4ea1ff; text-decoration: none; }
  a:hover { text-decoration: underline; }
  button { padding: 10px 20px; font-size: 14px; background: #4ea1ff; color: #fff; border: none; border-radius: 8px; cursor: pointer; }
  button:hover { background: #3888e6; }
</style>
</head>
<body>
<div class="container">
  <div class="card">
    <div class="card-header">抓取失敗</div>
    <div class="card-body">
      <div class="錯誤訊息">###錯誤訊息###</div>
      <button onclick="history.back()">回上一頁</button>
      <a href="/">回首頁</a>
    </div>
  </div>
</div>
</body>
</html>"""

分析頁面樣板 = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>###代號### AI 交易決策報告</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, "PingFang TC", "Microsoft JhengHei", sans-serif; background: #f4f6f8; color: #1a202c; }
  .container { max-width: 1000px; margin: 16px auto; padding: 0 16px; }
  .card { background: #fff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); margin-bottom: 16px; overflow: hidden; }
  .card-header { background: #1a202c; color: #fff; padding: 12px 16px; font-size: 16px; font-weight: 700; }
  .card-body { padding: 16px; }
  .card-body h3 { margin-top: 0; font-size: 14px; color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  th, td { border: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; font-size: 13px; }
  th { background: #f7fafc; width: 28%; }
  .rr { font-size: 14px; font-weight: 700; color: #2c5282; }
  .footer { text-align: center; color: #718096; font-size: 12px; margin-top: 16px; }
  .決策區 { background: #f7fafc; border: 2px solid #e2e8f0; border-radius: 10px; padding: 16px; margin-top: 16px; }
  .決策區 h3 { margin-top: 0; border-bottom: none; font-size: 15px; }
  .btn-row { display: flex; gap: 8px; margin-top: 10px; }
  button { flex: 1; padding: 8px 14px; font-size: 13px; border: 1px solid #cbd5e0; border-radius: 6px; background: #fff; cursor: pointer; }
  button.active { box-shadow: 0 0 10px rgba(0,0,0,0.15); }
  button.buy.active { background: #48bb78; color: #fff; border-color: #38a169; }
  button.sell.active { background: #f56565; color: #fff; border-color: #e53e3e; }
  button.wait.active { background: #ed8936; color: #fff; border-color: #dd6b20; }
  button.notrade.active { background: #a0aec0; color: #fff; border-color: #718096; }
  button.inactive { opacity: 0.45; cursor: not-allowed; background: #edf2f7; color: #a0aec0; border-color: #cbd5e0; }
  .走勢圖 { text-align: center; margin-top: 8px; }
  .走勢圖 img { max-width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; }
  .統計列 { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
  .統計卡 { flex: 1; min-width: 120px; background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; text-align: center; }
  .統計卡 .數值 { font-size: 16px; font-weight: 700; color: #2d3748; }
  .統計卡 .副標 { font-size: 10px; color: #a0aec0; margin-top: 2px; }
  .統計卡 .標籤 { font-size: 11px; color: #718096; }
  .漲 { color: #2ecc71; }
  .跌 { color: #e74c3c; }
  .分數高 { color: #2ecc71; font-weight: 700; }
  .分數中 { color: #ed8936; font-weight: 700; }
  .分數低 { color: #e74c3c; font-weight: 700; }
  .na { color: #a0aec0; font-style: italic; }
  a.回首頁 { color: #4ea1ff; text-decoration: none; font-size: 13px; }
  a.回首頁:hover { text-decoration: underline; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 700; }
  .badge-bullish { background: #c6f6d5; color: #276749; }
  .badge-bearish { background: #fed7d7; color: #9b2c2c; }
  .badge-neutral { background: #feebc8; color: #975a16; }
  .警示列 { background: #fef3c7; border: 1px solid #f59e0b; border-radius: 6px; padding: 8px 12px; margin-top: 8px; font-size: 12px; color: #92400e; }
</style>
</head>
<body>
<div class="container">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
    <h2>###代號### AI 交易決策報告</h2>
    <a class="回首頁" href="/">← 輸入其他股票</a>
  </div>

  <div class="card">
    <div class="card-header">1. 市場基本資訊</div>
    <div class="card-body">
      <table>
        <tr><th>交易標的</th><td>###代號###</td></tr>
        <tr><th>交易所</th><td>台股 (Yahoo Finance)</td></tr>
        <tr><th>當前價格</th><td class="###漲跌顏色###">###最新收盤### 元</td></tr>
        <tr><th>分析時間</th><td>###分析時間###</td></tr>
        <tr><th>HTF Bias</th><td><span class="badge ###htf_badge###">###htf_bias###</span></td></tr>
        <tr><th>LTF Bias</th><td><span class="badge ###ltf_badge###">###ltf_bias###</span></td></tr>
        ###多空對齊區###
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header">2. 市場結構分析</div>
    <div class="card-body">
      <table>
        <tr><th>當前市場結構</th><td>###市場結構###</td></tr>
        <tr><th>最近一次 BOS</th><td>###最近BOS###</td></tr>
        <tr><th>最近一次 MSS / CHOCH</th><td>###最近MSS_CHOCH###</td></tr>
        <tr><th>重要 OB</th><td>###重要OB###</td></tr>
        <tr><th>重要 FVG</th><td>###重要FVG###</td></tr>
        <tr><th>Premium / Discount 狀態</th><td>###premium_discount###</td></tr>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header">3. 流動性分析</div>
    <div class="card-body">
      <table>
        <tr><th>上方流動性</th><td>###上方流動性###</td></tr>
        <tr><th>下方流動性</th><td>###下方流動性###</td></tr>
        <tr><th>已獵取流動性</th><td>###已獵取流動性###</td></tr>
        <tr><th>未獵取流動性</th><td>###未獵取流動性###</td></tr>
        <tr><th>預期價格目標</th><td>###預期價格目標###</td></tr>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header">4. 價格行為分析</div>
    <div class="card-body">
      <table>
        <tr><th>當前市場階段</th><td>###市場階段###</td></tr>
        <tr><th>是否出現 Manipulation</th><td>###是否Manipulation###</td></tr>
        <tr><th>是否出現 Expansion</th><td>###是否Expansion###</td></tr>
        <tr><th>是否存在回調進場機會</th><td>###是否回調進場###</td></tr>
        <tr><th>是否符合交易模型</th><td>###是否符合模型###</td></tr>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header">5. AI 交易決策與評分</div>
    <div class="card-body">
      <div class="統計列">
        <div class="統計卡">
          <div class="數值 ###評分顏色###">###信心分數### 分</div>
          <div class="副標">###分數說明###</div>
          <div class="標籤">信心分數</div>
        </div>
        <div class="統計卡">
          <div class="數值 ###rr顏色###">###風險報酬###</div>
          <div class="標籤">風險報酬比</div>
        </div>
        <div class="統計卡">
          <div class="數值 ###漲跌顏色###">###建議進場###</div>
          <div class="標籤">建議進場</div>
        </div>
        <div class="統計卡">
          <div class="數值 ###跌顏色###">###停損###</div>
          <div class="標籤">停損</div>
        </div>
        <div class="統計卡">
          <div class="數值 ###漲顏色###">###止盈1###</div>
          <div class="標籤">止盈 1</div>
        </div>
        <div class="統計卡">
          <div class="數值 ###漲顏色###">###止盈2###</div>
          <div class="標籤">止盈 2</div>
        </div>
      </div>
      <table style="margin-top:12px;">
        <tr><th>交易信號</th><td><span class="badge ###信號顏色###">###交易信號###</span></td></tr>
        <tr><th>建議倉位</th><td>###建議倉位###</td></tr>
        <tr><th>帳戶風險</th><td>###帳戶風險###</td></tr>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header">6. 交易理由</div>
    <div class="card-body">
      <table>
        <tr><th>支持進場的證據</th><td>###支持證據###</td></tr>
        <tr><th>反對進場的證據</th><td>###反對證據###</td></tr>
        <tr><th>可能的失敗情境</th><td>###失敗情境###</td></tr>
        <tr><th>計畫失效條件</th><td>###失效條件###</td></tr>
      </table>
    </div>
  </div>

  <div class="決策區">
    <h3>7. 最終執行建議</h3>
    <p>只允許以下四種狀態：BUY / SELL / WAIT / NO TRADE</p>
    <div class="btn-row">
      <button class="buy ###buy_class###">BUY</button>
      <button class="sell ###sell_class###">SELL</button>
      <button class="wait ###wait_class###">WAIT</button>
      <button class="notrade ###notrade_class###">NO TRADE</button>
    </div>
    <p style="margin-top:8px; font-size:12px; color:#718096;">由老闆最終判斷要不要執行（抓住韁繩的地方）。</p>
  </div>

  <div class="footer">
    本報告僅供個人投資決策參考，不構成投資建議。股市有風險，入市需謹慎。<br>
    數據由 Python + yfinance 抓取 Yahoo Finance，分析基於 SMC 聰明錢概念。
  </div>
</div>
</body>
</html>"""

# ================= SMC 分析邏輯 =================

def 正規化代號(raw):
    raw = raw.strip().upper()
    if not raw:
        return raw
    if '.' in raw:
        return raw
    if raw.isdigit() and len(raw) == 4:
        return raw + 代號後綴
    return raw

def 抓數據(代號, 週期="6mo", 間隔="1d"):
    tk = yf.Ticker(代號)
    df = tk.history(period=週期, interval=間隔)
    if df.empty:
        raise ValueError(f"找不到 {代號} 的 {間隔} 數據")
    return df

def 分析_HTF(代號):
    try:
        df_d = 抓數據(代號, 週期="1y", 間隔="1d")
    except Exception:
        df_d = None
    try:
        df_4h = 抓數據(代號, 週期="730d", 間隔="4h")
    except Exception:
        df_4h = None

    htf_bias = "Neutral"
    htf_badge = "badge-neutral"
    市場結構 = "盤整"
    premium_discount = "未知"
    重要OB = "未偵測到"
    重要FVG = "未偵測到"
    多空對齊區 = ""
    多空說明 = ""
    看漲OB範圍 = None
    看跌OB範圍 = None

    if df_d is not None and len(df_d) > 20:
        最近收盤 = float(df_d["Close"].iloc[-1])
        最近高 = float(df_d["High"].tail(20).max())
        最近低 = float(df_d["Low"].tail(20).min())
        範圍中點 = (最近高 + 最近低) / 2

        if 最近收盤 > 範圍中點:
            htf_bias = "Bullish"
            htf_badge = "badge-bullish"
            市場結構 = "多頭"
            premium_discount = "Premium"
        else:
            htf_bias = "Bearish"
            htf_badge = "badge-bearish"
            市場結構 = "空頭"
            premium_discount = "Discount"

        最後K = df_d.tail(5)
        for i in range(len(最後K)-1, 0, -1):
            開 = float(最後K["Open"].iloc[i])
            收 = float(最後K["Close"].iloc[i])
            高 = float(最後K["High"].iloc[i])
            低 = float(最後K["Low"].iloc[i])
            身體 = abs(收 - 開)
            全範圍 = 高 - 低
            if 全範圍 > 0 and 身體 / 全範圍 > 0.6:
                if 收 > 開:
                    看漲OB範圍 = (低, 開)
                    重要OB = f"看漲 OB 約 {低:.2f}-{開:.2f}"
                else:
                    看跌OB範圍 = (開, 高)
                    重要OB = f"看跌 OB 約 {開:.2f}-{高:.2f}"
                break

    # 多空週期對齊判斷
    ltf_bias = htf_bias
    ltf_badge = htf_badge
    if df_4h is not None and len(df_4h) > 10:
        最後收 = float(df_4h["Close"].iloc[-1])
        最後開 = float(df_4h["Open"].iloc[-1])
        if htf_bias == "Bullish":
            if 最後收 < 最後開:
                ltf_bias = "Bearish"
                ltf_badge = "badge-bearish"
                多空對齊區 = f"""
                <tr><th>多空週期對齊</th><td><span class="badge badge-bearish">不一致（HTF 多 / LTF 空）</span></td></tr>
                <tr><td colspan="2"><div class="警示列">大週期多頭中的小週期回調，需等待 LTF 出現 MSS 轉多再行評估</div></td></tr>"""
            else:
                ltf_bias = "Bullish"
                ltf_badge = "badge-bullish"
                多空對齊區 = f"""
                <tr><th>多空週期對齊</th><td><span class="badge badge-bullish">一致（多頭）</span></td></tr>"""
        elif htf_bias == "Bearish":
            if 最後收 > 最後開:
                ltf_bias = "Bullish"
                ltf_badge = "badge-bullish"
                多空對齊區 = f"""
                <tr><th>多空週期對齊</th><td><span class="badge badge-bullish">不一致（HTF 空 / LTF 多）</span></td></tr>
                <tr><td colspan="2"><div class="警示列">大週期空頭中的小週期反彈，需等待 LTF 出現 MSS 轉空再行評估</div></td></tr>"""
            else:
                ltf_bias = "Bearish"
                ltf_badge = "badge-bearish"
                多空對齊區 = f"""
                <tr><th>多空週期對齊</th><td><span class="badge badge-bearish">一致（空頭）</span></td></tr>"""
        else:
            多空對齊區 = f"""
            <tr><th>多空週期對齊</th><td><span class="badge badge-neutral">中性</span></td></tr>"""
    else:
        多空對齊區 = f"""
        <tr><th>多空週期對齊</th><td><span class="badge badge-neutral">數據不足</span></td></tr>"""

    return {
        "htf_bias": htf_bias,
        "htf_badge": htf_badge,
        "ltf_bias": ltf_bias,
        "ltf_badge": ltf_badge,
        "市場結構": 市場結構,
        "premium_discount": premium_discount,
        "重要OB": 重要OB,
        "重要FVG": 重要FVG,
        "看漲OB範圍": 看漲OB範圍,
        "看跌OB範圍": 看跌OB範圍,
        "多空對齊區": 多空對齊區,
        "df_d": df_d,
        "df_4h": df_4h,
    }

def 分析_流動性(df_d, 代號):
    if df_d is None or len(df_d) < 10:
        return {
            "上方流動性": NA,
            "下方流動性": NA,
            "已獵取流動性": NA,
            "未獵取流動性": NA,
            "預期價格目標": NA,
            "下方低點": None,
        }

    最近高 = float(df_d["High"].tail(20).max())
    最近低 = float(df_d["Low"].tail(20).min())
    當前價 = float(df_d["Close"].iloc[-1])
    昨收 = float(df_d["Close"].iloc[-2])

    上方流動性 = f"近 20 日高點 {最近高:.2f} 元"
    下方流動性 = f"近 20 日低點 {最近低:.2f} 元"

    if 當前價 > 昨收:
        已獵取 = "可能已獵取下方流動性後反彈"
        未獵取 = f"上方流動性 {最近高:.2f} 元尚未觸及"
        預期目標 = f"{最近高:.2f} 元"
    else:
        已獵取 = "可能已獵取上方流動性後回落"
        未獵取 = f"下方流動性 {最近低:.2f} 元尚未觸及"
        預期目標 = f"{最近低:.2f} 元"

    return {
        "上方流動性": 上方流動性,
        "下方流動性": 下方流動性,
        "已獵取流動性": 已獵取,
        "未獵取流動性": 未獵取,
        "預期價格目標": 預期目標,
        "下方低點": 最近低,
    }

def 分析_價格行為(df_d, 代號):
    if df_d is None or len(df_d) < 5:
        return {
            "市場階段": "數據不足",
            "是否Manipulation": NA,
            "是否Expansion": NA,
            "是否回調進場": NA,
            "是否符合模型": NA,
            "最近BOS": NA,
            "最近MSS_CHOCH": NA,
        }

    最後5 = df_d.tail(5)
    當前價 = float(最後5["Close"].iloc[-1])
    昨收 = float(最後5["Close"].iloc[-2])
    漲跌 = 當前價 - 昨收

    if abs(漲跌) / 當前價 < 0.01:
        市場階段 = "盤整 (Consolidation)"
        最近BOS = f"價格正在 {float(df_d['Low'].tail(20).min()):.2f} - {float(df_d['High'].tail(20).max()):.2f} 區間震盪，等待 BOS 或 CHoCH 變盤訊號"
        最近MSS_CHOCH = NA
    elif 漲跌 > 0:
        市場階段 = "擴張 (Expansion)"
        最近BOS = "價格向上擴張，等待回調確認"
        最近MSS_CHOCH = "待偵測"
    else:
        市場階段 = "回調 (Retracement)"
        最近BOS = NA
        最近MSS_CHOCH = "待偵測"

    是否Manipulation = "是" if abs(漲跌) / 當前價 > 0.03 else "否"
    是否Expansion = "是" if 市場階段 == "擴張 (Expansion)" else "否"
    是否回調進場 = "是" if 市場階段 == "回調 (Retracement)" else "否"
    是否符合模型 = "待確認" if 市場階段 != "盤整 (Consolidation)" else "否"

    return {
        "市場階段": 市場階段,
        "是否Manipulation": 是否Manipulation,
        "是否Expansion": 是否Expansion,
        "是否回調進場": 是否回調進場,
        "是否符合模型": 是否符合模型,
        "最近BOS": 最近BOS,
        "最近MSS_CHOCH": 最近MSS_CHOCH,
    }

def 計算_評分(htf_bias, 市場結構, 流動性分析, 價格行為, 風險報酬):
    分數 = 0
    if htf_bias == "Bullish":
        分數 += 15
    elif htf_bias == "Neutral":
        分數 += 5
    if "尚未觸及" in 流動性分析.get("未獵取流動性", ""):
        分數 += 15
    elif 流動性分析.get("未獵取流動性") != NA:
        分數 += 8
    if 價格行為.get("是否Manipulation") == "是":
        分數 += 15
    if 市場結構 in ["多頭", "空頭"]:
        分數 += 10
    else:
        分數 += 5
    if 價格行為.get("是否Expansion") == "是":
        分數 += 10
    分數 += 10
    分數 += 5
    if 風險報酬 >= 2:
        分數 += 10
    elif 風險報酬 >= 1.5:
        分數 += 5
    return min(分數, 100)

def 計算_風險管理(當前價, 信號, 停損比例=停損比例, 風險報酬比=風險報酬比, 下方低點=None):
    if 信號 not in ["LONG", "SHORT"]:
        return {
            "停損": NA,
            "目標1": NA,
            "目標2": NA,
            "rr": NA,
            "建議倉位": "不建議建倉",
            "帳戶風險": "0%",
            "失效條件": "目前無進行中交易計畫，等待有效結構出現",
        }

    if 信號 == "LONG":
        停損 = round(當前價 * (1 - 停損比例), 2)
        目標1 = round(當前價 * (1 + 停損比例 * 風險報酬比), 2)
        目標2 = round(當前價 * (1 + 停損比例 * 風險報酬比 * 1.5), 2)
        風險金額 = 當前價 - 停損
        失效條件 = f"價格跌破 {停損:.2f} 元（結構失效）"
        if 下方低點:
            失效條件 += f"，或跌破下方流動性低點 {下方低點:.2f} 元"
    else:
        停損 = round(當前價 * (1 + 停損比例), 2)
        目標1 = round(當前價 * (1 - 停損比例 * 風險報酬比), 2)
        目標2 = round(當前價 * (1 - 停損比例 * 風險報酬比 * 1.5), 2)
        風險金額 = 停損 - 當前價
        失效條件 = f"價格突破 {停損:.2f} 元（結構失效）"

    rr = round(abs((目標1 - 當前價) / 風險金額), 2) if 風險金額 > 0 else 0
    建議倉位 = "帳戶資金 1% 風險"
    帳戶風險 = "1%"

    return {
        "停損": 停損,
        "目標1": 目標1,
        "目標2": 目標2,
        "rr": rr,
        "建議倉位": 建議倉位,
        "帳戶風險": 帳戶風險,
        "失效條件": 失效條件,
    }

def 決定_信號(htf_bias, 價格行為, 評分):
    if 評分 >= 進場評分門檻 and 價格行為.get("是否符合模型") not in ["否", NA]:
        if htf_bias == "Bullish":
            return "LONG"
        elif htf_bias == "Bearish":
            return "SHORT"
    if 評分 >= 進場評分門檻 - 15:
        return "WAIT"
    return "NO TRADE"

def 抓取並分析(raw_symbol):
    代號 = 正規化代號(raw_symbol)

    htf = 分析_HTF(代號)
    df_d = htf["df_d"]

    if df_d is None or len(df_d) < 5:
        raise ValueError(f"找不到 {代號} 的足夠數據，請確認股票代號是否正確")

    最新收盤 = float(df_d["Close"].iloc[-1])
    昨日收盤 = float(df_d["Close"].iloc[-2])
    漲跌 = 最新收盤 - 昨日收盤
    漲跌幅 = (漲跌 / 昨日收盤) * 100
    最高價 = float(df_d["High"].max())
    最低價 = float(df_d["Low"].min())

    流動性 = 分析_流動性(df_d, 代號)
    價格行為 = 分析_價格行為(df_d, 代號)

    # SMC 進場邏輯：價格必須回調到 OB 區或支撐位附近
    看漲OB範圍 = htf.get("看漲OB範圍")
    建議進場價 = NA  # 預設不建議進場

    if 看漲OB範圍:
        ob_低, ob_高 = 看漲OB範圍
        # 價格是否已回調到 OB 區或附近（OB 上緣 3% 以內）
        if 最新收盤 <= ob_高 * 1.03:
            建議進場價 = round(ob_高, 2)  # 建議掛單在 OB 上緣

    # 評分與信號決策：只有回調到 OB 區且評分足夠才給 LONG
    評分 = 計算_評分(htf["htf_bias"], htf["市場結構"], 流動性, 價格行為, 3.0)

    if 評分 >= 進場評分門檻 and 建議進場價 != NA and 價格行為.get("是否符合模型") not in ["否", NA]:
        信號 = "LONG" if htf["htf_bias"] == "Bullish" else "SHORT"
    elif 評分 >= 進場評分門檻 - 15:
        信號 = "WAIT"
    else:
        信號 = "NO TRADE"

    # 風險管理使用建議進場價（如果有的話）
    風險進場價 = 建議進場價 if 建議進場價 != NA else 最新收盤
    風險 = 計算_風險管理(風險進場價, 信號, 下方低點=流動性.get("下方低點"))

    # 顯示格式化
    if 評分 >= 85:
        評分顏色 = "分數高"
    elif 評分 >= 70:
        評分顏色 = "分數中"
    else:
        評分顏色 = "分數低"

    信號顏色 = "badge-bullish" if 信號 == "LONG" else ("badge-bearish" if 信號 == "SHORT" else "badge-neutral")

    buy_class = "buy active" if 信號 == "LONG" else "buy inactive"
    sell_class = "sell active" if 信號 == "SHORT" else "sell inactive"
    wait_class = "wait active" if 信號 == "WAIT" else "wait inactive"
    notrade_class = "notrade active" if 信號 == "NO TRADE" else "notrade inactive"

    漲跌顏色 = "漲" if 漲跌 >= 0 else "跌"
    跌顏色 = "跌" if 漲跌 < 0 else ""
    漲顏色 = "漲" if 漲跌 >= 0 else ""

    rr顯示 = f"1:{風險['rr']}" if 風險['rr'] != NA else NA
    rr顏色 = "漲" if isinstance(風險['rr'], (int, float)) and 風險['rr'] >= 2 else ("跌" if isinstance(風險['rr'], (int, float)) and 風險['rr'] < 1.5 else "")

    buf = BytesIO()
    mpf.plot(df_d, type="candle", style="yahoo",
             title=f"{代號} SMC 分析圖",
             ylabel="Price (TWD)",
             xrotation=15,
             figratio=(10, 5),
             savefig=dict(fname=buf, format="png", bbox_inches="tight"))
    buf.seek(0)
    圖片_base64 = base64.b64encode(buf.read()).decode("utf-8")

    分析時間 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 分數說明（加入進場門檻）
    if 信號 == "NO TRADE":
        分數說明 = f"未達進場門檻 {進場評分門檻} 分"
    else:
        分數說明 = f"達到進場門檻 {進場評分門檻} 分"

    # 支持證據（過濾 N/A）
    多空對齊說明 = "HTF 與 LTF 同步多頭" if htf["htf_bias"] == htf["ltf_bias"] and htf["htf_bias"] == "Bullish" else f"HTF Bias {htf['htf_bias']}"
    支持證據_parts = [f"{多空對齊說明}，評分 {評分} 分"]
    if rr顯示 != NA:
        支持證據_parts.append(f"風險報酬 {rr顯示}")
    if 建議進場價 != NA and 看漲OB範圍:
        支持證據_parts.append(f"鎖定看漲 OB 區 {看漲OB範圍[0]:.2f}-{看漲OB範圍[1]:.2f} 進行回踩佈局")
    支持證據 = "、".join(支持證據_parts)

    # 盤整區間（用於反對證據）
    盤整高 = float(df_d["High"].tail(20).max())
    盤整低 = float(df_d["Low"].tail(20).min())

    if 信號 == "NO TRADE":
        反對證據 = f"當前處於 {盤整低:.2f}-{盤整高:.2f} 區間盤整，尚未出現突破或變盤（CHoCH）訊號"
        if 流動性.get("下方低點"):
            失敗情境 = f"價格跌破 {流動性['下方低點']:.2f} 元下方流動性或支撐區，結構轉空"
        else:
            失敗情境 = "等待突破或回調確認失敗，結構轉空"
    else:
        if 看漲OB範圍:
            反對證據 = f"價格尚未回調至看漲 OB 區 {看漲OB範圍[0]:.2f}-{看漲OB範圍[1]:.2f}，需等待回踩確認"
        else:
            反對證據 = "未偵測到有效看漲 OB 區，需等待價格回踩確認"
        失敗情境 = "價格跌破停損點位，結構失效"

    內容 = 分析頁面樣板
    替換 = {
        "###代號###": html_mod.escape(代號),
        "###最新收盤###": f"{最新收盤:,.2f}",
        "###漲跌顏色###": 漲跌顏色,
        "###分析時間###": 分析時間,
        "###htf_bias###": htf["htf_bias"],
        "###htf_badge###": htf["htf_badge"],
        "###ltf_bias###": htf["ltf_bias"],
        "###ltf_badge###": htf["ltf_badge"],
        "###多空對齊區###": htf["多空對齊區"],
        "###市場結構###": htf["市場結構"],
        "###最近BOS###": 價格行為["最近BOS"],
        "###最近MSS_CHOCH###": 價格行為["最近MSS_CHOCH"],
        "###重要OB###": htf["重要OB"],
        "###重要FVG###": htf["重要FVG"],
        "###premium_discount###": htf["premium_discount"],
        "###上方流動性###": 流動性["上方流動性"],
        "###下方流動性###": 流動性["下方流動性"],
        "###已獵取流動性###": 流動性["已獵取流動性"],
        "###未獵取流動性###": 流動性["未獵取流動性"],
        "###預期價格目標###": 流動性["預期價格目標"],
        "###市場階段###": 價格行為["市場階段"],
        "###是否Manipulation###": 價格行為["是否Manipulation"],
        "###是否Expansion###": 價格行為["是否Expansion"],
        "###是否回調進場###": 價格行為["是否回調進場"],
        "###是否符合模型###": 價格行為["是否符合模型"],
        "###信心分數###": str(評分),
        "###評分顏色###": 評分顏色,
        "###分數說明###": 分數說明,
        "###風險報酬###": rr顯示,
        "###rr顏色###": rr顏色,
        "###建議進場###": f"{建議進場價:,.2f}" if 建議進場價 != NA else NA,
        "###停損###": f"{風險['停損']:,.2f}" if 風險['停損'] != NA else NA,
        "###止盈1###": f"{風險['目標1']:,.2f}" if 風險['目標1'] != NA else NA,
        "###止盈2###": f"{風險['目標2']:,.2f}" if 風險['目標2'] != NA else NA,
        "###漲顏色###": 漲顏色,
        "###跌顏色###": 跌顏色,
        "###交易信號###": 信號,
        "###信號顏色###": 信號顏色,
        "###建議倉位###": 風險["建議倉位"],
        "###帳戶風險###": 風險["帳戶風險"],
        "###支持證據###": 支持證據,
        "###反對證據###": 反對證據,
        "###失敗情境###": 失敗情境,
        "###失效條件###": 風險["失效條件"],
        "###buy_class###": buy_class,
        "###sell_class###": sell_class,
        "###wait_class###": wait_class,
        "###notrade_class###": notrade_class,
        "###圖片_base64###": 圖片_base64,
        "###漲###": "漲",
        "###跌###": "跌",
    }

    for 舊, 新 in 替換.items():
        內容 = 內容.replace(舊, 新)

    return 內容

# ================= HTTP 伺服器 =================

class 處理器(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        路徑 = parsed.path
        參數 = parse_qs(parsed.query)

        if 路徑 == "/" or 路徑 == "/index.html":
            self._回應(200, "text/html; charset=utf-8", 輸入頁面)
        elif 路徑 == "/analyze":
            symbol = 參數.get("symbol", [""])[0]
            if not symbol:
                self._回應(200, "text/html; charset=utf-8", 錯誤頁面樣板.replace("###錯誤訊息###", "請輸入股票號碼"))
                return
            try:
                內容 = 抓取並分析(symbol)
                self._回應(200, "text/html; charset=utf-8", 內容)
            except Exception as e:
                self._回應(200, "text/html; charset=utf-8", 錯誤頁面樣板.replace("###錯誤訊息###", str(e)))
        else:
            self._回應(404, "text/plain; charset=utf-8", "找不到頁面")

    def _回應(self, code, 類型, 內容):
        位元組 = 內容.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", 類型)
        self.send_header("Content-Length", str(len(位元組)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(位元組)

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    伺服器 = HTTPServer(("127.0.0.1", 埠號), 處理器)
    print(f"AI 交易決策分析伺服器啟動：http://127.0.0.1:{埠號}")
    print("在瀏覽器開啟上面的網址，輸入股票代號即可進行 SMC 分析")
    伺服器.serve_forever()
