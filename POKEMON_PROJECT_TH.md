# ข้อเสนอโครงงานและรายการตรวจรับ

หมวด: ข้อมูลเกม Pokémon

ขอบเขต: รวมข้อมูล Pokémon หมายเลข National Pokédex 1–151 เฉพาะร่างปกติ วิเคราะห์ประเภทและ base stats ปัจจุบันจาก 3 แหล่ง

แหล่ง: 1) Pokémon Database (HTML scraping) 2) PokéAPI (REST) 3) Pokémon Showdown (JSON)

ลำดับที่ 19 · รหัสนิสิต 6621601093 · Repository https://github.com/PasitPukang/02739452-19-6621601093

## คำถามวิเคราะห์

1. โปเกมอนหมายเลข 1–151 กระจายตามประเภทอย่างไร? โปเกมอนสองประเภทนับในทั้งสองกลุ่ม
2. ตัวใดมี base stat total สูงสุด และเมื่อกรองประเภท/ค่าขั้นต่ำผลเปลี่ยนอย่างไร?
3. ทั้งสามแหล่งครอบคลุม ID เดียวกันหรือไม่ มีค่าสถิติแตกต่างกันหรือไม่?

## ขอบเขตส่งมอบ

- ใช้ 3 TaskGroups ขนาน extract/transform; ต่อด้วย merge_validate, quality_route, load_postgres หรือ quarantine และ finish
- ไม่มี Selenium, ไม่มี API key และไม่มีข้อมูลบัญชีผู้เล่น/บุคคล
- อ่าน robots ของโปรแกรมที่ใช้งานจริงทุก origin เก็บหลักฐาน เคารพ crawl-delay และ cache PokéAPI
- ผลจริง 453 observations รวมเหลือ 151 unique species, UPSERT key `dex_id`, observations key `(source,dex_id)`
- หน้าเว็บอ่าน PostgreSQL โดยตรง มี 4 KPI, 2 กราฟ, 5 ตัวกรอง/ตัวเลือกเรียง, ตารางแบ่งหน้า, provenance และ Pipeline history
- ทดสอบ source outage และ quality rejection แบบจำลองที่ระบุชัดเจน เก็บหลักฐานจาก scheduler จริง
- PDF 3 หน้า พร้อม Graph/Grid/dashboard, ปัญหาและวิธีแก้, แผนจัดลำดับงาน และลิงก์ GitHub

## สิ่งที่ตัดออกเพื่อให้งานเสร็จและตรวจได้

ไม่ทำระบบล็อกอิน dashboard, battle simulator, predictive model, ภาพ/แอนิเมชันตัวละคร, live streaming, ระบบสมาชิก หรือ Power BI เพราะไม่จำเป็นต่อโจทย์ เน้นความถูกต้องของ ID/สถิติ การกู้คืน source failure และการเปิดระบบซ้ำได้จาก README

## หลักฐาน

- `audit/pokemon_validation.json`: rerun, partial, rejected และ normal ผ่าน Airflow จริง
- `audit/browser_validation.json`: การแบ่งหน้า ตัวกรอง HTTP 400 และ mobile overflow ของ dashboard
- `audit/screenshots/`: ภาพจริงจาก Edge DevTools ไม่ใช้ Selenium
- `tests/test_pokemon.py`: parser/รูปแบบ schema/robots/cache/dedup/UPSERT/quality/filters
- `submission/19_6621601093_summary.pdf`: รายงานส่ง Classroom

ผลการตรวจเป็นหลักฐานทางเทคนิค ไม่ใช่การรับประกันคะแนนจากอาจารย์
