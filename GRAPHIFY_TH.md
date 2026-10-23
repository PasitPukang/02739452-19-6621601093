# Graphify สำหรับนำทาง agent ในโปรเจกต์

ติดตั้งแพ็กเกจทางการ `graphifyy[sql]==0.9.94` จาก Graphify Labs เมื่อ 23 ตุลาคม 2026 ใน environment แยก `.tools/graphify` ไม่เพิ่ม dependencies ให้ Airflow หรือเว็บ

อ้างอิง: [Repository ทางการ](https://github.com/Graphify-Labs/graphify), [วิธีติดตั้ง](https://docs.graphify.com/installation)

## พร้อมใช้งาน

- `AGENTS.md` บอกให้ agent ค้นกราฟก่อน แล้วอ่านโค้ดตามเส้นทางที่พบ พร้อมอ้างอิง `PROJECT_CONTEXT.md` สำหรับข้อตกลงผู้ใช้
- `.codex/skills/graphify/SKILL.md` และ references เป็น skill ระดับโปรเจกต์สำหรับ Codex
- `.codex/hooks.json` เป็น hook ที่ตัวติดตั้งสร้าง และปรับให้ชี้ executable ในเครื่องนี้แล้ว ตัว hook เป็น no-op ตาม upstream; การนำทาง Codex ใช้ `AGENTS.md` เป็นหลัก ไม่ได้บังคับทุก tool call
- `graphify-out/graph.json` เป็นกราฟที่ CLI ใช้ค้นหา
- `graphify-out/GRAPH_REPORT.md` และ `graphify-out/graph.html` เป็นรายงานกับแผนภาพ

กราฟเป็นแผนที่โค้ด ไม่ใช่ฐานข้อมูลธุรกิจและไม่ใช่ข้อมูลร้านอาหาร หาก Codex ยังไม่แสดง skill ใหม่ ให้เปิดเซสชันโปรเจกต์ใหม่ แล้วใช้ `$graphify` ได้ตาม skill ที่ติดตั้ง ส่วน CLI ด้านล่างใช้ได้ทันที

## คำสั่งใน PowerShell

รันจาก `D:\final_bigdata` โดยใช้ path ของโปรแกรมนี้ เพราะไม่ได้ติดตั้งใน global PATH:

```powershell
# ค้นหาบริเวณโค้ดที่เกี่ยวข้อง
.\.tools\graphify\Scripts\graphify.exe query "validate export_csv" --budget 1200

# ดูฟังก์ชันและความสัมพันธ์
.\.tools\graphify\Scripts\graphify.exe explain "validate()"

# ดูเส้นทางระหว่างฟังก์ชัน
.\.tools\graphify\Scripts\graphify.exe path "run()" "export_csv()"

# อัปเดตหลังแก้โค้ด
.\.tools\graphify\Scripts\graphify.exe update .
```

หากต้องสร้างกราฟใหม่พร้อม HTML/รายงานแบบ local ที่ไม่เรียกโมเดล:

```powershell
.\.tools\graphify\Scripts\graphify.exe extract . --code-only --max-workers 1
.\.tools\graphify\Scripts\graphify.exe cluster-only . --no-label
Start-Process .\graphify-out\graph.html
```

กราฟที่พบความสัมพันธ์ไม่ได้แทนการอ่านโค้ดจริงก่อนแก้ไข ความสัมพันธ์ที่อนุมานต้องตรวจที่ source อีกครั้ง

## ข้อมูลที่ไม่นำเข้ากราฟ

`.graphifyignore` กัน `.env*`, ข้อมูลจริงใน `data/`, CSV ส่งออก, ฐาน SQLite, logs, `.venv/`, `.tools/`, `.codex/`, `.agents/` และผลกราฟเอง ไม่อ่านฐาน PostgreSQL สดและไม่เปิด Cloud/MCP server

ใช้ AST และ SQL parser แบบ local เท่านั้น เอกสาร Markdown ไม่ผ่าน semantic extraction จึงให้อ่าน `PROJECT_CONTEXT.md`, `START_HERE_TH.md` และ `README.md` ประกอบ ส่วน Dockerfile/Compose ไม่ได้รับประกันว่ามีความสัมพันธ์ครบในกราฟ code-only นี้

`.tools/` และ `graphify-out/` ถูกกันจาก Git และ Docker build context ถ้าย้ายเครื่องต้องติดตั้ง tool และสร้างกราฟใหม่ ไม่ต้องคัดลอก environment หรือกราฟเก่า

## ติดตั้งใหม่เมื่อย้ายเครื่อง

```powershell
python -m venv .tools/graphify
uv --no-cache pip install --python .tools/graphify/Scripts/python.exe "graphifyy[sql]==0.9.94"
.\.tools\graphify\Scripts\graphify.exe install --project --platform codex
```

ตรวจ `.codex/hooks.json` หลังติดตั้ง หากคำสั่งเป็น bare `graphify` ให้ใช้ executable path ของเครื่องใหม่หรือเพิ่ม environment นี้ใน PATH ของเซสชัน ก่อนเรียก hook ไม่ต้องเปลี่ยน config ของ Codex ระดับผู้ใช้หรือเปิด parallel agents เพื่อค้นกราฟที่สร้างแล้ว
