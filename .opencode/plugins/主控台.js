// I4582 W7 駕駛艙中控台：老闆在網頁上跟 AI 代表談、按鍵，這支外掛轉給 OpenCode，並把公司的狀態、成品送回網頁。
//
// 為什麼是外掛：學生用 OpenCode 電腦版，不必開終端機。開這個專案、按「新增工作階段」，
// OpenCode 就自動載入 .opencode/plugins/ 裡的外掛，這支就在 http://127.0.0.1:4777 開好中控台。
// 2026-10-11 實測：電腦版跑外掛的環境沒有 Bun（Bun.serve 會 ReferenceError），所以只用 node: 內建模組。
// 2026-11-07 W7 加：跟 AI 代表的對話區（同一段對話一直接著談）、請它先停下來、AI 團隊與待辦、成品櫃。
// 2026-11-15 修：OpenCode 新版要求外掛要 default 匯出一個有 id 和 setup 的定義。
//              舊寫法（具名匯出 async ({client, directory}) => {}）會載入失敗，
//              日誌原文：Plugin must export a default definition with an id and an effect or setup function.
//              這次照新版 API 改寫：ctx.location.directory 取代 directory，ctx.session.* 取代 client.session.*。
//              新版沒有 status/todo/children 這幾個方法，待辦與幫手先給空的，「忙不忙」用最後一則訊息推。
//
// 安全：只聽 127.0.0.1；只接受固定幾種動作，不接受任意指令；每次開專案產生一把隨機鑰匙，
// 只放在外掛自己送出去的中控台網頁裡。別的網站讀不到這一頁（沒有開跨站讀取），就拿不到鑰匙，送不了動作。
// 成品櫃只送 成品/ 底下的檔，路徑裡有 .. 一律拒絕。
// 2026-11-08 加「八、我的公司加的」：中控台是基本款，學生跟 AI 團隊在 公司/中控台加的.json 寫上自己公司要看的區、要按的鍵，
// 不用改這支外掛就接得上。按鍵只跑那份檔裡寫好的指令（照名稱對），網頁送不了任意指令；/看/ 送資料夾裡的檔，. 開頭與 .. 一律拒絕。
import { createServer } from "node:http"
import { spawn } from "node:child_process"
import { readFile, writeFile, mkdir, stat } from "node:fs/promises"
import { join, normalize, extname, sep } from "node:path"
import { randomBytes } from "node:crypto"

const 起始埠 = 4777

const 前言 = {
  討論: 話 => "【中控台・老闆按「跟它討論」：這一則只想、只回話，不動任何檔，不跑任何指令】\n" + 話,
  照做: 話 => "【中控台・老闆按「照這樣做」：照 AGENTS.md 開工，每一步都更新 公司/公司資料.json 的目前階段與流程狀態】\n" + 話,
  回答: 話 => "【中控台・老闆在「AI 在等你的事」回答了】\n" + 話 + "\n把這個決定寫進 公司/公司資料.json 那一題的「老闆的決定」。你原本在做成品，就接著做；原本是開好公司、在等老闆看策略與流程，就停在那裡，等他按「照這樣做」。",
}

const 型別 = {
  ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8", ".md": "text/plain; charset=utf-8", ".txt": "text/plain; charset=utf-8",
  ".srt": "text/plain; charset=utf-8", ".csv": "text/plain; charset=utf-8",
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp",
  ".mp4": "video/mp4", ".webm": "video/webm", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
  ".pdf": "application/pdf",
}

export default {
  id: "control-panel",
  async setup(ctx) {
    const directory = ctx.location.directory
    const 鑰匙 = randomBytes(16).toString("hex")
    const 記 = (level, message) => { try { console.log("[中控台] " + level + "：" + message) } catch {} }
    const 讀身體 = req => new Promise((ok, no) => {
      let b = ""
      req.on("data", c => { b += c; if (b.length > 20000) no(new Error("太長")) })
      req.on("end", () => ok(b))
    })
    const 回 = (res, code, type, body) => { res.writeHead(code, { "Content-Type": type, "Cache-Control": "no-store" }); res.end(body) }
    const 回JSON = (res, 物) => 回(res, 200, "application/json; charset=utf-8", JSON.stringify(物))

    // ===== 跟 OpenCode 講話：全部集中這裡，新版 API 換寫法時只改這一段 =====
    const 開對話 = async 標題 => {
      const s = await ctx.session.create({ title: 標題 })
      return s?.id || s?.data?.id || ""
    }
    const 有這段對話 = async id => {
      if (!id) return false
      try { const s = await ctx.session.get({ sessionID: id }); return !!(s?.id || s?.data?.id) } catch { return false }
    }
    const 拿訊息 = async id => {
      try { return (await ctx.session.context({ sessionID: id })) || [] } catch { return [] }
    }
    const 送話 = async (id, 字, 模型) => {
      if (模型 && /^[\w.-]+\/[\w.:-]+$/.test(模型)) {
        const [providerID, ...rest] = 模型.split("/")
        try { await ctx.session.switchModel({ sessionID: id, model: { providerID, id: rest.join("/") } }) } catch (e) { 記("warn", "換模型沒成功：" + e) }
      }
      return ctx.session.prompt({ sessionID: id, text: 字 })
    }
    const 停話 = async id => {
      if (!id) return
      try { await ctx.session.interrupt({ sessionID: id, resume: false }) } catch (e) { 記("warn", "停不下來：" + e) }
    }

    // AI 代表固定用同一段對話，老闆在中控台講的話一直接著談。對話編號存在 公司/代表對話.txt
    const 代表檔 = join(directory, "公司", "代表對話.txt")
    let 代表 = ""
    const 找代表 = async (要建) => {
      if (!代表) { try { 代表 = (await readFile(代表檔, "utf8")).trim() } catch {} }
      if (代表 && await 有這段對話(代表)) return 代表
      代表 = ""
      if (!要建) return ""
      代表 = await 開對話("中控台：AI 代表")
      await mkdir(join(directory, "公司"), { recursive: true })
      await writeFile(代表檔, 代表 + "\n")
      return 代表
    }

    const 讀資料 = async () => {
      let 資料 = "{}"
      try {
        資料 = await readFile(join(directory, "公司", "公司資料.json"), "utf8")
        try { JSON.parse(資料) }
        catch {
          // 公司寫檔時常在字串裡留下看不見的 Tab、換行（2026-10-11 電腦版實跑撞到）。換成空白再讀；多出來的反斜線拿掉
          const 修 = 資料.replace(/[\u0000-\u001f]/g, " ").replace(/\\(?!["\\/bfnrtu])/g, "")
          JSON.parse(修); 資料 = 修
        }
      }
      catch (e) { 資料 = JSON.stringify({ 還沒有: String(e).includes("ENOENT") ? "公司還沒蓋" : "公司資料.json 讀不了：公司可能正在寫，等一分鐘；一直這樣的話，在對話區跟 AI 代表說「公司資料.json 讀不了，請修好格式」" }) }
      return 資料
    }

    // 「八、我的公司加的」那幾個鍵的最近一次結果；上次開著時的紀錄從 公司/按鍵紀錄.json 讀回來
    let 跑的紀錄 = {}
    try { 跑的紀錄 = JSON.parse(await readFile(join(directory, "公司", "按鍵紀錄.json"), "utf8")); for (const k in 跑的紀錄) 跑的紀錄[k].正在跑 = false } catch {}

    const 伺服器 = createServer(async (req, res) => {
      try {
        const u = new URL(req.url, "http://127.0.0.1")
        const 路 = decodeURIComponent(u.pathname)   // 瀏覽器會把中文網址轉成 %E8… 的編碼
        if (req.method === "GET" && 路 === "/") {
          const 頁 = (await readFile(join(directory, "主控台.html"), "utf8")).replace("__鑰匙__", 鑰匙)
          return 回(res, 200, "text/html; charset=utf-8", 頁)
        }
        if (req.method === "GET" && 路 === "/資料") return 回(res, 200, "application/json; charset=utf-8", await 讀資料())

        if (req.method === "GET" && 路 === "/對話") {
          const id = await 找代表(false)
          if (!id) return 回JSON(res, { 還沒開始: true, 訊息: [], 忙: false, 待辦: [], 幫手: [] })
          const 原始 = await 拿訊息(id)
          // 2026-11-15 實測新版結構：每一則是 { type: "user"|"assistant"|"idle", text?, content?, model?, time }
          // user 的文字在 text；assistant 的在 content 陣列（type 為 text / reasoning / tool）；idle 只是這一輪結束的記號
          const 訊息 = 原始
            .filter(m => m.type === "user" || m.type === "assistant")
            .slice(-40)
            .map(m => {
              const 段們 = m.content || []
              const 字 = m.type === "user"
                ? String(m.text || "").trim()
                : 段們.filter(c => c.type === "text").map(c => c.text).join("\n").trim()
              const 工具 = 段們.filter(c => c.type === "tool").map(c => (c.tool || c.name || "工具") + ((c.state?.status === "running" || c.status === "running") ? "（進行中）" : ""))
              return { 誰: m.type === "user" ? "老闆" : "AI 代表", 字, 工具, 時間: m.time?.created || 0 }
            })
            .filter(m => m.字 || m.工具.length)
          // 最後一則是 idle 代表這一輪做完了；不是 idle 就是還在忙
          const 末 = 原始[原始.length - 1]
          const 忙 = !!末 && 末.type !== "idle"
          const 末AI = [...原始].reverse().find(m => m.type === "assistant")
          const 錯 = 末AI && 末AI.error
          const 錯誤 = 錯 && !忙 ? String(錯.data?.message || 錯.name || 錯.message || "出錯了") : ""
          const 模型 = 末AI?.model ? [末AI.model.providerID, 末AI.model.id].filter(Boolean).join("/") : ""
          return 回JSON(res, { 訊息, 忙, 待辦: [], 幫手: [], 錯誤, 模型, 卡住: false, 幾分鐘沒動: 0 })
        }

        if (req.method === "POST" && (路 === "/說" || 路 === "/停" || 路 === "/重來")) {
          if (req.headers["x-key"] !== 鑰匙) return 回(res, 403, "text/plain; charset=utf-8", "鑰匙不對")
          if (路 === "/重來") {
            // 卡住時：停掉舊的那一段，開一段新的 AI 代表對話，請它讀公司資料接著做。實跑發現同一段對話接著問常常還是卡，開新的才解得開
            const { 模型 } = JSON.parse((await 讀身體(req)) || "{}")
            const 舊 = await 找代表(false)
            await 停話(舊)
            代表 = ""; try { await writeFile(代表檔, "") } catch {}
            const id = await 找代表(true)
            const 話 = "【中控台・老闆按「卡住了，換一段新對話接著做」】\n上一段對話卡住了，這是新的一段。先讀 AGENTS.md、公司/記住的事.md、公司/公司資料.json，看流程做到哪、成品/ 裡已經有哪些檔（有做好卻還沒登記進 成品 的，先登記），然後從還沒完成的那一步接著做。先用一兩句告訴老闆你看到做到哪、接下來做什麼。"
            送話(id, 話, 模型).catch(e => 記("error", "重來失敗：" + e))
            return 回JSON(res, { ok: true })
          }
          if (路 === "/停") {
            const id = await 找代表(false)
            await 停話(id)
            return 回JSON(res, { ok: true })
          }
          const { 模式, 話, 模型 } = JSON.parse(await 讀身體(req))
          if (!前言[模式]) return 回(res, 400, "text/plain; charset=utf-8", "沒有這個動作")
          if (!String(話 || "").trim()) return 回(res, 400, "text/plain; charset=utf-8", "沒有寫字")
          const id = await 找代表(true)
          if (!id) return 回(res, 500, "text/plain; charset=utf-8", "開不了對話，請看 OpenCode 日誌")
          // 老闆在中控台選了頭腦（模型）就用那一個；沒選就用 opencode.json 的預設
          送話(id, 前言[模式](String(話).slice(0, 4000)), 模型).catch(e => 記("error", "送給 AI 代表失敗：" + e))
          return 回JSON(res, { ok: true })
        }

        if (req.method === "GET" && 路 === "/加的") {
          let 加 = {}
          try { 加 = JSON.parse(await readFile(join(directory, "公司", "中控台加的.json"), "utf8")) }
          catch (e) { 加 = String(e).includes("ENOENT") ? {} : { 讀不了: "公司/中控台加的.json 格式壞了：" + String(e.message || e).slice(0, 200) } }
          return 回JSON(res, { ...加, 跑的紀錄: 跑的紀錄 })
        }

        if (req.method === "POST" && 路 === "/按") {
          if (req.headers["x-key"] !== 鑰匙) return 回(res, 403, "text/plain; charset=utf-8", "鑰匙不對")
          const { 名稱 } = JSON.parse((await 讀身體(req)) || "{}")
          let 加 = {}
          try { 加 = JSON.parse(await readFile(join(directory, "公司", "中控台加的.json"), "utf8")) } catch (e) { return 回(res, 400, "text/plain; charset=utf-8", "公司/中控台加的.json 讀不了：" + e.message) }
          const 鍵 = (加.按鍵 || []).find(k => k.名稱 === 名稱)
          if (!鍵 || !String(鍵.指令 || "").trim()) return 回(res, 400, "text/plain; charset=utf-8", "公司/中控台加的.json 裡沒有這個鍵，或它沒寫指令")
          if (跑的紀錄[名稱]?.正在跑) return 回(res, 409, "text/plain; charset=utf-8", "這個鍵還在跑")
          const 紀 = 跑的紀錄[名稱] = { 正在跑: true, 開始: Date.now(), 輸出: "" }
          const 子 = spawn(String(鍵.指令), { cwd: directory, shell: true, windowsHide: true })
          const 收 = b => { 紀.輸出 = (紀.輸出 + b.toString()).slice(-6000) }
          子.stdout.on("data", 收); 子.stderr.on("data", 收)
          const 限 = setTimeout(() => { 收("\n（跑超過 15 分鐘，中控台把它停掉了）"); 子.kill() }, 15 * 60 * 1000)
          const 收尾 = async (碼, 錯) => {
            clearTimeout(限); if (!紀.正在跑) return
            if (錯) 收("\n" + 錯)
            紀.正在跑 = false; 紀.結束 = Date.now(); 紀.成功 = 碼 === 0
            try { await writeFile(join(directory, "公司", "按鍵紀錄.json"), JSON.stringify(跑的紀錄, null, 2)) } catch {}
          }
          子.on("close", 碼 => 收尾(碼)); 子.on("error", e => 收尾(1, "跑不起來：" + e.message))
          return 回JSON(res, { ok: true })
        }

        if (req.method === "GET" && 路.startsWith("/看/")) {
          const 相對 = 路.slice("/看/".length)
          const 段 = 相對.split(/[\\/]/)
          if (段.includes("..") || 段.some(x => x.startsWith("."))) return 回(res, 403, "text/plain; charset=utf-8", "不行")
          const 檔 = normalize(join(directory, 相對))
          if (!檔.startsWith(normalize(directory) + sep)) return 回(res, 403, "text/plain; charset=utf-8", "不行")
          try {
            const s = await stat(檔)
            if (!s.isFile()) return 回(res, 404, "text/plain; charset=utf-8", "不是檔案")
            res.writeHead(200, { "Content-Type": 型別[extname(檔).toLowerCase()] || "text/plain; charset=utf-8", "Cache-Control": "no-store", "Content-Length": s.size })
            return res.end(await readFile(檔))
          } catch { return 回(res, 404, "text/plain; charset=utf-8", "資料夾裡沒有這個檔：" + 相對) }
        }

        if (req.method === "GET" && 路.startsWith("/成品/")) {
          const 相對 = 路.slice("/成品/".length)
          if (相對.split(/[\\/]/).includes("..")) return 回(res, 403, "text/plain; charset=utf-8", "不行")
          const 根 = join(directory, "成品")
          const 檔 = normalize(join(根, 相對))
          if (!檔.startsWith(根 + sep)) return 回(res, 403, "text/plain; charset=utf-8", "不行")
          try {
            const s = await stat(檔)
            if (!s.isFile()) return 回(res, 404, "text/plain; charset=utf-8", "不是檔案")
            const 型 = 型別[extname(檔).toLowerCase()] || "application/octet-stream"
            res.writeHead(200, { "Content-Type": 型, "Cache-Control": "no-store", "Content-Length": s.size })
            return res.end(await readFile(檔))
          } catch { return 回(res, 404, "text/plain; charset=utf-8", "成品櫃裡沒有這個檔：" + 相對) }
        }
        回(res, 404, "text/plain; charset=utf-8", "沒有這一頁")
      } catch (e) {
        回(res, 500, "text/plain; charset=utf-8", "中控台出錯：" + e)
      }
    })
    // 4777 被占了（例如另一個工作資料夾也開著），就往下找空的，最多試到 4796。實際網址寫進 公司/主控台網址.txt
    let 埠 = 起始埠
    const 開 = () => 伺服器.listen(埠, "127.0.0.1")
    伺服器.on("error", e => {
      if (e.code === "EADDRINUSE" && 埠 < 起始埠 + 19) { 埠 += 1; return 開() }
      記("warn", "中控台沒開成：" + e)
    })
    伺服器.on("listening", async () => {
      const 網址 = "http://127.0.0.1:" + 埠
      記("info", "中控台開在 " + 網址)
      try { await mkdir(join(directory, "公司"), { recursive: true }); await writeFile(join(directory, "公司", "主控台網址.txt"), 網址 + "\n") } catch {}
    })
    開()
    return () => { try { 伺服器.close() } catch {} }
  },
}
