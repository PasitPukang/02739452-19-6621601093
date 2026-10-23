# ฐานข้อมูล

`python -m pipeline.cli init` สร้างเฉพาะตารางเปล่า ไม่ seed ข้อมูล ใช้ SQLite หากไม่ตั้ง `DATABASE_URL`; Docker ใช้ PostgreSQL ฐาน `project` แยกจากฐาน metadata `airflow`

| ตาราง | หน้าที่ |
| --- | --- |
| dataset_records | record_key ไม่ซ้ำ และ payload JSON text ของแถวที่ผ่านการตรวจ |
| dataset_settings | contract ที่ล็อกไว้หลังนำเข้าครั้งแรก |
| pipeline_run_audit | run ID, เวลา UTC, สถานะ, จำนวนแถวในรอบ, stage และข้อความผิดพลาด |

```sql
SELECT COUNT(*) AS total_rows FROM dataset_records;
SELECT run_id, started_at, status, row_count, stage, message
FROM pipeline_run_audit ORDER BY started_at DESC;
SELECT name, value FROM dataset_settings;
```

`row_count` คือจำนวนแถวในไฟล์ที่ตรวจผ่าน ไม่ใช่จำนวนแถวที่เพิ่มใหม่ หากรอบล้มเหลวให้ดู status และ stage ประกอบ

DBeaver: PostgreSQL, host `127.0.0.1`, port `55433`, database `project`, user `airflow`, password ตาม `.env` ฐานใน Docker volume กับไฟล์ SQLite เป็นคนละชุด ไม่ซิงก์กัน
