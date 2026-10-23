# ผลตรวจโครงโปรเจกต์

วันที่ตรวจ: **23 ตุลาคม 2026 (Asia/Bangkok)**

## อัปเดต: Graphify สำหรับนำทาง agent

- ติดตั้ง `graphifyy[sql]==0.9.94` แยกใน `.tools/graphify` พร้อม skill ระดับโปรเจกต์สำหรับ Codex
- สร้างกราฟ code-only แบบ local สำเร็จ: 64 nodes, 146 edges พร้อม JSON, HTML และรายงาน
- Query พบตำแหน่ง validation และ DAG; `path "run()" "export_csv()"` พบความสัมพันธ์ `calls [EXTRACTED]`; `explain "validate()"` แสดง source และผู้เรียกได้
- ใช้ `.graphifyignore` ตัดความลับ ข้อมูลจริง environment และผลลัพธ์ที่สร้างออก ไม่เรียก LLM หรือ Cloud
- SQL parser ติดตั้งแล้ว แต่ไฟล์ `CREATE DATABASE` ไม่มี table/column symbols ให้สกัด จึงมีคำเตือน no symbols ตามปกติ
- ไม่ทำ semantic extraction ของเอกสารหรือยืนยันว่า Dockerfile/Compose ถูกเชื่อมครบ ใช้คู่มือ Markdown ประกอบตาม `GRAPHIFY_TH.md`

## อัปเดต: เปิด Airflow + Docker ตามคำขอ

- Build image ของโปรเจกต์และ `docker compose up -d --build` สำเร็จ
- `project-init` และ `airflow-init` จบด้วย exit code 0
- PostgreSQL healthy; Airflow webserver, scheduler และ dashboard ทำงาน
- เข้าหน้า login ผ่าน host port `8089` ได้ และทดสอบล็อกอิน `admin` สำเร็จโดยไม่พิมพ์รหัสผ่านในผลตรวจ
- `/health` รายงาน metadatabase และ scheduler เป็น healthy
- `airflow dags list-import-errors --output json` คืน `[]`
- เว็บสถานะที่ port `8091` อ่าน PostgreSQL ได้: `rows=0`, `latest_run=null`
- สร้าง `.env` พร้อมรหัสสุ่มสำหรับเครื่องนี้ ไม่คัดลอกรหัสจากต้นแบบและไม่บันทึกรหัสในเอกสาร

ยังไม่ Trigger งานนำเข้าจริง เพราะ contract ยังว่างและไม่มี CSV การตรวจ runtime นี้แทนข้อจำกัดเดิมเรื่องยังไม่ได้ build/open Compose และ login แต่ไม่ได้ยืนยันการรัน task กับข้อมูลจริง

Runtime Airflow มี requests dependency/deprecation warnings จาก base image แต่การ login, health และ DAG import ผ่าน ยังไม่ได้ปรับรุ่น dependency นอกขอบเขตการเปิดระบบ

## สิ่งที่ตรวจจริง

| รายการ | ผล |
| --- | --- |
| Unit/HTTP tests บน Python 3.14.7 + SQLAlchemy 1.4.54 | ผ่าน 8 tests |
| CSV ภาษาไทย/BOM, quoted comma, ช่องขาด/เกิน, quote ไม่ปิด | ผ่าน |
| Contract ว่าง, คีย์ว่าง/ซ้ำ และการเปลี่ยน contract | ปฏิเสธตามที่กำหนด |
| รันซ้ำ/อัปเดตแถวเดิม | จำนวนแถวไม่เพิ่มซ้ำ |
| ข้อมูลไม่ผ่าน validation | ข้อมูลเดิมและ export เดิมไม่ถูกแก้ |
| Export ล้มเหลวหลัง commit | Audit เป็น FAILED/export และรันซ้ำสำเร็จ |
| HTTP หน้าแรก, API สถานะว่าง, URL ที่ไม่มี | 200, 200, 404 ตามลำดับ |
| Python compile ของ pipeline/web/dags/tests | ผ่าน |
| `pip check` ใน .venv | ไม่พบ dependency ที่ขัดกัน |
| `docker compose config --quiet` | ผ่าน โดยใช้รหัสชั่วคราวใน environment ของคำสั่งตรวจ ไม่มีการเขียน .env |
| Airflow DagBag import | ผ่าน: ไม่มี import error, manual schedule, catchup=False, max_active_runs=1 |
| PostgreSQL 16 integration ใน container ชั่วคราว | ผ่าน: load, rerun, update, duplicate rejection, audit และ export |
| ฐาน SQLite ที่เตรียมให้ผู้ใช้หลัง init | 0 แถว, latest_run=null |

การตรวจ Airflow รอบแรกใช้ image `thailand-rainfall-observatory-seed-postgres:latest` ที่มีอยู่ในเครื่อง ซึ่งเป็น runtime ของต้นแบบ โดย mount โค้ดใหม่แบบอ่านอย่างเดียว ไม่เปลี่ยนฐานต้นแบบ ต่อมา build/open Compose ของโปรเจกต์นี้แล้วตามอัปเดตด้านบน

PostgreSQL integration ใช้ฐาน `project_check` ใน container แยกที่ไม่เปิด host port จากนั้นลบ container พร้อม anonymous volume และ network ที่สร้าง ข้อมูลทดสอบอยู่ใน temporary directory ไม่แก้ `config/dataset.json` จริง

## คำสั่งตรวจซ้ำ

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q pipeline web dags tests
.\.venv\Scripts\python.exe -m pip check
```

`tests/check_postgres.py` เป็น integration self-check ที่สั่งเอง ต้องตั้ง `TEST_POSTGRES_URL` ให้ชี้ PostgreSQL ว่างสำหรับทดสอบโดยเฉพาะ และตั้ง `PYTHONPATH` ให้เห็น root ของโปรเจกต์ สคริปต์ไม่ล้างฐานให้และปฏิเสธฐานที่มีแถว/audit อยู่แล้ว

## สิ่งที่ยังไม่ได้ตรวจ

- การ trigger task ผ่าน scheduler ด้วยข้อมูลจริง (build/open Compose และ login ตรวจผ่านแล้ว)
- แสดงผลใน browser จริง/หน้าจอมือถือ — ตรวจ HTTP และ HTML เท่านั้น
- ข้อมูลจริง API ภายนอก กฎเฉพาะหัวข้อ และ performance ระดับ Big Data
- Power BI Desktop/PBIX และความตรงกับ rubric ที่ยังไม่ได้รับ

ผลนี้ยืนยันเฉพาะโครงและพฤติกรรมที่ทดสอบ ไม่ใช่ผลวิเคราะห์หรือการรับรองคุณภาพของชุดข้อมูลจริง
